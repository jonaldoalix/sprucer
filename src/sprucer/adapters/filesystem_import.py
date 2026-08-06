"""Optional import from a lab-style filesystem career vault."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sprucer.adapters.storage.sqlalchemy_store import SqlAlchemyStorage


def import_filesystem_vault(vault_root: Path | str, store: SqlAlchemyStorage) -> dict[str, Any]:
    root = Path(vault_root)
    truth_path = root / "current" / "career-truth.json"
    if not truth_path.is_file():
        raise FileNotFoundError(f"Missing {truth_path}")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    store.save_truth(truth)

    apps_root = root / "applications"
    imported_apps = 0
    imported_gens = 0
    if apps_root.is_dir():
        for child in sorted(apps_root.iterdir()):
            if not child.is_dir():
                continue
            meta_path = child / "meta.json"
            if not meta_path.is_file():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            jd = ""
            jd_path = child / "jd.txt"
            if jd_path.is_file():
                jd = jd_path.read_text(encoding="utf-8", errors="replace")
            meta.setdefault("id", child.name)
            store.upsert_application(meta, jd_text=jd)
            imported_apps += 1

            gens_dir = child / "generations"
            if not gens_dir.is_dir():
                continue
            # Prefer meta.generations list; fall back to scanning markdown
            for g in meta.get("generations") or []:
                gen_id = str(g.get("id") or "")
                files = g.get("files") or []
                content = ""
                if files:
                    p = gens_dir / files[0]
                    if p.is_file():
                        content = p.read_text(encoding="utf-8", errors="replace")
                if not gen_id:
                    continue
                store.save_generation(
                    meta["id"],
                    generation={
                        "id": gen_id,
                        "types": g.get("types") or [],
                        "emphasisPlan": g.get("emphasisPlan") or [],
                        "approval": g.get("approval") or "draft",
                    },
                    content=content,
                )
                if (g.get("approval") or "") == "approved":
                    store.approve_generation(meta["id"], gen_id)
                imported_gens += 1

    return {"ok": True, "applications": imported_apps, "generations": imported_gens}
