from __future__ import annotations

import pytest

from sprucer.security import (
    DEFAULT_DEV_PASSWORD,
    DEFAULT_SESSION_SECRET,
    validate_runtime_settings,
)
from sprucer.settings import Settings
from sprucer.ssrf import UnsafeUrlError, assert_public_http_url


def test_ssrf_blocks_localhost_and_private(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://127.0.0.1/secret", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://10.0.0.5/x", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://169.254.169.254/latest", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("http://localhost/admin", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("ftp://example.com/x", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("https://user:pass@example.com/x", resolve=False)
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url("", resolve=False)

    # Public hostname without DNS resolve
    assert assert_public_http_url("https://example.com/jobs/1", resolve=False).startswith("https://")

    # DNS that resolves to private must fail
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(None, None, None, None, ("10.1.2.3", port))]

    monkeypatch.setattr("sprucer.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeUrlError, match="private"):
        assert_public_http_url("https://evil.example/jobs")


def test_validate_runtime_settings_refuses_exposed_dev():
    settings = Settings(
        host="0.0.0.0",
        auth_mode="dev",
        dev_password="unique-lab-pass",
        session_secret="unique-session-secret-value",
        allow_insecure_dev=False,
    )
    with pytest.raises(RuntimeError, match="Refusing to start"):
        validate_runtime_settings(settings)

    settings.allow_insecure_dev = True
    msgs = validate_runtime_settings(settings)
    assert any("ALLOW_INSECURE_DEV" in m for m in msgs)


def test_validate_runtime_settings_warns_on_defaults():
    settings = Settings(
        host="127.0.0.1",
        auth_mode="dev",
        dev_password=DEFAULT_DEV_PASSWORD,
        session_secret=DEFAULT_SESSION_SECRET,
    )
    msgs = validate_runtime_settings(settings)
    assert any("SESSION_SECRET" in m for m in msgs)
    assert any("DEV_PASSWORD" in m for m in msgs)


def test_validate_api_key_and_oidc_requirements():
    with pytest.raises(RuntimeError, match="API_KEYS"):
        validate_runtime_settings(Settings(auth_mode="api_key", api_keys="", session_secret="x" * 24))
    with pytest.raises(RuntimeError, match="OIDC"):
        validate_runtime_settings(
            Settings(auth_mode="oidc", oidc_issuer="", oidc_client_id="", session_secret="x" * 24)
        )
