from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from sprucer.adapters.auth import ApiKeyAuth, DevAuth, NoneAuth, OidcAuth, create_auth
from sprucer.adapters.filesystem_import import import_filesystem_vault
from sprucer.adapters.llm import MockLlm, OpenAICompatLlm
from sprucer.adapters.oidc import OidcClient
from sprucer.adapters.storage import create_storage
from sprucer.adapters.storage.sqlalchemy_store import _iso
from sprucer.security import validate_runtime_settings
from sprucer.settings import Settings, get_settings
from sprucer.ssrf import UnsafeUrlError, assert_public_http_url


def request(headers: dict[str, str] | None = None, cookies: dict[str, str] | None = None) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw_headers.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({"type": "http", "headers": raw_headers})


def settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "host": "127.0.0.1",
        "auth_mode": "dev",
        "dev_password": "password",
        "session_secret": "not-default",
        "llm_api_key": "key",
    }
    values.update(overrides)
    return Settings(**values)


def test_auth_classes_all_paths():
    response = Response()
    none = NoneAuth()
    assert none.authenticate(request()).subject == "anonymous"
    assert none.login(response).mode == "none"
    assert none.logout(response) is None

    dev = DevAuth(password="p", secret="s", cookie_secure=True)
    with pytest.raises(HTTPException):
        dev.authenticate(request())
    with pytest.raises(HTTPException):
        dev.login(Response(), password="wrong")
    token = dev._token()
    assert dev.authenticate(request({"authorization": f"Bearer {token}"})).subject == "dev"
    assert dev.authenticate(request(cookies={dev.cookie_name: token})).subject == "dev"
    assert dev.login(response, password="p").subject == "dev"
    dev.logout(response)
    assert dev.public_config()["dev_login"]

    keys = ApiKeyAuth(keys={"a"})
    for headers in ({}, {"Authorization": "Bearer bad"}):
        with pytest.raises(HTTPException):
            keys.authenticate(request(headers))
    assert keys.authenticate(request({"Authorization": "Bearer a"})).subject == "api-key"
    with pytest.raises(HTTPException):
        keys.login(Response(), api_key="bad")
    assert keys.login(Response(), api_key="a").subject == "api-key"
    assert keys.logout(Response()) is None
    assert keys.public_config()["api_key"]

    with pytest.raises(RuntimeError):
        OidcAuth(issuer="", client_id="", client_secret="", redirect_uri="", session_secret="s")
    oidc = OidcAuth(
        issuer="https://issuer", client_id="id", client_secret="secret", redirect_uri="http://cb",
        session_secret="session", api_keys={"a"}, cookie_secure=True,
    )
    assert oidc.authenticate(request({"Authorization": "Bearer a"})).mode == "api_key"
    with pytest.raises(HTTPException):
        oidc.authenticate(request())
    with pytest.raises(HTTPException):
        oidc.login(Response())
    assert oidc.login(Response(), api_key="a").subject == "api-key"
    assert oidc.establish_session(response, "person").subject == "person"
    session_cookie = response.headers.getlist("set-cookie")[-1].split("=", 1)[1].split(";", 1)[0]
    assert oidc.authenticate(request(cookies={oidc.cookie_name: session_cookie})).subject == "person"
    oidc.logout(response)
    assert oidc.public_config()["oidc_login"]
    assert create_auth(mode=" strange ", dev_password="", session_secret="", api_keys=set()).mode == "dev"


@pytest.mark.asyncio
async def test_openai_compat_network_paths(monkeypatch: pytest.MonkeyPatch):
    class Client:
        response: object

        def __init__(self, *args, **kwargs):
            assert kwargs["timeout"] == 900.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            if self.response == "timeout":
                raise httpx.TimeoutException("slow")
            return self.response

    class Result:
        def __init__(self, status_code=200, data=None):
            self.status_code, self._data, self.text = status_code, data or {}, "details"

        def json(self):
            return self._data

    monkeypatch.setattr("sprucer.adapters.llm.httpx.AsyncClient", Client)
    llm = OpenAICompatLlm(base_url="http://llm/", api_key="secret", default_model="default")
    Client.response = Result(data={"choices": [{"message": {"content": "ok"}}]})
    assert await llm.chat([{"role": "user", "content": "x"}], model="other") == "ok"
    Client.response = "timeout"
    with pytest.raises(RuntimeError, match="timed out"):
        await llm.chat([])
    Client.response = Result(500)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await llm.chat([])
    Client.response = Result(data={})
    with pytest.raises(RuntimeError, match="unexpected"):
        await llm.chat([])

    mock = MockLlm()
    custom = await mock.chat([{"role": "user", "content": '{"artifactTypes":["custom:case-study"]}'}])
    assert "Case Study" in custom
    assert "Cover Letter" in await mock.chat([{"role": "user", "content": "not json"}])
    assert await MockLlm(reply="fixed").chat([]) == "fixed"


@pytest.mark.asyncio
async def test_oidc_failure_and_jwt_fallback(monkeypatch: pytest.MonkeyPatch):
    class Client:
        response: object
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, *args, **kwargs): return self.response
        async def post(self, *args, **kwargs): return self.response

    class Result:
        def __init__(self, code=200, data=None):
            self.status_code, self._data, self.text = code, data or {}, "err"
        def json(self): return self._data

    monkeypatch.setattr("sprucer.adapters.oidc.httpx.AsyncClient", Client)
    oidc = OidcClient(issuer="https://idp/", client_id="id", client_secret="s", redirect_uri="cb")
    Client.response = Result(500)
    with pytest.raises(RuntimeError, match="discovery failed"):
        await oidc.discovery()
    oidc._discovery = {}
    with pytest.raises(RuntimeError, match="authorization_endpoint"):
        await oidc.authorization_url(state="x")
    with pytest.raises(RuntimeError, match="token_endpoint"):
        await oidc.exchange_code("x")
    oidc._discovery = {"token_endpoint": "token"}
    Client.response = Result(400)
    with pytest.raises(RuntimeError, match="token exchange"):
        await oidc.exchange_code("x")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "jwt-user"}).encode()).decode().rstrip("=")
    Client.response = Result(data={"id_token": f"x.{payload}.sig"})
    assert (await oidc.exchange_code("x"))["sub"] == "jwt-user"
    Client.response = Result(data={})
    with pytest.raises(RuntimeError, match="missing subject"):
        await oidc.exchange_code("x")


def test_storage_filesystem_security_settings_ssrf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = create_storage(f"sqlite:///{tmp_path / 'nested' / 'db.sqlite'}")
    assert store.get_truth()["version"] == 1
    assert store.save_truth({"version": "bad"})["version"] == 1
    assert _iso(datetime(2020, 1, 1)).endswith("+00:00")
    with pytest.raises(KeyError):
        store.delete_application("missing")
    with pytest.raises(KeyError):
        store.get_jd("missing")
    with pytest.raises(KeyError):
        store.list_generations("missing")
    with pytest.raises(KeyError):
        store.save_generation("missing", generation={"id": "g"}, content="")
    with pytest.raises(KeyError):
        store.approve_generation("missing", "g")
    with pytest.raises(KeyError):
        store.delete_generation("missing", "g")

    root = tmp_path / "vault"
    with pytest.raises(FileNotFoundError):
        import_filesystem_vault(root, store)
    (root / "current").mkdir(parents=True)
    (root / "current" / "career-truth.json").write_text("{}")
    app = root / "applications" / "a"
    app.mkdir(parents=True)
    (app / "meta.json").write_text(json.dumps({"generations": [{"id": "", "files": []}, {"id": "g", "approval": "approved", "files": ["g.md"]}]}))
    (app / "jd.txt").write_text("jd")
    (app / "generations").mkdir()
    (app / "generations" / "g.md").write_text("content")
    assert import_filesystem_vault(root, store)["generations"] == 1

    public = [(None, None, None, None, ("8.8.8.8", 80))]
    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", lambda *args, **kwargs: public)
    assert assert_public_http_url(" https://example.com/x ") == "https://example.com/x"
    for url in ("", "ftp://x", "http://", "http://u:p@example.com", "http://localhost", "http://127.0.0.1"):
        with pytest.raises(UnsafeUrlError):
            assert_public_http_url(url)
    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", lambda *args, **kwargs: [])
    with pytest.raises(UnsafeUrlError, match="Could not resolve"):
        assert_public_http_url("https://example.com")
    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", lambda *args, **kwargs: (_ for _ in ()).throw(__import__("socket").gaierror()))
    with pytest.raises(UnsafeUrlError, match="Could not resolve"):
        assert_public_http_url("https://example.com")
    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 80)), (None, None, None, None, ("not-an-ip", 80))])
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("https://example.com")

    with pytest.raises(RuntimeError, match="auth_mode=none"):
        validate_runtime_settings(settings(tmp_path, auth_mode="none", host="0.0.0.0"))
    with pytest.raises(RuntimeError, match="API_KEYS"):
        validate_runtime_settings(settings(tmp_path, auth_mode="api_key"))
    with pytest.raises(RuntimeError, match="OIDC"):
        validate_runtime_settings(settings(tmp_path, auth_mode="oidc"))
    assert validate_runtime_settings(settings(tmp_path, auth_mode="none", host="0.0.0.0", allow_insecure_dev=True)) == []
    get_settings.cache_clear()
    assert isinstance(get_settings(), Settings)
