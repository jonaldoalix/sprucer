from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx


class OidcClient:
    """Generic OpenID Connect authorization-code helper (Authentik, Auth0, Keycloak, …)."""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str = "openid profile email",
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self._discovery: dict[str, Any] | None = None

    async def discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        url = f"{self.issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            res = await client.get(url)
            if res.status_code >= 400:
                raise RuntimeError(f"OIDC discovery failed HTTP {res.status_code}: {res.text[:300]}")
            self._discovery = res.json()
        return self._discovery

    async def authorization_url(self, *, state: str) -> str:
        meta = await self.discovery()
        endpoint = meta.get("authorization_endpoint")
        if not endpoint:
            raise RuntimeError("OIDC discovery missing authorization_endpoint")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": self.scopes,
                "state": state,
            }
        )
        return f"{endpoint}?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        meta = await self.discovery()
        token_url = meta.get("token_endpoint")
        if not token_url:
            raise RuntimeError("OIDC discovery missing token_endpoint")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            res = await client.post(token_url, data=data)
            if res.status_code >= 400:
                raise RuntimeError(f"OIDC token exchange failed HTTP {res.status_code}: {res.text[:400]}")
            tokens = res.json()
        # Prefer userinfo when available
        userinfo_url = meta.get("userinfo_endpoint")
        access = tokens.get("access_token")
        if userinfo_url and access:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                ui = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access}"})
                if ui.status_code < 400:
                    info = ui.json()
                    tokens["userinfo"] = info
                    if not tokens.get("sub") and info.get("sub"):
                        tokens["sub"] = info["sub"]
        if not tokens.get("sub"):
            # decode id_token payload without verification for subject only (signature verified by TLS to IdP)
            id_token = str(tokens.get("id_token") or "")
            parts = id_token.split(".")
            if len(parts) >= 2:
                import base64
                import json

                pad = "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
                tokens["sub"] = payload.get("sub")
                tokens["userinfo"] = {**(tokens.get("userinfo") or {}), **payload}
        if not tokens.get("sub"):
            raise RuntimeError("OIDC token response missing subject")
        return tokens


def sign_session(secret: str, subject: str, *, ttl_seconds: int = 60 * 60 * 24 * 14) -> str:
    exp = int(time.time()) + ttl_seconds
    body = f"{subject}:{exp}"
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"oidc:{body}:{sig}"


def verify_session(secret: str, token: str) -> str | None:
    if not token.startswith("oidc:"):
        return None
    try:
        rest = token[len("oidc:") :]
        subject, exp_s, sig = rest.rsplit(":", 2)
        exp = int(exp_s)
    except Exception:
        return None
    if exp < int(time.time()):
        return None
    expect = hmac.new(secret.encode("utf-8"), f"{subject}:{exp}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    return subject


def new_state() -> str:
    return secrets.token_urlsafe(24)
