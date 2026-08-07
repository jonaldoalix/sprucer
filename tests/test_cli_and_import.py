from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sprucer.adapters.filesystem_import import import_filesystem_vault
from sprucer.adapters.storage import create_storage
from sprucer.cli.main import app as cli_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"
runner = CliRunner()


def test_filesystem_vault_import(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "current").mkdir(parents=True)
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    (vault / "current" / "career-truth.json").write_text(json.dumps(truth), encoding="utf-8")

    app_dir = vault / "applications" / "acme-role"
    app_dir.mkdir(parents=True)
    (app_dir / "meta.json").write_text(
        json.dumps(
            {
                "id": "acme-role",
                "company": "Acme",
                "title": "Eng",
                "generations": [
                    {
                        "id": "g1",
                        "types": ["cover"],
                        "approval": "approved",
                        "files": ["g1.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (app_dir / "jd.txt").write_text("Company: Acme\nTitle: Eng\n", encoding="utf-8")
    gens = app_dir / "generations"
    gens.mkdir()
    (gens / "g1.md").write_text("## Cover Letter\n\nHi\n", encoding="utf-8")

    db = tmp_path / "import.db"
    store = create_storage(f"sqlite:///{db}")
    result = import_filesystem_vault(vault, store)
    assert result["applications"] == 1
    assert result["generations"] == 1
    assert store.get_application("acme-role") is not None


def test_filesystem_vault_missing(tmp_path: Path):
    store = create_storage(f"sqlite:///{tmp_path / 'x.db'}")
    try:
        import_filesystem_vault(tmp_path / "nope", store)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_cli_load_fixture(tmp_path: Path):
    db = tmp_path / "cli.db"
    result = runner.invoke(
        cli_app,
        [
            "load-fixture",
            "--database-url",
            f"sqlite:///{db}",
            "--truth",
            str(FIXTURES / "career-truth.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    store = create_storage(f"sqlite:///{db}")
    assert store.get_truth().get("profile")


def test_cli_import_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "current").mkdir(parents=True)
    truth = json.loads((FIXTURES / "career-truth.json").read_text(encoding="utf-8"))
    (vault / "current" / "career-truth.json").write_text(json.dumps(truth), encoding="utf-8")
    db = tmp_path / "cli-import.db"
    result = runner.invoke(
        cli_app,
        ["import-vault", str(vault), "--database-url", f"sqlite:///{db}"],
    )
    assert result.exit_code == 0, result.output
