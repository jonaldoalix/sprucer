"""Tests for the richer JD extraction ported from Nathan.

Covers Workday CXS mapping, HTML hero/job-description extraction, PDF/DOCX/DOC
upload parsing, field guessing, and the SSRF-safe URL routing in
``CareerService._fetch_url_text`` / ``_fetch_workday_cxs``.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from sprucer.adapters.llm import MockLlm
from sprucer.adapters.storage import create_storage
from sprucer.service import (
    CareerService,
    _clean_jd_text,
    _extract_docx_text,
    _extract_html_jd,
    _extract_pdf_text,
    _find_workday_job_url,
    _guess_fields,
    _meta_content,
    _strip_html,
    _workday_cxs_url,
)


def _svc(tmp_path: Path) -> CareerService:
    store = create_storage(f"sqlite:///{tmp_path / 'ext.db'}")
    return CareerService(store, MockLlm())


def _docx_bytes(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_strip_html_preserves_structure():
    out = _strip_html(
        "<script>x</script><style>y</style><noscript>z</noscript>"
        "<br><p>Hello&nbsp;World</p><ul><li>a</li><li>b</li></ul>"
    )
    assert "Hello World" in out
    assert "- a" in out and "- b" in out
    assert "x" not in out and "z" not in out


def test_clean_jd_text_drops_workday_empty_tails():
    txt = "Real body here.\nRequirements:\nEducation if Required:\n"
    assert _clean_jd_text(txt) == "Real body here."


def test_meta_content_matches_and_missing():
    assert _meta_content('<meta name="og:title" content="X Co">', "og:title") == "X Co"
    assert _meta_content("<html></html>", "og:title") == ""


def test_extract_html_jd_full_hero_and_chunk():
    raw = (
        "<title>Senior Engineer | Boston, MA | Acme Corp</title>"
        '<meta property="og:title" content="Senior Engineer at Acme Corp">'
        '<h1 class="hero-title"><span>Staff Engineer</span></h1>'
        '<div class="meta-location"><span>Remote US</span></div>'
        '<section id="job-description">' + ("Build things well. " * 60) + "</section>"
    )
    text, fields = _extract_html_jd(raw)
    assert fields["title"] == "Staff Engineer"
    assert fields["location"] == "Remote US"
    assert fields["company"] == "Acme Corp"
    assert "Build things well." in text


def test_extract_html_jd_og_fallback_and_marker():
    big = "nav chrome text " * 300  # > 2500 chars
    raw = (
        '<meta property="og:title" content="Cloud Architect">'
        + big
        + "Job Description: the real content lives here"
    )
    text, fields = _extract_html_jd(raw)
    assert fields["title"] == "Cloud Architect"
    assert text.lower().startswith("job description")


def test_workday_cxs_url_mapping():
    assert (
        _workday_cxs_url(
            "https://acme.wd5.myworkdayjobs.com/en-US/SSH_Careers/job/Boston/Title_R-1/apply"
        )
        == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/SSH_Careers/job/Boston/Title_R-1"
    )
    assert _workday_cxs_url("https://example.com/job") is None


def test_find_workday_job_url():
    found = _find_workday_job_url(
        'x <a href="https://acme.wd5.myworkdayjobs.com/SSH/job/Boston/T-1/apply?x=1">apply</a>'
    )
    assert found == "https://acme.wd5.myworkdayjobs.com/SSH/job/Boston/T-1"
    assert _find_workday_job_url("no links here") is None


def test_extract_docx_text():
    assert _extract_docx_text(_docx_bytes("Hello", "World")) == "Hello\nWorld"


def test_extract_pdf_text_filters_short_tokens():
    out = _extract_pdf_text(b"x (Hello World) y (ab) z (Second Line Yay)")
    assert "Hello World" in out
    assert "Second Line Yay" in out
    assert "ab" not in out.split()


def test_guess_fields_label_and_noise_and_host():
    loc = _guess_fields("Location: Boston, MA\nsome body text")
    assert loc["location"] == "Boston, MA"

    noisy = _guess_fields("http://x\nskip to main content\nReal Title Here")
    assert noisy["title"] == "Real Title Here"

    assert _guess_fields("body only", url="https://acme.com/careers/1")["company"] == "Acme"
    assert (
        _guess_fields("body only", url="https://careers.bigco.org/job/1")["company"] == "Bigco"
    )


# ---------------------------------------------------------------------------
# Async fetch routing (mocked httpx + SSRF bypass)
# ---------------------------------------------------------------------------

_HANDLER: list = [None]


class _Resp:
    def __init__(self, status=200, text="", headers=None, url="https://x/", content=None, data=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.url = url
        self.content = content if content is not None else text.encode()
        self._data = data

    @property
    def is_redirect(self) -> bool:
        return self.status_code in {301, 302, 303, 307, 308}

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class _Client:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        return _HANDLER[0](url, headers)


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("sprucer.service.httpx.AsyncClient", _Client)
    monkeypatch.setattr("sprucer.ssrf.assert_public_http_url", lambda u, resolve=True: u)
    yield


def _wd_payload(desc: str, *, title="Engineer"):
    return {
        "jobPostingInfo": {
            "title": title,
            "jobDescription": f"<p>{desc}</p>",
            "jobPostingLocation": {"descriptor": "Boston, MA"},
        },
        "hiringOrganization": {"name": "Acme"},
    }


@pytest.mark.asyncio
async def test_fetch_direct_workday_cxs(tmp_path: Path, patched):
    svc = _svc(tmp_path)

    def handler(url, headers):
        assert "wday/cxs" in url
        return _Resp(200, headers={"content-type": "application/json"}, data=_wd_payload("word " * 40))

    _HANDLER[0] = handler
    text, hints = await svc._fetch_url_text(
        "https://acme.wd5.myworkdayjobs.com/en-US/SSH/job/Boston/T-1"
    )
    assert "Engineer" in text
    assert hints["company"] == "Acme"
    assert hints["location"] == "Boston, MA"


@pytest.mark.asyncio
async def test_fetch_workday_cxs_none_paths(tmp_path: Path, patched):
    svc = _svc(tmp_path)
    client = _Client()

    assert await svc._fetch_workday_cxs(client, "https://example.com/not-workday") is None

    def raiser(url, headers):
        raise httpx.RequestError("boom")

    _HANDLER[0] = raiser
    assert await svc._fetch_workday_cxs(client, "https://t.wd1.myworkdayjobs.com/S/job/C/R-1") is None

    _HANDLER[0] = lambda url, headers: _Resp(500)
    assert await svc._fetch_workday_cxs(client, "https://t.wd1.myworkdayjobs.com/S/job/C/R-1") is None

    _HANDLER[0] = lambda url, headers: _Resp(200, text="notjson")
    assert await svc._fetch_workday_cxs(client, "https://t.wd1.myworkdayjobs.com/S/job/C/R-1") is None

    _HANDLER[0] = lambda url, headers: _Resp(200, data={"jobPostingInfo": {}})
    assert await svc._fetch_workday_cxs(client, "https://t.wd1.myworkdayjobs.com/S/job/C/R-1") is None


@pytest.mark.asyncio
async def test_fetch_pdf_by_content_type_and_extension(tmp_path: Path, patched):
    svc = _svc(tmp_path)

    _HANDLER[0] = lambda url, headers: _Resp(
        200, headers={"content-type": "application/pdf"}, content=b"(Hello World Role)"
    )
    text, _ = await svc._fetch_url_text("https://x/job")
    assert "Hello World Role" in text

    _HANDLER[0] = lambda url, headers: _Resp(
        200, headers={"content-type": "text/plain"}, content=b"(Some Role Here)"
    )
    text2, _ = await svc._fetch_url_text("https://x/jd.pdf")
    assert "Some Role Here" in text2


@pytest.mark.asyncio
async def test_fetch_json_jobposting_and_plain(tmp_path: Path, patched):
    svc = _svc(tmp_path)

    _HANDLER[0] = lambda url, headers: _Resp(
        200,
        headers={"content-type": "application/json"},
        data={"jobPostingInfo": {"title": "Eng", "jobDescription": "<p>Body text</p>"}},
    )
    text, hints = await svc._fetch_url_text("https://x/api")
    assert "Eng" in text and "Body text" in text and hints["title"] == "Eng"

    # JSON without jobPostingInfo -> return raw body text.
    _HANDLER[0] = lambda url, headers: _Resp(
        200, headers={"content-type": "application/json"}, text='{"foo": 1}', data={"foo": 1}
    )
    text2, _ = await svc._fetch_url_text("https://x/api")
    assert "foo" in text2

    # Undecodable JSON body -> also falls back to raw text.
    _HANDLER[0] = lambda url, headers: _Resp(
        200, headers={"content-type": "application/json"}, text="oops", data=None
    )
    text3, _ = await svc._fetch_url_text("https://x/api")
    assert text3 == "oops"


@pytest.mark.asyncio
async def test_fetch_html_with_embedded_workday_link(tmp_path: Path, patched):
    svc = _svc(tmp_path)
    page = (
        "<html><body>"
        '<a href="https://acme.wd5.myworkdayjobs.com/S/job/C/R-1/apply">Apply</a>'
        "</body></html>"
    )

    def handler(url, headers):
        if "wday/cxs" in url:
            return _Resp(
                200,
                headers={"content-type": "application/json"},
                data=_wd_payload("real content " * 80),
            )
        return _Resp(200, headers={"content-type": "text/html"}, text=page)

    _HANDLER[0] = handler
    text, hints = await svc._fetch_url_text("https://x/careers")
    assert "Engineer" in text
    assert hints["company"] == "Acme"


# ---------------------------------------------------------------------------
# Upload parsing through jd_ingest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_upload_docx(tmp_path: Path):
    svc = _svc(tmp_path)
    b64 = base64.b64encode(_docx_bytes("Senior Engineer", "Acme Inc")).decode()
    res = await svc.jd_ingest(source_type="upload", filename="jd.docx", content_base64=b64)
    assert res["jdChars"] > 0
    assert res["application"]["company"] == "Acme Inc"


@pytest.mark.asyncio
async def test_ingest_upload_pdf(tmp_path: Path):
    svc = _svc(tmp_path)
    b64 = base64.b64encode(b"junk (Cloud Engineer Role) (Acme Corp Inc)").decode()
    res = await svc.jd_ingest(source_type="upload", filename="jd.pdf", content_base64=b64)
    assert "Cloud Engineer Role" in res["application"]["jdText"]


@pytest.mark.asyncio
async def test_ingest_upload_doc_and_empty_placeholder(tmp_path: Path):
    svc = _svc(tmp_path)
    good = base64.b64encode(b"Staff Engineer at Globex Inc").decode()
    res = await svc.jd_ingest(source_type="upload", filename="role.doc", content_base64=good)
    assert "Globex" in res["application"]["jdText"]

    empty = base64.b64encode(b"\x00\x00\x01").decode()
    res2 = await svc.jd_ingest(source_type="upload", filename="blank.doc", content_base64=empty)
    assert "text extraction empty" in res2["application"]["jdText"]
