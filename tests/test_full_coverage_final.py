from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sprucer.adapters.auth import create_auth
from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.api import app as app_mod
from sprucer.service import CareerService
from sprucer.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'final.db'}", auth_mode="oidc", host="127.0.0.1",
        session_secret="s" * 24, oidc_issuer="https://idp.example", oidc_client_id="client",
        oidc_client_secret="secret", llm_url="http://x", llm_api_key="key",
    )


def test_oidc_callback_and_application_error_routes(tmp_path: Path):
    settings = _settings(tmp_path)
    store = create_storage(settings.database_url)
    auth = create_auth(
        mode="oidc", dev_password="p", session_secret=settings.session_secret, api_keys={"key"},
        oidc_issuer=settings.oidc_issuer, oidc_client_id=settings.oidc_client_id,
        oidc_client_secret=settings.oidc_client_secret,
    )

    async def fail_exchange(code: str):
        raise RuntimeError("exchange failed")

    auth.client.exchange_code = fail_exchange  # type: ignore[method-assign]
    app = app_mod.build_app(settings=settings, service=CareerService(store, MockLlm()), auth=auth)
    with TestClient(app) as client:
        assert client.get("/v1/auth/oidc/callback?error=denied").status_code == 400
        assert client.get("/v1/auth/oidc/callback?code=x&state=missing").status_code == 400
        client.cookies.set(auth.state_cookie, "expected")
        assert client.get("/v1/auth/oidc/callback?code=x&state=wrong").status_code == 400
        assert client.get("/v1/auth/oidc/callback?code=x&state=expected").status_code == 400
        assert client.post("/v1/applications", json={}, headers={"Authorization": "Bearer key"}).status_code == 400


@pytest.mark.asyncio
async def test_ingest_collision_suffix(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'collision.db'}")
    svc = CareerService(store, MockLlm())
    first = await svc.jd_ingest(source_type="paste", text="Company: Z\nTitle: Eng\n")
    second = await svc.jd_ingest(source_type="paste", text="Company: Z\nTitle: Eng\n")
    assert second["application"]["id"] == f"{first['application']['id']}-2"
