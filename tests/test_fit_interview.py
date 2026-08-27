from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sprucer.adapters.auth import create_auth
from sprucer.adapters.llm import DemoLlm, MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.api.app import build_app
from sprucer.service import CareerService
from sprucer.settings import Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


@pytest.fixture
def fit_env(tmp_path: Path):
    db = tmp_path / "fit.db"
    settings = Settings(
        database_url=f"sqlite:///{db}",
        auth_mode="dev",
        host="127.0.0.1",
        allow_insecure_dev=False,
        dev_password="test-pass",
        session_secret="test-secret-not-default-value",
        llm_url="http://example.invalid/v1",
        llm_api_key="test",
        llm_model="mock",
        cors_origins="http://test",
    )
    store = create_storage(settings.database_url)
    llm = MockLlm()
    service = CareerService(store, llm)
    auth = create_auth(
        mode="dev",
        dev_password="test-pass",
        session_secret="test-secret",
        api_keys=set(),
    )
    app = build_app(settings=settings, service=service, auth=auth)
    with TestClient(app) as client:
        yield client, store, service, llm


def _auth(client: TestClient) -> None:
    res = client.post("/v1/auth/login", json={"password": "test-pass"})
    assert res.status_code == 200


def test_fit_start_confirm_when_spectrum_present(fit_env):
    client, store, _service, _llm = fit_env
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth, owner="dev")
    _auth(client)
    res = client.post("/v1/fit/start", json={})
    assert res.status_code == 200
    session = res.json()["session"]
    assert session["mode"] == "confirm"
    assert session["status"] == "interviewing"
    assert session["messages"][0]["role"] == "assistant"
    assert "role spectrum" in session["messages"][0]["content"].lower() or "knowledge bank" in session[
        "messages"
    ][0]["content"].lower()


def test_fit_start_inquire_when_empty(fit_env):
    client, _store, _service, _llm = fit_env
    _auth(client)
    res = client.post("/v1/fit/start", json={})
    assert res.status_code == 200
    session = res.json()["session"]
    assert session["mode"] == "inquire"
    assert "inquire" in session["messages"][0]["content"].lower() or "energize" in session[
        "messages"
    ][0]["content"].lower()


def test_fit_turn_recommend_accept_writes_career_fit(fit_env):
    client, store, _service, llm = fit_env
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth, owner="dev")
    _auth(client)

    start = client.post("/v1/fit/start", json={})
    session_id = start.json()["session"]["id"]

    turn = client.post(
        "/v1/fit/turn",
        json={"session_id": session_id, "message": "Confirm platform focus; remote OK; no healthcare."},
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["session"]["messages"][-1]["role"] == "assistant"
    assert len(llm.calls) >= 1

    rec = client.post("/v1/fit/recommend", json={"session_id": session_id})
    assert rec.status_code == 200, rec.text
    draft = rec.json()["draft"]
    assert draft["industries"]
    assert draft["titles"]
    assert all("http" not in (i.get("rationale") or "").lower() for i in draft["industries"])

    deny = client.post("/v1/fit/accept", json={"session_id": session_id, "confirm": False})
    assert deny.status_code == 400

    accept = client.post(
        "/v1/fit/accept",
        json={"session_id": session_id, "confirm": True, "update_role_spectrum": True},
    )
    assert accept.status_code == 200, accept.text
    career_fit = accept.json()["careerFit"]
    assert career_fit["industries"]
    assert career_fit["sourceSessionId"] == session_id

    vault = store.get_truth("dev")
    assert vault["careerFit"]["industries"]
    assert vault["roleSpectrum"]["summary"]

    listed = client.get("/v1/fit/sessions")
    assert listed.status_code == 200
    assert any(s["id"] == session_id for s in listed.json()["sessions"])


def test_fit_demo_llm_rejected_on_turn(tmp_path: Path):
    db = tmp_path / "demo-fit.db"
    settings = Settings(
        database_url=f"sqlite:///{db}",
        auth_mode="dev",
        host="127.0.0.1",
        allow_insecure_dev=False,
        dev_password="test-pass",
        session_secret="test-secret-not-default-value",
        llm_url="",
        llm_api_key="",
        llm_model="demo",
        cors_origins="http://test",
        demo=True,
    )
    store = create_storage(settings.database_url)
    service = CareerService(store, DemoLlm())
    auth = create_auth(
        mode="dev",
        dev_password="test-pass",
        session_secret="test-secret",
        api_keys=set(),
    )
    app = build_app(settings=settings, service=service, auth=auth)
    with TestClient(app) as client:
        _auth(client)
        start = client.post("/v1/fit/start", json={})
        assert start.status_code == 200
        session_id = start.json()["session"]["id"]
        turn = client.post(
            "/v1/fit/turn",
            json={"session_id": session_id, "message": "I like platform work"},
        )
        assert turn.status_code == 400
        assert "live LLM" in turn.json()["detail"]


def test_fit_recommend_rejects_invented_employer_urls(fit_env):
    import asyncio

    _client, store, service, llm = fit_env
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    store.save_truth(truth, owner="dev")
    started = service.fit_start(owner="dev")
    session_id = started["session"]["id"]
    session = store.get_fit_session(session_id, "dev")
    assert session is not None
    session["messages"].append({"role": "user", "content": "Platform focus"})
    store.save_fit_session(session_id, session, owner="dev")

    llm.reply = json.dumps(
        {
            "industries": [
                {
                    "name": "Acme Corp openings",
                    "rank": 1,
                    "rationale": "See https://jobs.example.com/acme",
                }
            ],
            "titles": [],
            "constraints": {},
            "confidence": "high",
            "notes": "",
        }
    )

    with pytest.raises(RuntimeError, match="employers or job postings"):
        asyncio.run(service.fit_recommend(session_id=session_id, owner="dev"))
