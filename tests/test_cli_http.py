from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sprucer.cli.main import app as cli_app

runner = CliRunner()


class _FakeResp:
    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def json(self):
        return self._data

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, *a, **k):
        self.posts = []
        self.init_kwargs = k

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, path):
        if path == "/health":
            return _FakeResp({"ok": True, "service": "sprucer"})
        if path == "/v1/truth":
            return _FakeResp({"ok": True, "truth": {}})
        if path == "/v1/applications":
            return _FakeResp({"ok": True, "items": []})
        return _FakeResp({"ok": True})

    def post(self, path, payload=None):
        self.posts.append((path, payload))
        if path == "/v1/auth/login":
            return _FakeResp({"ok": True})
        return _FakeResp({"ok": True, "application": {"id": "a1"}, "generation": {"id": "g1"}})


def test_cli_http_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class Client(_FakeClient):
        def post(self, path, json=None):
            return super().post(path, payload=json)

    monkeypatch.setattr("sprucer.cli.main.httpx.Client", Client)
    assert runner.invoke(cli_app, ["health"]).exit_code == 0
    assert runner.invoke(cli_app, ["--password", "x", "truth"]).exit_code == 0
    assert runner.invoke(cli_app, ["--api-key", "k", "list"]).exit_code == 0
    jd = tmp_path / "jd.txt"
    jd.write_text("Company: Z\nTitle: Y\n", encoding="utf-8")
    assert runner.invoke(cli_app, ["ingest", "--paste", str(jd)]).exit_code == 0
    assert runner.invoke(cli_app, ["ingest", "--url", "https://example.com/j"]).exit_code == 0
    assert runner.invoke(cli_app, ["ingest"]).exit_code != 0
    assert runner.invoke(cli_app, ["generate", "a1", "--types", "cover"]).exit_code == 0
    assert runner.invoke(cli_app, ["approve", "a1", "g1"]).exit_code == 0


def test_cli_client_password_and_api_key(monkeypatch: pytest.MonkeyPatch):
    from sprucer.cli import main as cli_main

    created: list[_FakeClient] = []

    class Client(_FakeClient):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(self)

        def post(self, path, json=None):
            return super().post(path, payload=json)

    monkeypatch.setattr(cli_main.httpx, "Client", Client)

    with cli_main._client("http://127.0.0.1:8787", password="secret", api_key=None):
        pass
    assert created[-1].posts[0] == ("/v1/auth/login", {"password": "secret"})
    assert created[-1].init_kwargs.get("headers") == {}

    with cli_main._client("http://127.0.0.1:8787/", password=None, api_key="k"):
        pass
    assert created[-1].init_kwargs.get("headers") == {"Authorization": "Bearer k"}
