from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from sprucer.adapters.auth import create_auth
from sprucer.adapters.llm import MockLlm, OpenAICompatLlm
from sprucer.adapters.oidc import OidcClient, new_state, sign_session, verify_session
from sprucer.adapters.storage import create_storage
from sprucer.api.app import build_app
from sprucer.service import CareerService
from sprucer.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


def _settings(tmp_path: Path, **kwargs) -> Settings:
    base = dict(
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        auth_mode="dev",
        dev_password="test-pass",
        session_secret="test-secret-not-default-value",
        llm_url="http://example.invalid/v1",
        llm_api_key="test",
        llm_model="mock",
        cors_origins="http://test",
        host="127.0.0.1",
        docs_enabled=True,
    )
    base.update(kwargs)
    return Settings(**base)


def _app_client(tmp_path: Path, *, auth_mode: str = "dev", api_keys: set[str] | None = None, **kw):
    if api_keys is not None and "api_keys" not in kw:
        kw["api_keys"] = ",".join(sorted(api_keys))
    settings = _settings(tmp_path, auth_mode=auth_mode, **kw)
    store = create_storage(settings.database_url)
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth)
    llm = MockLlm()
    service = CareerService(store, llm)
    auth = create_auth(
        mode=auth_mode,
        dev_password=settings.dev_password,
        session_secret=settings.session_secret,
        api_keys=api_keys if api_keys is not None else settings.api_key_set(),
        oidc_issuer=settings.oidc_issuer,
        oidc_client_id=settings.oidc_client_id,
        oidc_client_secret=settings.oidc_client_secret,
        oidc_redirect_uri=settings.oidc_redirect_uri,
        cookie_secure=settings.cookie_secure,
    )
    app = build_app(settings=settings, service=service, auth=auth)
    return TestClient(app), llm, store, settings


def test_none_auth_open(tmp_path: Path):
    client, _, _, _ = _app_client(tmp_path, auth_mode="none")
    with client:
        assert client.get("/v1/truth").status_code == 200
        assert client.get("/v1/auth/config").json()["mode"] == "none"


def test_api_key_auth(tmp_path: Path):
    client, _, _, _ = _app_client(tmp_path, auth_mode="api_key", api_keys={"k-test"})
    with client:
        assert client.get("/v1/truth").status_code == 401
        ok = client.get("/v1/truth", headers={"Authorization": "Bearer k-test"})
        assert ok.status_code == 200
        bad_login = client.post("/v1/auth/login", json={"api_key": "nope"})
        assert bad_login.status_code == 401
        good_login = client.post("/v1/auth/login", json={"api_key": "k-test"})
        assert good_login.status_code == 200


def test_dev_rejects_raw_password_bearer(tmp_path: Path):
    client, _, _, _ = _app_client(tmp_path)
    with client:
        assert (
            client.get("/v1/truth", headers={"Authorization": "Bearer test-pass"}).status_code
            == 401
        )
        login = client.post("/v1/auth/login", json={"password": "test-pass"})
        assert login.status_code == 200
        who = client.get("/v1/auth/whoami")
        assert who.json()["subject"] == "dev"
        assert client.post("/v1/auth/logout").status_code == 200


def test_applications_crud_and_upload_ingest(tmp_path: Path):
    client, _, _, _ = _app_client(tmp_path)
    with client:
        client.post("/v1/auth/login", json={"password": "test-pass"})
        up = client.post(
            "/v1/applications",
            json={"id": "app-1", "company": "Acme", "title": "Eng", "status": "draft"},
        )
        assert up.status_code == 200
        listed = client.get("/v1/applications")
        assert any(i["id"] == "app-1" for i in listed.json()["items"])
        got = client.get("/v1/applications/app-1")
        assert got.status_code == 200
        assert client.get("/v1/applications/missing").status_code == 404

        raw = base64.b64encode(b"<html><body>Company: Beta\nTitle: Dev</body></html>").decode()
        ingest = client.post(
            "/v1/jd/ingest",
            json={"source_type": "upload", "filename": "jd.html", "content_base64": raw},
        )
        assert ingest.status_code == 200

        assert (
            client.post("/v1/applications/app-1/delete", json={"confirm": False}).status_code == 400
        )
        assert (
            client.post("/v1/applications/app-1/delete", json={"confirm": True}).status_code == 200
        )


def test_truth_update_remove_and_generation_delete(tmp_path: Path):
    client, llm, _, _ = _app_client(tmp_path)
    with client:
        client.post("/v1/auth/login", json={"password": "test-pass"})
        add = client.patch(
            "/v1/truth",
            json={"op": "add", "section": "metrics", "item": {"text": "Covered metric"}},
        )
        assert add.status_code == 200
        mid = add.json()["truth"]["metrics"][-1]["id"]
        upd = client.patch(
            "/v1/truth",
            json={
                "op": "update",
                "section": "metrics",
                "item_id": mid,
                "item": {"text": "Updated metric"},
            },
        )
        assert upd.status_code == 200
        nc = client.patch(
            "/v1/truth",
            json={"op": "add", "section": "neverClaim", "item": "Do not invent X"},
        )
        assert nc.status_code == 200
        rem = client.patch(
            "/v1/truth",
            json={"op": "remove", "section": "metrics", "item_id": mid, "confirm": True},
        )
        assert rem.status_code == 200

        jd = (FIXTURES / "sample-jd.txt").read_text(encoding="utf-8")
        app_id = client.post("/v1/jd/ingest", json={"source_type": "paste", "text": jd}).json()[
            "application"
        ]["id"]
        gen = client.post(
            "/v1/generate", json={"application_id": app_id, "types": ["cover"]}
        ).json()
        gid = gen["generation"]["id"]
        assert (
            client.post(
                "/v1/generations/delete",
                json={"application_id": app_id, "generation_id": gid, "confirm": True},
            ).status_code
            == 200
        )
        assert llm.calls


@pytest.mark.asyncio
async def test_url_ingest_ssrf_and_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client, _, _, _ = _app_client(tmp_path)

    class FakeResponse:
        def __init__(
            self,
            status_code=200,
            text="Company: Gamma\nRole: SRE",
            headers=None,
            url="https://jobs.example/1",
        ):
            self.status_code = status_code
            self.text = text
            self.headers = headers or {"content-type": "text/plain"}
            self.url = url

        @property
        def is_redirect(self):
            return self.status_code in {301, 302, 303, 307, 308}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return FakeResponse(url=url)

    def fake_getaddrinfo(host, port, *a, **k):
        if host in {"jobs.example", "example.com"}:
            return [(None, None, None, None, ("93.184.216.34", port))]
        return [(None, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", fake_getaddrinfo)

    with client:
        client.post("/v1/auth/login", json={"password": "test-pass"})
        bad = client.post("/v1/jd/ingest", json={"source_type": "url", "url": "http://127.0.0.1/"})
        assert bad.status_code == 400
        ok = client.post(
            "/v1/jd/ingest", json={"source_type": "url", "url": "https://jobs.example/1"}
        )
        assert ok.status_code == 200, ok.text


def test_oidc_session_expiry_and_state():
    tok = sign_session("sec", "user", ttl_seconds=-5)
    assert verify_session("sec", tok) is None
    assert verify_session("sec", "garbage") is None
    assert verify_session("sec", "oidc:bad") is None
    good = sign_session("sec", "user-1", ttl_seconds=60)
    assert verify_session("sec", good) == "user-1"
    assert len(new_state()) > 10


@pytest.mark.asyncio
async def test_oidc_client_discovery_and_auth_url():
    client = OidcClient(
        issuer="https://idp.example",
        client_id="cid",
        client_secret="secret",
        redirect_uri="http://127.0.0.1:3737/v1/auth/oidc/callback",
    )

    class AC:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            if "openid-configuration" in url:

                class R:
                    status_code = 200

                    def json(self_inner):
                        return {
                            "authorization_endpoint": "https://idp.example/authorize",
                            "token_endpoint": "https://idp.example/token",
                            "userinfo_endpoint": "https://idp.example/userinfo",
                        }

                return R()

            class UI:
                status_code = 200

                def json(self_inner):
                    return {"sub": "oidc-user"}

            return UI()

        async def post(self, url, data=None):
            class R:
                status_code = 200

                def json(self_inner):
                    return {"access_token": "at", "id_token": "x.e30.x"}

            return R()

    old = httpx.AsyncClient
    httpx.AsyncClient = AC  # type: ignore
    try:
        url = await client.authorization_url(state="abc")
        assert "authorize" in url and "state=abc" in url
        tokens = await client.exchange_code("code")
        assert tokens["sub"] == "oidc-user"
    finally:
        httpx.AsyncClient = old


@pytest.mark.asyncio
async def test_openai_compat_llm_errors():
    llm = OpenAICompatLlm(base_url="", api_key="k", default_model="m")
    with pytest.raises(RuntimeError, match="LLM_URL"):
        await llm.chat([{"role": "user", "content": "hi"}])
    llm = OpenAICompatLlm(base_url="http://x", api_key="", default_model="m")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        await llm.chat([{"role": "user", "content": "hi"}])


def test_oidc_start_requires_mode(tmp_path: Path):
    client, _, _, _ = _app_client(tmp_path, auth_mode="dev")
    with client:
        assert client.get("/v1/auth/oidc/start", follow_redirects=False).status_code == 400


def test_create_auth_oidc_and_api_key_errors():
    with pytest.raises(RuntimeError):
        create_auth(mode="api_key", dev_password="x", session_secret="y", api_keys=set())
    auth = create_auth(
        mode="oidc",
        dev_password="x",
        session_secret="y" * 8,
        api_keys=set(),
        oidc_issuer="https://idp.example",
        oidc_client_id="cid",
        oidc_client_secret="sec",
    )
    assert auth.mode == "oidc"
    assert auth.public_config()["oidc_login"] is True
