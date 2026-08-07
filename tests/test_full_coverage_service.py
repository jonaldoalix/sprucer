from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.service import CareerService, _clean_jd_text, _guess_fields, _slug, _strip_html


def service(tmp_path: Path, reply: str | None = None) -> CareerService:
    store = create_storage(f"sqlite:///{tmp_path / 'service.db'}")
    store.save_truth(
        {
            "profile": {"name": "Person", "shortName": "P"},
            "roleSpectrum": {"summary": "operator"},
            "metrics": [{"id": "m1", "text": "Improved cloud reliability", "tags": ["cloud"]}, "bad"],
            "blurbs": [{"id": "b1", "text": "Built platforms", "tags": ["platform"]}, "bad"],
            "projects": [{"id": "p1", "title": "Project"}],
            "experience": [{"id": "e1", "role": "Engineer", "employer": "Co"}],
            "signatureStories": [{"id": "s1", "title": "Story"}],
            "neverClaim": ["No fake claims"],
        }
    )
    return CareerService(store, MockLlm(reply=reply))


def test_service_sync_error_and_helper_paths(tmp_path: Path):
    svc = service(tmp_path)
    assert _slug(" Hello, World! ") == "hello-world"
    assert _slug("", fallback="x") == "x"
    assert "hello" in _strip_html("<style>x</style><script>x</script><p>hello &amp; bye</p>")
    assert _clean_jd_text(" a\r\n\r\n\r\nb ") == "a\n\nb"
    assert _guess_fields("Title\nCompany Inc\nRemote")["company"] == "Company Inc"
    assert svc.truth_get()["counts"]["metrics"] == 2
    assert svc.truth_patch(op="set", section="headline", value="new")["truth"]["headline"] == "new"
    for kwargs, match in [
        (dict(op="add", section="bad"), "section"),
        (dict(op="add", section="neverClaim", item={}), "requires text"),
        (dict(op="add", section="metrics", item=None), "item object"),
        (dict(op="update", section="neverClaim", item={}), "supports"),
        (dict(op="update", section="metrics", item={}), "not found"),
        (dict(op="remove", section="metrics"), "confirm"),
        (dict(op="remove", section="neverClaim", confirm=True), "index"),
        (dict(op="remove", section="metrics", confirm=True), "item_id"),
        (dict(op="wat", section="metrics"), "op must"),
    ]:
        with pytest.raises(RuntimeError, match=match):
            svc.truth_patch(**kwargs)
    added = svc.truth_patch(op="add", section="metrics", item={"text": "x"})["truth"]["metrics"][-1]
    assert added["id"].startswith("metric-")
    assert svc.truth_patch(op="update", section="metrics", index=0, item={}).get("ok") is True
    assert svc.truth_patch(op="remove", section="metrics", index=0, confirm=True)["ok"]
    assert svc.truth_patch(op="add", section="neverClaim", item={"body": "avoid"})["ok"]
    assert svc.truth_patch(op="remove", section="neverClaim", index=0, confirm=True)["ok"]

    assert svc.applications_list()["items"] == []
    with pytest.raises(RuntimeError, match="not found"):
        svc.applications_get("no")
    with pytest.raises(RuntimeError, match="id is required"):
        svc.applications_upsert({})
    app = svc.applications_upsert({"application_id": "a", "company": "Co"})["application"]
    assert app["id"] == "a"
    with pytest.raises(RuntimeError, match="confirm"):
        svc.applications_delete("a")
    with pytest.raises(RuntimeError, match="not found"):
        svc.applications_delete("no", confirm=True)
    assert svc.applications_delete("a", confirm=True)["deleted"] == "a"
    assert svc._normalize_types(["cover", "THING", "cover", "", "custom:x"], "One Off") == ["cover", "custom:thing", "custom:x", "custom:one-off"]
    with pytest.raises(RuntimeError, match="at least"):
        svc._normalize_types([], None)
    assert "Cover Letter" in svc._heading_instruction(["cover", "custom:thing"])
    assert "Do NOT write ## Cover" in svc._heading_instruction(["email"])
    assert svc._type_batches(["cover", "email", "resume", "interview", "linkedin"])
    assert svc._max_tokens_for(["interview", "resume"]) == 3400


@pytest.mark.asyncio
async def test_ingest_fetch_generate_errors_and_repairs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    svc = service(tmp_path)
    for kwargs, match in [
        (dict(source_type="wat"), "source_type"),
        (dict(source_type="paste"), "text is required"),
        (dict(source_type="url"), "url is required"),
        (dict(source_type="upload"), "content_base64"),
    ]:
        with pytest.raises(RuntimeError, match=match):
            await svc.jd_ingest(**kwargs)
    html = base64.b64encode(b"<html><body>Role\nCloud Company\nRemote</body></html>").decode()
    ingest = await svc.jd_ingest(source_type="upload", filename="x.html", content_base64=html)
    app_id = ingest["application"]["id"]
    assert (await svc.jd_ingest(source_type="paste", text="Role\nCloud Company", application_id=app_id))["application"]["id"] == app_id
    with pytest.raises(RuntimeError, match="not found"):
        await svc.generate(application_id="no", types=["cover"])
    svc.store.upsert_application({"id": "empty"})
    with pytest.raises(RuntimeError, match="JD missing"):
        await svc.generate(application_id="empty", types=["cover"])

    class Response:
        def __init__(self, status=200, text="Title\nCloud Inc", headers=None, url="https://example.test/a"):
            self.status_code, self.text, self.headers, self.url = status, text, headers or {}, url
        @property
        def is_redirect(self): return self.status_code in {301, 302}

    class Client:
        responses: list[object] = []
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, *args, **kwargs):
            value = self.responses.pop(0)
            if isinstance(value, Exception): raise value
            return value

    monkeypatch.setattr("sprucer.service.httpx.AsyncClient", Client)
    monkeypatch.setattr("sprucer.service.assert_public_http_url", lambda value: value, raising=False)
    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", lambda value: value)
    Client.responses = [Response(302, headers={})]
    with pytest.raises(RuntimeError, match="missing Location"):
        await svc._fetch_url_text("https://example.test")
    Client.responses = [Response(403)]
    with pytest.raises(RuntimeError, match="Paste"):
        await svc._fetch_url_text("https://example.test")
    Client.responses = [Response(500)]
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await svc._fetch_url_text("https://example.test")
    Client.responses = [httpx.RequestError("no")]
    with pytest.raises(RuntimeError, match="URL fetch failed"):
        await svc._fetch_url_text("https://example.test")
    Client.responses = [Response(200, "<html><p>Hello</p></html>", {"content-type": "text/html"})]
    assert (await svc._fetch_url_text("https://example.test"))[0] == "Hello"

    bad = CareerService(svc.store, MockLlm(reply="## Wrong\nx"))
    with pytest.raises(RuntimeError, match="wrong artifact"):
        await bad.generate(application_id=app_id, types=["cover"])
    repaired = CareerService(svc.store, MockLlm(reply="## Email\nSubject: x\nHi\nThanks"))
    result = await repaired.generate(application_id=app_id, types=["email"])
    gid = result["generation"]["id"]
    assert repaired.generation_get(application_id=app_id, generation_id=gid)["content"]
    with pytest.raises(RuntimeError, match="confirm"):
        repaired.generation_approve(application_id=app_id, generation_id=gid)
    with pytest.raises(RuntimeError, match="not found"):
        repaired.generation_approve(application_id=app_id, generation_id="no", confirm=True)
    assert repaired.generation_approve(application_id=app_id, generation_id=gid, confirm=True)["ok"]
    with pytest.raises(RuntimeError, match="confirm"):
        repaired.generation_delete(application_id=app_id, generation_id=gid)
    with pytest.raises(RuntimeError, match="not found"):
        repaired.generation_delete(application_id=app_id, generation_id="no", confirm=True)
    assert repaired.generation_delete(application_id=app_id, generation_id=gid, confirm=True)["ok"]
    with pytest.raises(RuntimeError, match="not found"):
        repaired.generation_get(application_id=app_id, generation_id=gid)


def test_content_validation_branches(tmp_path: Path):
    svc = service(tmp_path)
    assert not svc._content_satisfies_types("## Cover Letter\nx", ["email"])
    assert not svc._content_satisfies_types("## LinkedIn DM\nupdate your LinkedIn", ["linkedin"])
    assert not svc._content_satisfies_types("## LinkedIn DM\n" + "\n- x" * 9, ["linkedin"])
    assert not svc._content_satisfies_types("## LinkedIn DM\n[Your Name]", ["linkedin"])
    assert not svc._content_satisfies_types("## Interview Prep\nx", ["interview"])
    assert not svc._content_satisfies_types("## Interview Prep\n### Questions\nProject ID 12345", ["interview"])
    assert not svc._content_satisfies_types("## Interview Prep\n### Questions\n?", ["interview"], cite_ids={"m1", "b1"})
    assert not svc._content_satisfies_types("## Interview Prep\n### Questions\n? ? ?\nm1 b1", ["interview"], cite_ids={"m1", "b1", "e1"})
    assert svc._content_satisfies_types("## Interview Prep\n### Questions\n? ? ?\nAnswer with: m1 b1 e1", ["interview"], cite_ids={"m1", "b1", "e1"})


def test_email_validation_guard_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    svc = service(tmp_path)
    monkeypatch.setitem(
        __import__("sprucer.service", fromlist=["ARTIFACT_HEADINGS"]).ARTIFACT_HEADINGS,
        "email",
        ("foo",),
    )
    assert not svc._content_satisfies_types("## Foo\n## Cover Letter\nx", ["email"])
    assert not svc._content_satisfies_types("## Foo\nx", ["email"])
