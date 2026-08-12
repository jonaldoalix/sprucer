"""Close residual coverage gaps for the CI coverage gate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.adapters.storage import sqlalchemy_store as store_mod
from sprucer.api import app as app_mod
from sprucer.service import CareerService
from sprucer.settings import Settings
from sprucer.ssrf import UnsafeUrlError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


def _svc(tmp_path: Path) -> CareerService:
    store = create_storage(f"sqlite:///{tmp_path / 'r.db'}")
    store.save_truth(json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8")))
    return CareerService(store, MockLlm())


def test_sqlalchemy_migrate_and_list_generations(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'm.db'}")
    mock_conn = MagicMock()
    begin_cm = MagicMock()
    begin_cm.__enter__.return_value = mock_conn
    begin_cm.__exit__.return_value = False
    with patch.object(store_mod, "inspect") as insp:
        insp.return_value.get_columns.return_value = [{"name": "id"}, {"name": "content"}]
        with patch.object(store.engine, "begin", return_value=begin_cm):
            store._ensure_generation_duration_column()
    assert mock_conn.exec_driver_sql.called

    with patch.object(store_mod, "inspect", side_effect=RuntimeError("boom")):
        store._ensure_generation_duration_column()

    store.upsert_application({"id": "a1"}, jd_text="jd")
    with patch.object(store, "get_application", return_value={"id": "a1", "generations": None}):
        assert store.list_generations("a1") == []


def test_create_app_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'c.db'}",
        auth_mode="dev",
        host="127.0.0.1",
        dev_password="p",
        session_secret="s" * 24,
        llm_url="http://x",
        llm_api_key="k",
        llm_model="m",
        cors_origins="http://test",
    )
    monkeypatch.setattr(app_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(app_mod, "validate_runtime_settings", lambda s: [])
    app = app_mod.create_app()
    assert app.title == "Sprucer"


def test_api_remaining_error_branches(tmp_path: Path):
    from fastapi.testclient import TestClient

    from sprucer.adapters.auth import create_auth
    from sprucer.api.app import build_app

    # Callback rejected when auth is not OIDC
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'd.db'}",
        auth_mode="dev",
        host="127.0.0.1",
        dev_password="p",
        session_secret="s" * 24,
        llm_url="http://x",
        llm_api_key="k",
        llm_model="m",
        cors_origins="http://test",
    )
    store = create_storage(settings.database_url)
    auth = create_auth(mode="dev", dev_password="p", session_secret="s" * 24, api_keys=set())
    app = build_app(settings=settings, service=CareerService(store, MockLlm()), auth=auth)
    with TestClient(app) as client:
        assert client.get("/v1/auth/oidc/callback?code=a&state=b").status_code == 400

    settings2 = Settings(
        database_url=f"sqlite:///{tmp_path / 'e.db'}",
        auth_mode="oidc",
        host="127.0.0.1",
        session_secret="s" * 24,
        oidc_issuer="https://idp.example",
        oidc_client_id="cid",
        oidc_client_secret="sec",
        llm_url="http://x",
        llm_api_key="k",
        llm_model="m",
        cors_origins="http://test",
    )
    store2 = create_storage(settings2.database_url)
    auth2 = create_auth(
        mode="oidc",
        dev_password="x",
        session_secret="s" * 24,
        api_keys={"ak"},
        oidc_issuer="https://idp.example",
        oidc_client_id="cid",
        oidc_client_secret="sec",
    )

    async def boom(_code: str):
        raise RuntimeError("exchange failed")

    auth2.client.exchange_code = boom  # type: ignore[method-assign]
    app2 = build_app(settings=settings2, service=CareerService(store2, MockLlm()), auth=auth2)
    with TestClient(app2) as client:
        client.cookies.set("sprucer_oidc_state", "expected")
        assert client.get("/v1/auth/oidc/callback?code=a&state=wrong").status_code == 400
        assert client.get("/v1/auth/oidc/callback?code=a&state=expected").status_code == 400
        assert (
            client.post(
                "/v1/applications",
                json={},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )


@pytest.mark.asyncio
async def test_service_remaining_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    svc = _svc(tmp_path)

    truth = svc.store.get_truth()
    truth["metrics"] = [{"id": "blank", "text": "   "}, {"id": "ok", "text": "Ship"}]
    cat = svc._interview_cite_catalog(truth)
    assert all(c["id"] != "blank" for c in cat)

    # Email heading + cover letter heading → reject for email-only
    assert not svc._content_satisfies_types(
        "## Email\nSubject: Hi\n\n## Cover Letter\nDear",
        ["email"],
    )
    # Email heading without Subject
    assert not svc._content_satisfies_types("## Email\nHello there", ["email"])

    batches = svc._type_batches(["cover", "custom:a", "custom:b", "custom:c"])
    assert len(batches) >= 2

    # Force slug collision loop (275-276)
    text = "Company: CollisionCo\nTitle: CollisionRole\n"
    first = await svc.jd_ingest(source_type="paste", text=text)
    second = await svc.jd_ingest(source_type="paste", text=text)
    assert first["application"]["id"] != second["application"]["id"]

    app_id = first["application"]["id"]

    class OnceBad(MockLlm):
        def __init__(self):
            super().__init__()
            self.n = 0

        async def chat(self, messages, **kw):
            self.n += 1
            if self.n == 1:
                return "## Wrong heading\nnope"
            return await MockLlm().chat(messages, **kw)

    svc.llm = OnceBad()
    await svc.generate(application_id=app_id, types=["interview"])
    svc.llm = OnceBad()
    await svc.generate(application_id=app_id, types=["linkedin"])

    class FakeResp:
        status_code = 302
        text = ""
        headers = {"location": "https://evil.example/x"}
        url = "https://jobs.example/start"

        @property
        def is_redirect(self):
            return True

    class FC:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    def selective(url, resolve=True):
        if "evil" in url:
            raise UnsafeUrlError("blocked")
        return url

    monkeypatch.setattr(httpx, "AsyncClient", FC)
    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", selective)
    with pytest.raises(RuntimeError, match="blocked"):
        await svc._fetch_url_text("https://jobs.example/start")
