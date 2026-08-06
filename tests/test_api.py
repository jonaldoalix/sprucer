from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sprucer.adapters.auth import create_auth
from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.api.app import build_app
from sprucer.service import CareerService
from sprucer.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite:///{db}",
        auth_mode="dev",
        dev_password="test-pass",
        session_secret="test-secret",
        llm_url="http://example.invalid/v1",
        llm_api_key="test",
        llm_model="mock",
        cors_origins="http://test",
    )
    store = create_storage(settings.database_url)
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth)
    llm = MockLlm()
    service = CareerService(store, llm)
    auth = create_auth(
        mode="dev",
        dev_password="test-pass",
        session_secret="test-secret",
        api_keys=set(),
    )
    app = build_app(settings=settings, service=service, auth=auth)
    with TestClient(app) as c:
        c.llm = llm  # type: ignore[attr-defined]
        yield c


def _auth(client: TestClient) -> None:
    res = client.post("/v1/auth/login", json={"password": "test-pass"})
    assert res.status_code == 200


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "sprucer"


def test_truth_requires_auth(client: TestClient):
    assert client.get("/v1/truth").status_code == 401
    _auth(client)
    res = client.get("/v1/truth")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["counts"]["metrics"] >= 1


def test_ingest_generate_approve_flow(client: TestClient):
    _auth(client)
    jd = (FIXTURES / "sample-jd.txt").read_text(encoding="utf-8")
    ingest = client.post("/v1/jd/ingest", json={"source_type": "paste", "text": jd})
    assert ingest.status_code == 200
    app_id = ingest.json()["application"]["id"]

    gen = client.post(
        "/v1/generate",
        json={"application_id": app_id, "types": ["cover", "email"]},
    )
    assert gen.status_code == 200
    payload = gen.json()
    assert payload["ok"] is True
    gen_id = payload["generation"]["id"]
    assert payload["generation"]["approval"] == "draft"
    assert client.llm.calls  # type: ignore[attr-defined]
    system = client.llm.calls[0][0]["content"]  # type: ignore[attr-defined]
    assert "neverClaim" in system or "Never invent" in system

    bad = client.post(
        "/v1/generations/approve",
        json={"application_id": app_id, "generation_id": gen_id, "confirm": False},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/v1/generations/approve",
        json={"application_id": app_id, "generation_id": gen_id, "confirm": True},
    )
    assert ok.status_code == 200
    assert ok.json()["generation"]["approval"] == "approved"


def test_truth_add_blurb(client: TestClient):
    _auth(client)
    res = client.patch(
        "/v1/truth",
        json={
            "op": "add",
            "section": "blurbs",
            "item": {"label": "Fixture", "text": "A defensible one-liner.", "tags": ["test"]},
        },
    )
    assert res.status_code == 200
    blurbs = res.json()["truth"]["blurbs"]
    assert any(b.get("text") == "A defensible one-liner." for b in blurbs)
