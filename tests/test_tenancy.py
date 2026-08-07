from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sprucer.adapters.auth import create_auth
from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.adapters.storage import sqlalchemy_store as store_mod
from sprucer.api.app import build_app
from sprucer.service import CareerService
from sprucer.settings import Settings
from sprucer.tenancy import SHARED_OWNER, api_key_subject, owner_key, vault_owner


def test_vault_owner_helpers():
    assert vault_owner(auth_mode="none", subject="anyone") == SHARED_OWNER
    assert vault_owner(auth_mode="dev", subject="dev") == "dev"
    assert vault_owner(auth_mode="oidc", subject="sub-1") == "sub-1"
    assert vault_owner(auth_mode="oidc", subject="  ") == SHARED_OWNER
    assert owner_key(SHARED_OWNER) == "shared"
    assert owner_key("alice@example.com").startswith("aliceexa-")
    assert api_key_subject("secret").startswith("api-key:")
    assert api_key_subject("a") != api_key_subject("b")


def test_store_isolates_truth_and_apps(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'iso.db'}")
    store.save_truth({"version": 1, "profile": {"name": "A"}}, owner="alice")
    store.save_truth({"version": 1, "profile": {"name": "B"}}, owner="bob")
    assert store.get_truth("alice")["profile"]["name"] == "A"
    assert store.get_truth("bob")["profile"]["name"] == "B"

    store.upsert_application({"id": "app-a", "company": "A Co"}, jd_text="jd-a", owner="alice")
    store.upsert_application({"id": "app-b", "company": "B Co"}, jd_text="jd-b", owner="bob")
    assert [a["id"] for a in store.list_applications("alice")] == ["app-a"]
    assert [a["id"] for a in store.list_applications("bob")] == ["app-b"]
    assert store.get_application("app-a", "bob") is None
    assert store.get_application("app-b", "alice") is None

    with pytest.raises(KeyError):
        store.upsert_application({"id": "app-a", "company": "steal"}, owner="bob")
    with pytest.raises(KeyError):
        store.delete_application("app-a", "bob")
    with pytest.raises(KeyError):
        store.get_jd("app-a", "bob")
    with pytest.raises(KeyError):
        store.save_generation(
            "app-a", generation={"id": "g1", "types": ["cover"]}, content="x", owner="bob"
        )

    store.save_generation(
        "app-a", generation={"id": "g1", "types": ["cover"]}, content="body", owner="alice"
    )
    assert store.get_generation("app-a", "g1", "bob") is None
    assert store.get_generation("app-a", "g1", "alice")["content"] == "body"
    with pytest.raises(KeyError):
        store.approve_generation("app-a", "g1", "bob")
    with pytest.raises(KeyError):
        store.delete_generation("app-a", "g1", "bob")
    store.approve_generation("app-a", "g1", "alice")
    store.delete_generation("app-a", "g1", "alice")


def test_owner_subject_migration(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'mig.db'}")
    mock_conn = MagicMock()
    begin_cm = MagicMock()
    begin_cm.__enter__.return_value = mock_conn
    begin_cm.__exit__.return_value = False
    with patch.object(store_mod, "inspect") as insp:
        insp.return_value.get_columns.return_value = [{"name": "id"}, {"name": "document"}]
        with patch.object(store.engine, "begin", return_value=begin_cm):
            store._ensure_owner_subject_columns()
    assert mock_conn.execute.call_count >= 1

    with patch.object(store_mod, "inspect", side_effect=RuntimeError("boom")):
        store._ensure_owner_subject_columns()


@pytest.mark.asyncio
async def test_service_owner_scoping(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'svc.db'}")
    svc = CareerService(store, MockLlm())
    await svc.jd_ingest(source_type="paste", text="Acme Inc\nEngineer\n", owner="alice")
    await svc.jd_ingest(source_type="paste", text="Beta LLC\nEngineer\n", owner="bob")
    alice_apps = svc.applications_list(owner="alice")["items"]
    bob_apps = svc.applications_list(owner="bob")["items"]
    assert len(alice_apps) == 1
    assert len(bob_apps) == 1
    assert alice_apps[0]["id"] != bob_apps[0]["id"]
    assert alice_apps[0]["id"].startswith(owner_key("alice"))
    with pytest.raises(RuntimeError, match="not found"):
        svc.applications_get(alice_apps[0]["id"], owner="bob")
    # Same application id claimed by another vault
    with pytest.raises(RuntimeError, match="conflicts"):
        svc.applications_upsert({"id": alice_apps[0]["id"], "company": "Nope"}, owner="bob")
    with pytest.raises(RuntimeError, match="conflicts"):
        await svc.jd_ingest(
            source_type="paste",
            text="Steal\nRole\n",
            application_id=alice_apps[0]["id"],
            owner="bob",
        )


def test_api_key_isolation(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'keys.db'}",
        auth_mode="api_key",
        host="127.0.0.1",
        session_secret="s" * 24,
        api_keys="alpha,beta",
        llm_url="http://x",
        llm_api_key="k",
        llm_model="m",
        cors_origins="http://test",
    )
    store = create_storage(settings.database_url)
    auth = create_auth(
        mode="api_key",
        dev_password="x",
        session_secret=settings.session_secret,
        api_keys={"alpha", "beta"},
    )
    app = build_app(settings=settings, service=CareerService(store, MockLlm()), auth=auth)
    with TestClient(app) as client:
        a = client.post(
            "/v1/jd/ingest",
            json={"source_type": "paste", "text": "Alpha Co\nRole"},
            headers={"Authorization": "Bearer alpha"},
        )
        assert a.status_code == 200
        app_id = a.json()["application"]["id"]
        listed_b = client.get("/v1/applications", headers={"Authorization": "Bearer beta"})
        assert listed_b.status_code == 200
        assert listed_b.json()["items"] == []
        missing = client.get(f"/v1/applications/{app_id}", headers={"Authorization": "Bearer beta"})
        assert missing.status_code == 404
        listed_a = client.get("/v1/applications", headers={"Authorization": "Bearer alpha"})
        assert len(listed_a.json()["items"]) == 1
        who = client.get("/v1/auth/whoami", headers={"Authorization": "Bearer alpha"})
        assert who.json()["vault"] == api_key_subject("alpha")


def test_none_mode_shared_vault(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'none.db'}",
        auth_mode="none",
        host="127.0.0.1",
        allow_insecure_dev=True,
        session_secret="s" * 24,
        llm_url="http://x",
        llm_api_key="k",
        llm_model="m",
        cors_origins="http://test",
    )
    store = create_storage(settings.database_url)
    store.save_truth({"version": 1, "profile": {"name": "Shared"}}, owner=SHARED_OWNER)
    auth = create_auth(mode="none", dev_password="x", session_secret=settings.session_secret, api_keys=set())
    app = build_app(settings=settings, service=CareerService(store, MockLlm()), auth=auth)
    with TestClient(app) as client:
        truth = client.get("/v1/truth")
        assert truth.status_code == 200
        assert truth.json()["truth"]["profile"]["name"] == "Shared"
        who = client.get("/v1/auth/whoami")
        assert who.json()["vault"] == SHARED_OWNER
