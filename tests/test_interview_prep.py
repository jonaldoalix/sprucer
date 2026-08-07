from __future__ import annotations

from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage.sqlalchemy_store import SqlAlchemyStorage
from sprucer.service import CareerService


def _svc(tmp_path) -> CareerService:
    store = SqlAlchemyStorage(f"sqlite:///{tmp_path / 't.db'}")
    store.ensure_schema()
    return CareerService(store, MockLlm())


def test_interview_rejects_fake_ticket_ids(tmp_path):
    svc = _svc(tmp_path)
    bad = """
## Interview Prep
### Likely questions
1. What is Epic Resolute?
   - Coaching Line: *Use Project ID 00345*
2. How do you handle HIPAA?
   - Coaching Line: *Refer to Story ID 12345*
3. How do you troubleshoot?
   - Coaching Line: *Use Metric ID 00789*
### Refresh from your knowledge bank
- **Project ID 00345**: Fake overview
"""
    assert not svc._content_satisfies_types(
        bad, ["interview"], cite_ids={"nrs-sites", "components-tenure"}
    )


def test_interview_accepts_real_cites_and_answer_hooks(tmp_path):
    svc = _svc(tmp_path)
    good = """
## Interview Prep
### Likely questions
1. How have you supported complex business apps in production?
   - Answer with: Lead with Components USA web/IT ownership and multi-site ops. Cite: `components-tenure`
2. How do you reason about SQL-backed systems under change?
   - Answer with: Point to NRS SQL estate scale and how you kept client sites healthy. Cite: `nrs-dbs`
3. Tell me about a platform you shipped that stakeholders still use.
   - Answer with: Parker Fund scholarship platform live since 2020. Cite: `parker-platform`
### Refresh from your knowledge bank
- `components-tenure` — Components USA: ~10 years continuous web/IT/hosting
- `nrs-dbs` — NRS: 250+ SQL databases managed
- `parker-platform` — Parker Fund: scholarship platform live since 2020
### Watch-outs
- Never claim unverified percentage metrics
"""
    assert svc._content_satisfies_types(
        good,
        ["interview"],
        cite_ids={"components-tenure", "nrs-dbs", "parker-platform"},
    )


def test_interview_cite_catalog_uses_real_vault_ids(tmp_path):
    svc = _svc(tmp_path)
    truth = {
        "metrics": [{"id": "nrs-sites", "text": "NRS: 120+ sites"}],
        "projects": [{"id": "project-08866b90", "title": "Applicant Management Suite"}],
        "experience": [{"id": "exp-1", "role": "Web & IT Administrator", "employer": "Components USA"}],
        "neverClaim": ["Unverified percentage metrics"],
        "signatureStories": [],
        "blurbs": [],
    }
    catalog = svc._interview_cite_catalog(truth)
    ids = {row["id"] for row in catalog if row["id"]}
    assert "nrs-sites" in ids
    assert "project-08866b90" in ids
    assert "exp-1" in ids
    assert any(row["kind"] == "neverClaim" for row in catalog)


def test_type_batches_splits_all_five_presets(tmp_path):
    svc = _svc(tmp_path)
    batches = svc._type_batches(["cover", "email", "resume", "interview", "linkedin"])
    flat = [t for batch in batches for t in batch]
    assert flat == ["cover", "email", "resume", "interview", "linkedin"]
    assert ["interview"] in batches
    assert max(len(b) for b in batches) <= 2 or any(b == ["interview"] for b in batches)
