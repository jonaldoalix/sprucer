"""Tests for demo mode (offline DemoLlm, per-session vaults, cleanup) and BYO-key proxy."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sprucer.adapters.llm import DemoLlm, MockLlm, make_byok_llm, probe_byok_llm
from sprucer.adapters.storage import create_storage
from sprucer.adapters.storage.sqlalchemy_store import ApplicationRow, TruthRow
from sprucer.api.app import build_app
from sprucer.demo import seed_demo_vault
from sprucer.security import validate_runtime_settings
from sprucer.service import CareerService
from sprucer.settings import Settings


# --------------------------------------------------------------------------
# Settings / security
# --------------------------------------------------------------------------


def test_byok_allowed_host_set():
    s = Settings(byok_allowed_hosts="api.openai.com, OpenRouter.ai ,")
    assert s.byok_allowed_host_set() == {"api.openai.com", "openrouter.ai"}


def test_demo_mode_emits_warning():
    msgs = validate_runtime_settings(Settings(auth_mode="demo", host="127.0.0.1"))
    assert any("auth_mode=demo" in m for m in msgs)


# --------------------------------------------------------------------------
# Store TTL purge
# --------------------------------------------------------------------------


def test_purge_owner_prefix(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'purge.db'}")
    for owner in ("demo-old", "demo-new"):
        seed_demo_vault(store, owner)
    seed_demo_vault(store, "alice")  # non-demo prefix, must survive

    with store._Session() as s:
        stale = datetime.now(tz=timezone.utc) - timedelta(hours=48)
        for row in s.scalars(select(TruthRow).where(TruthRow.owner_subject == "demo-old")).all():
            row.updated_at = stale
        for row in s.scalars(
            select(ApplicationRow).where(ApplicationRow.owner_subject == "demo-old")
        ).all():
            row.updated_at = stale
        s.commit()

    assert store.purge_owner_prefix("", datetime.now(tz=timezone.utc)) == 0
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    assert store.purge_owner_prefix("demo-", cutoff) == 1

    assert not store.get_truth("demo-old").get("profile")  # truth purged -> empty default
    assert not store.list_applications("demo-old")
    assert store.list_applications("demo-new")  # fresh survives
    assert store.list_applications("alice")  # different prefix survives


# --------------------------------------------------------------------------
# DemoLlm (offline generator)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_llm_via_service_all_types(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'demo.db'}")
    app_id = seed_demo_vault(store, "shared")
    svc = CareerService(store, DemoLlm())
    res = await svc.generate(
        application_id=app_id,
        types=["cover", "email", "resume", "interview", "linkedin"],
        owner="shared",
    )
    body = res["generation"]["content"] if "content" in res["generation"] else res["preview"]
    assert res["ok"] is True
    # Custom type also works.
    res2 = await svc.generate(
        application_id=app_id, types=["cover"], custom_type="Recruiter Note", owner="shared"
    )
    assert res2["ok"] is True
    assert "recruiter note" in res2["preview"].lower() or "Recruiter Note" in body


@pytest.mark.asyncio
async def test_demo_llm_direct_edges():
    # Empty / non-JSON payload -> defaults + fallbacks.
    out = await DemoLlm().chat([{"role": "user", "content": "not json"}])
    assert "## Cover Letter" in out and "## Email" in out

    payload = {
        "artifactTypes": ["interview", "custom:cool-thing"],
        "application": {},
        "careerTruth": {"profile": {"name": "Sam Lee"}},
        "interviewCiteCatalog": [{"id": "m1"}],
    }
    out2 = await DemoLlm().chat([{"role": "user", "content": json.dumps(payload)}])
    assert "## Interview Prep" in out2
    assert "## Cool Thing" in out2
    assert "`m1`" in out2  # real id used
    assert "`demo-cite-2`" in out2  # padding for a thin catalog


@pytest.mark.asyncio
async def test_generate_llm_override(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'ov.db'}")
    app_id = seed_demo_vault(store, "shared")
    svc = CareerService(store, DemoLlm())
    override = MockLlm(reply="## Cover Letter\n\nGrounded override draft.\n")
    res = await svc.generate(
        application_id=app_id, types=["cover"], owner="shared", llm_override=override
    )
    assert res["ok"] is True
    assert override.calls  # the override was used, not self.llm


# --------------------------------------------------------------------------
# Service demo seed / cleanup / ingest gate
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_demo_seed_cleanup_and_ingest_gate(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'svc.db'}")
    svc = CareerService(store, DemoLlm(), ingest_url_enabled=False)

    app_id = svc.demo_seed("demo-abc")
    assert app_id and store.get_truth("demo-abc").get("profile")
    assert svc.demo_seed("demo-abc") is None  # already seeded

    assert svc.demo_cleanup(ttl_hours=24) == 0  # nothing stale yet

    with pytest.raises(RuntimeError, match="disabled"):
        await svc.jd_ingest(source_type="url", url="https://jobs.example/1", owner="demo-abc")


# --------------------------------------------------------------------------
# make_byok_llm
# --------------------------------------------------------------------------


def test_make_byok_llm_success_and_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", lambda u, resolve=True: u)

    llm = make_byok_llm(base_url="https://api.openai.com/v1", api_key="sk-x")
    assert llm.base_url == "https://api.openai.com/v1"

    assert make_byok_llm(
        base_url="https://api.openai.com/v1", api_key="sk", allowed_hosts={"api.openai.com"}
    )

    with pytest.raises(ValueError, match="required"):
        make_byok_llm(base_url="", api_key="k")
    with pytest.raises(ValueError, match="https"):
        make_byok_llm(base_url="http://api.openai.com/v1", api_key="k")
    with pytest.raises(ValueError, match="not allowed"):
        make_byok_llm(base_url="https://evil.com/v1", api_key="k", allowed_hosts={"api.openai.com"})


def test_make_byok_llm_ssrf_rejected(monkeypatch: pytest.MonkeyPatch):
    from sprucer.ssrf import UnsafeUrlError

    def boom(url, resolve=True):
        raise UnsafeUrlError("blocked private target")

    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", boom)
    with pytest.raises(ValueError, match="blocked private"):
        make_byok_llm(base_url="https://internal.local/v1", api_key="k")


@pytest.mark.asyncio
async def test_probe_byok_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", lambda u, resolve=True: u)

    class _ProbeLlm:
        base_url = "https://api.openai.com/v1"
        default_model = "gpt-4o-mini"

        async def chat(self, messages, **kwargs):
            assert kwargs.get("max_tokens") == 1
            return "ok"

    monkeypatch.setattr("sprucer.adapters.llm.make_byok_llm", lambda **kw: _ProbeLlm())
    out = await probe_byok_llm(base_url="https://api.openai.com/v1", api_key="sk")
    assert out["host"] == "api.openai.com"
    assert out["model"] == "gpt-4o-mini"


def test_llm_probe_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    async def fake_probe(**kwargs):
        return {"host": "api.openai.com", "model": "gpt-4o-mini", "preview": "ok"}

    monkeypatch.setattr("sprucer.api.app.probe_byok_llm", fake_probe)
    with _demo_client(tmp_path) as c:
        # byok disabled path covered by flipping settings on a second client below
        ok = c.post(
            "/v1/llm/probe",
            json={"base_url": "https://api.openai.com/v1", "api_key": "sk-x"},
        )
        assert ok.status_code == 200
        assert ok.json()["host"] == "api.openai.com"

        async def boom(**kwargs):
            raise ValueError("bad key")

        monkeypatch.setattr("sprucer.api.app.probe_byok_llm", boom)
        bad = c.post(
            "/v1/llm/probe",
            json={"base_url": "https://api.openai.com/v1", "api_key": "nope"},
        )
        assert bad.status_code == 400

        async def runtime_boom(**kwargs):
            raise RuntimeError("LLM HTTP 401: unauthorized")

        monkeypatch.setattr("sprucer.api.app.probe_byok_llm", runtime_boom)
        unauth = c.post(
            "/v1/llm/probe",
            json={"base_url": "https://api.openai.com/v1", "api_key": "bad"},
        )
        assert unauth.status_code == 400
        assert "401" in unauth.json()["detail"]

    # Probe rejected when BYOK is off.
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'nob.db'}",
        auth_mode="demo",
        host="127.0.0.1",
        demo=True,
        byok_enabled=False,
        session_secret="demo-secret-not-default-value-xxxxx",
        cors_origins="http://test",
    )
    with TestClient(build_app(settings=settings)) as c:
        assert (
            c.post(
                "/v1/llm/probe",
                json={"base_url": "https://api.openai.com/v1", "api_key": "sk"},
            ).status_code
            == 400
        )


# --------------------------------------------------------------------------
# App wiring: /v1/config, demo login+seed, offline generate, BYO proxy
# --------------------------------------------------------------------------


def _demo_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        auth_mode="demo",
        host="127.0.0.1",
        demo=True,
        byok_enabled=True,
        ingest_url_enabled=False,
        session_secret="demo-secret-not-default-value-xxxxx",
        cors_origins="http://test",
    )
    return TestClient(build_app(settings=settings))


def test_demo_config_login_and_offline_generate(tmp_path: Path):
    with _demo_client(tmp_path) as c:
        cfg = c.get("/v1/config").json()
        assert cfg["demo"] is True and cfg["byok_enabled"] is True
        assert cfg["ingest_url_enabled"] is False

        assert c.get("/v1/applications").status_code == 401  # needs a demo session

        login = c.post("/v1/auth/login", json={})
        assert login.status_code == 200
        assert login.json()["subject"].startswith("demo-")

        who = c.get("/v1/auth/whoami").json()
        assert who["mode"] == "demo"

        apps = c.get("/v1/applications").json()["items"]
        assert any(a["title"] == "Senior Platform Engineer" for a in apps)
        app_id = apps[0]["id"]

        # Offline generate (no headers) uses DemoLlm — zero external calls.
        gen = c.post("/v1/generate", json={"application_id": app_id, "types": ["cover", "email"]})
        assert gen.status_code == 200, gen.text
        assert gen.json()["ok"] is True

        assert c.get("/v1/auth/config").json()["demo"] is True
        assert c.post("/v1/auth/logout").status_code == 200
        assert c.get("/v1/applications").status_code == 401  # session cleared


def test_demo_byok_invalid_and_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with _demo_client(tmp_path) as c:
        c.post("/v1/auth/login", json={})
        app_id = c.get("/v1/applications").json()["items"][0]["id"]

        # Invalid BYO base (http) -> 400 from make_byok_llm.
        bad = c.post(
            "/v1/generate",
            json={"application_id": app_id, "types": ["cover"]},
            headers={"X-LLM-Base-Url": "http://x/v1", "X-LLM-Api-Key": "k"},
        )
        assert bad.status_code == 400

        # Valid BYO path: stub the builder so no real provider is hit.
        monkeypatch.setattr(
            "sprucer.api.app.make_byok_llm",
            lambda **kw: MockLlm(reply="## Cover Letter\n\nFrom your own provider.\n"),
        )
        ok = c.post(
            "/v1/generate",
            json={"application_id": app_id, "types": ["cover"]},
            headers={"X-LLM-Base-Url": "https://api.openai.com/v1", "X-LLM-Api-Key": "sk-x"},
        )
        assert ok.status_code == 200, ok.text
        assert "own provider" in ok.json()["preview"]
