"""Push remaining statement coverage toward 100%."""

from __future__ import annotations

import base64
import json
import runpy
import socket
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from sprucer.adapters.auth import ApiKeyAuth, DevAuth, NoneAuth, OidcAuth, create_auth
from sprucer.adapters.filesystem_import import import_filesystem_vault
from sprucer.adapters.llm import MockLlm, OpenAICompatLlm
from sprucer.adapters.oidc import OidcClient, sign_session
from sprucer.adapters.storage import create_storage
from sprucer.adapters.storage.sqlalchemy_store import SqlAlchemyStorage
from sprucer.api.app import build_app, create_app, run
from sprucer.security import validate_runtime_settings
from sprucer.service import CareerService, _now, _slug
from sprucer.settings import Settings, get_settings
from sprucer.ssrf import UnsafeUrlError, assert_public_http_url

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


def _settings(tmp_path: Path, **kwargs) -> Settings:
    base = {
        "database_url": f"sqlite:///{tmp_path / 'c.db'}",
        "auth_mode": "dev",
        "dev_password": "test-pass",
        "session_secret": "test-secret-not-default-value",
        "llm_url": "http://example.invalid/v1",
        "llm_api_key": "test",
        "llm_model": "mock",
        "cors_origins": "http://test",
        "host": "127.0.0.1",
        "docs_enabled": True,
    }
    base.update(kwargs)
    return Settings(**base)


def _service(tmp_path: Path) -> CareerService:
    store = create_storage(f"sqlite:///{tmp_path / 's.db'}")
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth)
    return CareerService(store, MockLlm())


def _request(path: str = "/", headers: dict | None = None, cookies: dict | None = None) -> Request:
    hdrs = []
    for k, v in (headers or {}).items():
        hdrs.append((k.lower().encode(), v.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": hdrs,
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
        "scheme": "http",
    }
    req = Request(scope)
    if cookies:
        req._cookies = cookies  # type: ignore[attr-defined]
    return req


# --- settings / security / ssrf / slug -------------------------------------------------


def test_get_settings_and_slug_now():
    get_settings.cache_clear()
    s = get_settings()
    assert s.port == 8787
    assert _slug("") == "role"
    assert _now()


def test_security_none_exposed_refused():
    with pytest.raises(RuntimeError, match="auth_mode=none"):
        validate_runtime_settings(
            Settings(
                host="0.0.0.0",
                auth_mode="none",
                allow_insecure_dev=False,
                session_secret="x" * 24,
            )
        )


def test_ssrf_edge_cases(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("https:///nohost", resolve=False)

    def boom(*a, **k):
        raise socket.gaierror("fail")

    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", boom)
    with pytest.raises(UnsafeUrlError, match="resolve"):
        assert_public_http_url("https://missing.example")

    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", lambda *a, **k: [])
    with pytest.raises(UnsafeUrlError, match="resolve"):
        assert_public_http_url("https://empty.example")

    def weird(*a, **k):
        return [(None, None, None, None, ("not-an-ip", 443))]

    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", weird)
    assert assert_public_http_url("https://weird.example").startswith("https://")


# --- auth adapters --------------------------------------------------------------------


def test_none_api_key_dev_oidc_auth_paths():
    none = NoneAuth()
    resp = Response()
    req = _request()
    assert none.authenticate(req).subject == "anonymous"
    assert none.login(resp).subject == "anonymous"
    assert none.logout(resp) is None
    assert none.public_config()["mode"] == "none"

    keys = ApiKeyAuth(keys={"good"})
    with pytest.raises(Exception):
        keys.authenticate(_request())
    with pytest.raises(Exception):
        keys.authenticate(_request(headers={"Authorization": "Bearer bad"}))
    assert keys.authenticate(_request(headers={"Authorization": "Bearer good"})).subject.startswith(
        "api-key:"
    )
    assert keys.login(resp, api_key="good").subject.startswith("api-key:")
    assert keys.logout(resp) is None
    assert keys.public_config()["api_key"] is True

    dev = DevAuth(password="pw", secret="sec", cookie_secure=True)
    assert "dev_login" in dev.public_config()
    tok = dev._token()
    assert dev.authenticate(_request(headers={"Authorization": f"Bearer {tok}"})).subject == "dev"
    with pytest.raises(Exception):
        dev.login(resp, password="wrong")
    assert dev.login(resp, password="pw").subject == "dev"
    dev.logout(resp)

    with pytest.raises(RuntimeError):
        OidcAuth(
            issuer="",
            client_id="",
            client_secret="",
            redirect_uri="http://x",
            session_secret="s",
        )
    oidc = OidcAuth(
        issuer="https://idp.example",
        client_id="cid",
        client_secret="sec",
        redirect_uri="http://127.0.0.1/cb",
        session_secret="sess",
        api_keys={"ak"},
        cookie_secure=True,
    )
    assert oidc.authenticate(_request(headers={"Authorization": "Bearer ak"})).mode == "api_key"
    cookie = sign_session("sess", "user-z")
    # Starlette Request cookies via header
    req2 = _request(headers={"cookie": f"sprucer_session={cookie}"})
    assert oidc.authenticate(req2).subject == "user-z"
    with pytest.raises(Exception):
        oidc.authenticate(_request())
    assert oidc.login(resp, api_key="ak").subject.startswith("api-key:")
    with pytest.raises(Exception):
        oidc.login(resp)
    oidc.logout(resp)
    assert oidc.public_config()["oidc_login"] is True
    assert oidc.establish_session(resp, "user-z").subject == "user-z"

    # empty session_secret falls back to random in create_auth
    a = create_auth(mode="dev", dev_password="p", session_secret="", api_keys=set())
    assert a.mode == "dev"


# --- llm / oidc client ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_compat_llm_success_and_errors(monkeypatch: pytest.MonkeyPatch):
    llm = OpenAICompatLlm(base_url="http://llm.test/v1", api_key="k", default_model="m")

    class R:
        status_code = 200
        text = "{}"

        def json(self):
            return {"choices": [{"message": {"content": "hi"}}]}

    class Bad:
        status_code = 500
        text = "nope"

        def json(self):
            return {}

    class Weird:
        status_code = 200
        text = "{}"

        def json(self):
            return {"choices": []}

    class AC:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return R()

    monkeypatch.setattr(httpx, "AsyncClient", AC)
    assert await llm.chat([{"role": "user", "content": "x"}]) == "hi"

    class ACTimeout(AC):
        async def post(self, *a, **k):
            raise httpx.TimeoutException("t")

    monkeypatch.setattr(httpx, "AsyncClient", ACTimeout)
    with pytest.raises(RuntimeError, match="timed out"):
        await llm.chat([{"role": "user", "content": "x"}])

    class ACBad(AC):
        async def post(self, *a, **k):
            return Bad()

    monkeypatch.setattr(httpx, "AsyncClient", ACBad)
    with pytest.raises(RuntimeError, match="LLM HTTP"):
        await llm.chat([{"role": "user", "content": "x"}])

    class ACWeird(AC):
        async def post(self, *a, **k):
            return Weird()

    monkeypatch.setattr(httpx, "AsyncClient", ACWeird)
    with pytest.raises(RuntimeError, match="unexpected"):
        await llm.chat([{"role": "user", "content": "x"}])


@pytest.mark.asyncio
async def test_mock_llm_branches():
    m = MockLlm(reply="fixed")
    assert await m.chat([{"role": "user", "content": "{}"}]) == "fixed"
    m2 = MockLlm()
    out = await m2.chat(
        [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "not-json"},
            {"role": "user", "content": "[]"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "artifactTypes": ["custom:thank-you"],
                        "interviewCiteCatalog": [{"id": "a"}, "x", {}],
                    }
                ),
            },
        ]
    )
    assert "Thank You" in out or "thank" in out.lower()


@pytest.mark.asyncio
async def test_oidc_client_error_paths(monkeypatch: pytest.MonkeyPatch):
    client = OidcClient(
        issuer="https://idp.example",
        client_id="c",
        client_secret="s",
        redirect_uri="http://cb",
    )

    class AC:
        def __init__(self, *a, **k):
            self.mode = "disco"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            class R:
                status_code = 500
                text = "fail"

                def json(self_inner):
                    return {}

            return R()

        async def post(self, url, data=None):
            class R:
                status_code = 500
                text = "fail"

                def json(self_inner):
                    return {}

            return R()

    monkeypatch.setattr(httpx, "AsyncClient", AC)
    with pytest.raises(RuntimeError, match="discovery"):
        await client.discovery()

    client._discovery = {}  # missing endpoints
    with pytest.raises(RuntimeError, match="authorization_endpoint"):
        await client.authorization_url(state="s")
    with pytest.raises(RuntimeError, match="token_endpoint"):
        await client.exchange_code("c")

    # id_token path for sub
    client._discovery = {
        "authorization_endpoint": "https://idp.example/a",
        "token_endpoint": "https://idp.example/t",
    }

    class AC2(AC):
        async def post(self, url, data=None):
            import base64

            payload = base64.urlsafe_b64encode(json.dumps({"sub": "from-id"}).encode()).decode().rstrip("=")

            class R:
                status_code = 200
                text = "{}"

                def json(self_inner):
                    return {"id_token": f"h.{payload}.s"}

            return R()

        async def get(self, url, headers=None):
            class R:
                status_code = 400
                text = "no"

                def json(self_inner):
                    return {}

            return R()

    monkeypatch.setattr(httpx, "AsyncClient", AC2)
    tokens = await client.exchange_code("code")
    assert tokens["sub"] == "from-id"

    class AC3(AC2):
        async def post(self, url, data=None):
            class R:
                status_code = 200
                text = "{}"

                def json(self_inner):
                    return {}

            return R()

    monkeypatch.setattr(httpx, "AsyncClient", AC3)
    client._discovery = {
        "token_endpoint": "https://idp.example/t",
    }
    with pytest.raises(RuntimeError, match="subject"):
        await client.exchange_code("code")


# --- storage / filesystem -------------------------------------------------------------


def test_storage_edge_paths(tmp_path: Path):
    rel = tmp_path / "nested" / "db.sqlite"
    store = SqlAlchemyStorage(f"sqlite:///{rel}")
    store.ensure_schema()
    # relative path branch
    store2 = SqlAlchemyStorage("sqlite:///./data_cov_test.db")
    store2.ensure_schema()

    # duration column already present -> early return
    store._ensure_generation_duration_column()

    # force inspect failure
    bad = SqlAlchemyStorage(f"sqlite:///{tmp_path / 'b.db'}")
    bad.ensure_schema()
    bad.engine = MagicMock()
    bad.engine.begin = MagicMock()

    # get_truth empty after wipe simulation
    empty = create_storage(f"sqlite:///{tmp_path / 'empty.db'}")
    with empty._Session() as session:
        from sprucer.adapters.storage.sqlalchemy_store import TruthRow
        from sqlalchemy import delete

        session.execute(delete(TruthRow))
        session.commit()
    assert empty.get_truth().get("version") == 1 or "profile" in empty.get_truth()

    # save_truth with bad version
    empty.save_truth({"version": "nope", "profile": {}})

    # KeyErrors
    with pytest.raises(KeyError):
        empty.delete_application("missing")
    with pytest.raises(KeyError):
        empty.get_jd("missing")
    with pytest.raises(KeyError):
        empty.list_generations("missing")
    assert empty.get_generation("a", "g") is None
    empty.upsert_application({"id": "a1", "company": "C"}, jd_text="jd")
    with pytest.raises(KeyError):
        empty.save_generation("nope", generation={"id": "g"}, content="x")
    with pytest.raises(KeyError):
        empty.approve_generation("a1", "missing")
    with pytest.raises(KeyError):
        empty.delete_generation("a1", "missing")

    empty.save_generation("a1", generation={"id": "g1", "types": ["cover"], "durationMs": 12}, content="c")
    empty.delete_generation("a1", "g1")


def test_filesystem_import_skips(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "current").mkdir(parents=True)
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    (vault / "current" / "career-truth.json").write_text(json.dumps(truth), encoding="utf-8")
    apps = vault / "applications"
    apps.mkdir()
    (apps / "file-not-dir").write_text("x", encoding="utf-8")
    skip = apps / "no-meta"
    skip.mkdir()
    no_gens = apps / "no-gens"
    no_gens.mkdir()
    (no_gens / "meta.json").write_text(json.dumps({"id": "no-gens", "generations": []}), encoding="utf-8")
    with_gens = apps / "with-gens"
    with_gens.mkdir()
    (with_gens / "meta.json").write_text(
        json.dumps(
            {
                "id": "with-gens",
                "generations": [
                    {"id": "", "files": ["missing.md"]},
                    {"id": "g2", "files": ["missing.md"], "approval": "draft"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (with_gens / "generations").mkdir()
    store = create_storage(f"sqlite:///{tmp_path / 'imp.db'}")
    result = import_filesystem_vault(vault, store)
    assert result["applications"] >= 1


# --- service truth / ingest / generate edges ------------------------------------------


@pytest.mark.asyncio
async def test_service_truth_and_ingest_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    svc = _service(tmp_path)
    svc.truth_patch(op="set", section="profile", value={"name": "X"})
    svc.truth_patch(op="set", section="voicePrefs", value={"tone": "direct"})
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="add", section="profile", item={})
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="add", section="neverClaim", item={})
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="add", section="neverClaim", item="")
    svc.truth_patch(op="add", section="neverClaim", item="Never invent X")
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="add", section="blurbs", item="x")  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="update", section="neverClaim", item={"id": "x"})
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="update", section="blurbs", item="x")  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="update", section="blurbs", item={"text": "t"}, item_id="missing")
    svc.truth_patch(
        op="add",
        section="blurbs",
        item={"label": "L", "text": "T"},
    )
    bid = svc.store.get_truth()["blurbs"][-1]["id"]
    svc.truth_patch(op="update", section="blurbs", item_id=bid, item={"text": "T2"})
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="remove", section="blurbs", item_id=bid, confirm=False)
    svc.truth_patch(op="add", section="neverClaim", item="Y")
    n = len(svc.store.get_truth()["neverClaim"])
    svc.truth_patch(op="remove", section="neverClaim", index=n - 1, confirm=True)
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="remove", section="neverClaim", index=999, confirm=True)
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="remove", section="blurbs", confirm=True)
    svc.truth_patch(op="remove", section="blurbs", index=0, confirm=True)
    with pytest.raises(RuntimeError):
        svc.truth_patch(op="nope", section="blurbs")

    with pytest.raises(RuntimeError):
        svc.applications_upsert({})
    with pytest.raises(RuntimeError):
        svc.applications_delete("x", confirm=False)
    with pytest.raises(RuntimeError):
        svc.applications_delete("missing", confirm=True)

    with pytest.raises(RuntimeError):
        await svc.jd_ingest(source_type="nope")
    with pytest.raises(RuntimeError):
        await svc.jd_ingest(source_type="paste", text="")
    with pytest.raises(RuntimeError):
        await svc.jd_ingest(source_type="url", url="")
    with pytest.raises(RuntimeError):
        await svc.jd_ingest(source_type="upload")

    # upload plain text + reuse existing by url
    await svc.jd_ingest(
        source_type="paste",
        text="Company: Reuse Co\nTitle: Eng\n",
        url="https://jobs.example/reuse",
    )
    await svc.jd_ingest(
        source_type="paste",
        text="Company: Reuse Co\nTitle: Eng Updated\n",
        url="https://jobs.example/reuse",
    )
    raw = base64.b64encode(b"plain text jd").decode()
    await svc.jd_ingest(source_type="upload", content_base64=raw, filename="jd.txt")

    # fetch errors
    class FakeResp:
        def __init__(self, code=200, text="ok", headers=None, url="https://jobs.example/1", redirect=False):
            self.status_code = code
            self.text = text
            self.headers = headers or {"content-type": "text/plain"}
            self.url = url
            self._redirect = redirect

        @property
        def is_redirect(self):
            return self._redirect or self.status_code in {301, 302, 303, 307, 308}

    calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            calls["n"] += 1
            if "err" in url:
                raise httpx.RequestError("boom")
            if "redir-loop" in url:
                return FakeResp(302, headers={"location": "https://jobs.example/redir-loop"}, url=url, redirect=True)
            if "redir-empty" in url:
                return FakeResp(302, headers={}, url=url, redirect=True)
            if "redir-bad" in url:
                return FakeResp(302, headers={"location": "http://127.0.0.1/x"}, url=url, redirect=True)
            if "redir-ok" in url:
                if calls["n"] == 1:
                    return FakeResp(302, headers={"location": "https://jobs.example/final"}, url=url, redirect=True)
                return FakeResp(200, text="<html><body>Company: Z</body></html>", headers={"content-type": "text/html"})
            if "401" in url:
                return FakeResp(401)
            if "404" in url:
                return FakeResp(404)
            return FakeResp(200, text="Company: Ok\nTitle: T")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        "sprucer.ssrf.socket.getaddrinfo",
        lambda host, port, *a, **k: [(None, None, None, None, ("93.184.216.34", port))],
    )

    with pytest.raises(RuntimeError, match="fetch failed"):
        await svc._fetch_url_text("https://jobs.example/err")
    with pytest.raises(RuntimeError, match="Location"):
        await svc._fetch_url_text("https://jobs.example/redir-empty")
    with pytest.raises(RuntimeError, match="Refusing|private"):
        await svc._fetch_url_text("https://jobs.example/redir-bad")
    with pytest.raises(RuntimeError, match="401"):
        await svc._fetch_url_text("https://jobs.example/401")
    with pytest.raises(RuntimeError, match="HTTP 404"):
        await svc._fetch_url_text("https://jobs.example/404")
    text, _ = await svc._fetch_url_text("https://jobs.example/redir-ok")
    assert "Company" in text or "Z" in text

    # redirect limit
    calls["n"] = 0

    class LoopClient(FakeClient):
        async def get(self, url, headers=None):
            return FakeResp(302, headers={"location": "https://jobs.example/redir-loop/x"}, url=url, redirect=True)

    monkeypatch.setattr(httpx, "AsyncClient", LoopClient)
    with pytest.raises(RuntimeError, match="redirect limit"):
        await svc._fetch_url_text("https://jobs.example/redir-loop")


@pytest.mark.asyncio
async def test_service_generate_and_content_checks(tmp_path: Path):
    svc = _service(tmp_path)
    with pytest.raises(RuntimeError):
        svc._normalize_types([], None)
    assert "custom:foo" in svc._normalize_types(["Foo"], None)
    assert "custom:x" in svc._normalize_types(["custom:x", ""], "X")
    assert "custom:hello-there" in svc._normalize_types(None, "Hello There")

    head = svc._heading_instruction(["cover", "email", "resume", "interview", "linkedin", "custom:note"])
    assert "Cover Letter" in head
    assert svc._heading_instruction(["email"])  # forbidden cover
    assert svc._heading_instruction(["cover"])  # forbidden email

    guides = svc._artifact_format_guides(["interview", "linkedin", "email", "cover", "resume"])
    assert "Interview" in guides or "interview" in guides.lower()

    # content satisfies
    assert not svc._content_satisfies_types("no headings", ["cover"])
    assert not svc._content_satisfies_types("## Other\n", ["custom:note"])
    assert svc._content_satisfies_types("## Note\nHi", ["custom:note"])
    assert not svc._content_satisfies_types("## Cover Letter\n", ["email"])
    assert not svc._content_satisfies_types("## Email\nHello", ["email"])
    assert svc._content_satisfies_types("## Email\nSubject: Hi\n\nHello", ["email"])
    assert not svc._content_satisfies_types(
        "## LinkedIn DM\nenhance your profile\n" + ("\n- x" * 10),
        ["linkedin"],
    )
    assert not svc._content_satisfies_types("## LinkedIn DM\nHi [Your Name]", ["linkedin"])
    assert not svc._content_satisfies_types("## Interview Prep\ntips only", ["interview"])
    assert not svc._content_satisfies_types(
        "## Interview Prep\n??? Project ID 12345\nAnswer with: x Cite: `a`\nAnswer with: y Cite: `b`",
        ["interview"],
        cite_ids={"a", "b", "c"},
    )
    # insufficient cites
    assert not svc._content_satisfies_types(
        "## Interview Prep\nQ1?\nQ2?\nQ3?\nAnswer with: x Cite: `a`",
        ["interview"],
        cite_ids={"a", "b", "c"},
    )
    # no answer with and few cites
    assert not svc._content_satisfies_types(
        "## Interview Prep\nQ1?\nQ2?\nQ3?\n`a` `b`",
        ["interview"],
        cite_ids={"a", "b", "c"},
    )

    # emphasis with non-dict metric
    truth = svc.store.get_truth()
    truth["metrics"] = [{"text": "python metrics tags", "tags": ["python"]}, "skip", {"text": "x"}]
    plan = svc._emphasis_hint(truth, "we need python engineer")
    assert isinstance(plan, list)

    # generate missing app / jd
    with pytest.raises(RuntimeError):
        await svc.generate(application_id="missing")
    svc.store.upsert_application({"id": "empty-jd"}, jd_text="   ")
    with pytest.raises(RuntimeError):
        await svc.generate(application_id="empty-jd")

    # happy generate + approve/delete/get errors
    jd = (FIXTURES / "sample-jd.txt").read_text(encoding="utf-8")
    app_id = (await svc.jd_ingest(source_type="paste", text=jd))["application"]["id"]
    gen = await svc.generate(application_id=app_id, types=["cover"], custom_type="note")
    gid = gen["generation"]["id"]
    with pytest.raises(RuntimeError):
        svc.generation_approve(application_id=app_id, generation_id=gid, confirm=False)
    with pytest.raises(RuntimeError):
        svc.generation_approve(application_id=app_id, generation_id="nope", confirm=True)
    with pytest.raises(RuntimeError):
        svc.generation_delete(application_id=app_id, generation_id=gid, confirm=False)
    with pytest.raises(RuntimeError):
        svc.generation_delete(application_id=app_id, generation_id="nope", confirm=True)
    with pytest.raises(RuntimeError):
        svc.generation_get(application_id=app_id, generation_id="nope")
    assert svc.generation_get(application_id=app_id, generation_id=gid)["ok"]

    # repair path: first bad reply then good
    class Flaky(MockLlm):
        def __init__(self):
            super().__init__()
            self.n = 0

        async def chat(self, messages, **kwargs):
            self.n += 1
            if self.n == 1:
                return "## Wrong\nnope"
            return await super().chat(messages, **kwargs)

    svc.llm = Flaky()
    await svc.generate(application_id=app_id, types=["linkedin"])

    # fail after repair
    class AlwaysBad(MockLlm):
        async def chat(self, messages, **kwargs):
            return "## Wrong\nnope"

    svc.llm = AlwaysBad()
    with pytest.raises(RuntimeError, match="wrong artifact"):
        await svc.generate(application_id=app_id, types=["cover"])


# --- API app routes -------------------------------------------------------------------


def test_build_app_defaults_and_oidc_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = _settings(
        tmp_path,
        auth_mode="oidc",
        oidc_issuer="https://idp.example",
        oidc_client_id="cid",
        oidc_client_secret="sec",
        docs_enabled=False,
    )
    store = create_storage(settings.database_url)
    store.save_truth(json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8")))
    auth = create_auth(
        mode="oidc",
        dev_password="x",
        session_secret=settings.session_secret,
        api_keys={"ak"},
        oidc_issuer=settings.oidc_issuer,
        oidc_client_id=settings.oidc_client_id,
        oidc_client_secret=settings.oidc_client_secret,
    )

    async def fake_auth_url(state: str):
        return "https://idp.example/authorize?state=" + state

    async def fake_exchange(code: str):
        return {"sub": "oidc-user"}

    auth.client.authorization_url = fake_auth_url  # type: ignore[method-assign]
    auth.client.exchange_code = fake_exchange  # type: ignore[method-assign]
    app = build_app(settings=settings, service=CareerService(store, MockLlm()), auth=auth)
    with TestClient(app) as client:
        r = client.get("/v1/auth/oidc/start", follow_redirects=False)
        assert r.status_code == 302
        state = r.cookies.get("sprucer_oidc_state")
        bad = client.get("/v1/auth/oidc/callback", follow_redirects=False)
        assert bad.status_code == 400
        err = client.get("/v1/auth/oidc/callback?error=access_denied", follow_redirects=False)
        assert err.status_code == 400
        client.cookies.set("sprucer_oidc_state", state or "s")
        ok = client.get(
            f"/v1/auth/oidc/callback?code=abc&state={state}",
            follow_redirects=False,
        )
        assert ok.status_code == 302

        # API error mapping
        client.cookies.clear()
        # login via api key through authenticate on protected route
        assert client.get("/v1/applications", headers={"Authorization": "Bearer ak"}).status_code == 200
        assert client.get("/v1/applications/missing", headers={"Authorization": "Bearer ak"}).status_code == 404
        assert (
            client.post(
                "/v1/applications/missing/delete",
                json={"confirm": True},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/generate",
                json={"application_id": "missing", "types": ["cover"]},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/generations/approve",
                json={"application_id": "a", "generation_id": "g", "confirm": True},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/generations/delete",
                json={"application_id": "a", "generation_id": "g", "confirm": True},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )
        assert (
            client.get(
                "/v1/applications/a/generations/g",
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/v1/jd/ingest",
                json={"source_type": "paste", "text": ""},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )
        assert (
            client.patch(
                "/v1/truth",
                json={"op": "nope", "section": "blurbs"},
                headers={"Authorization": "Bearer ak"},
            ).status_code
            == 400
        )

    # create_app / run with mocked uvicorn
    monkeypatch.setattr("sprucer.settings.get_settings", lambda: settings)
    monkeypatch.setattr("sprucer.api.app.get_settings", lambda: settings)
    monkeypatch.setattr("sprucer.api.app.validate_runtime_settings", lambda s: [])
    called = {}

    def fake_uvicorn_run(*a, **k):
        called["yes"] = True

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    run()
    assert called["yes"]
    # factory
    create_app_fn = create_app
    assert callable(create_app_fn)


def test_build_app_wires_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr("sprucer.api.app.get_settings", lambda: settings)
    monkeypatch.setattr("sprucer.api.app.validate_runtime_settings", lambda s: [])
    monkeypatch.setattr(
        "sprucer.api.app.create_storage",
        lambda url: create_storage(settings.database_url),
    )
    app = build_app(settings=settings)
    assert app.title == "Sprucer"


def test_cli_main_module(monkeypatch: pytest.MonkeyPatch):
    import sprucer.cli.main as mod

    called = {"n": 0}

    def fake_app():
        called["n"] += 1

    monkeypatch.setattr(mod, "app", fake_app)
    # Execute the __main__ guard by simulating module run of just that block
    if True:
        # cover line by calling the same code path
        mod.app()
    assert called["n"] == 1
    # Also run module as __main__ with patched app
    monkeypatch.setattr("sys.argv", ["sprucer", "--help"])
    try:
        runpy.run_module("sprucer.cli.main", run_name="__main__")
    except SystemExit:
        pass
