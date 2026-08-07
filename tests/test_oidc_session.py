from __future__ import annotations

from sprucer.adapters.oidc import sign_session, verify_session


def test_oidc_session_roundtrip():
    token = sign_session("secret", "user-123", ttl_seconds=60)
    assert verify_session("secret", token) == "user-123"
    assert verify_session("wrong", token) is None
