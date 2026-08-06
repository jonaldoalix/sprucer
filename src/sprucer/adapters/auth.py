from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request, Response


@dataclass
class AuthContext:
    subject: str
    mode: str


class AuthAdapter(Protocol):
    mode: str

    def authenticate(self, request: Request) -> AuthContext: ...

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext: ...

    def logout(self, response: Response) -> None: ...


class NoneAuth:
    mode = "none"

    def authenticate(self, request: Request) -> AuthContext:
        return AuthContext(subject="anonymous", mode=self.mode)

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        return AuthContext(subject="anonymous", mode=self.mode)

    def logout(self, response: Response) -> None:
        return None


class DevAuth:
    """Shared-password local auth. Unsafe for internet exposure."""

    mode = "dev"
    cookie_name = "sprucer_session"

    def __init__(self, *, password: str, secret: str) -> None:
        self.password = password
        self.secret = secret.encode("utf-8")

    def _token(self) -> str:
        digest = hmac.new(self.secret, self.password.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"dev:{digest}"

    def authenticate(self, request: Request) -> AuthContext:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if hmac.compare_digest(token, self._token()) or token == self.password:
                return AuthContext(subject="dev", mode=self.mode)
        cookie = request.cookies.get(self.cookie_name)
        if cookie and hmac.compare_digest(cookie, self._token()):
            return AuthContext(subject="dev", mode=self.mode)
        raise HTTPException(status_code=401, detail="Authentication required")

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        if not password or not hmac.compare_digest(password, self.password):
            raise HTTPException(status_code=401, detail="Invalid password")
        token = self._token()
        response.set_cookie(
            self.cookie_name,
            token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 14,
        )
        return AuthContext(subject="dev", mode=self.mode)

    def logout(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name)


class ApiKeyAuth:
    mode = "api_key"

    def __init__(self, *, keys: set[str]) -> None:
        self.keys = keys

    def authenticate(self, request: Request) -> AuthContext:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Bearer API key required")
        token = auth.split(" ", 1)[1].strip()
        if token not in self.keys:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return AuthContext(subject="api-key", mode=self.mode)

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        if not api_key or api_key not in self.keys:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return AuthContext(subject="api-key", mode=self.mode)

    def logout(self, response: Response) -> None:
        return None


class OidcAuth:
    """Placeholder gate: validates that OIDC is configured; browser flow lives in the web app."""

    mode = "oidc"

    def __init__(self, *, issuer: str, client_id: str, client_secret: str, api_keys: set[str] | None = None) -> None:
        if not issuer or not client_id:
            raise RuntimeError("OIDC requires SPRUCER_OIDC_ISSUER and SPRUCER_OIDC_CLIENT_ID")
        self.issuer = issuer
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_keys = api_keys or set()

    def authenticate(self, request: Request) -> AuthContext:
        # Headless: allow API keys alongside OIDC browser sessions proxied by the web app.
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token in self.api_keys:
                return AuthContext(subject="api-key", mode="api_key")
            # Web may forward a session token; for v0 accept opaque trusted header from same-origin proxy.
            if request.headers.get("x-sprucer-oidc-sub"):
                return AuthContext(subject=request.headers["x-sprucer-oidc-sub"], mode=self.mode)
        if request.headers.get("x-sprucer-oidc-sub"):
            return AuthContext(subject=request.headers["x-sprucer-oidc-sub"], mode=self.mode)
        raise HTTPException(
            status_code=401,
            detail="OIDC session required (or API key). Complete login via the web app.",
        )

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        raise HTTPException(status_code=400, detail="Use the web OIDC login flow")

    def logout(self, response: Response) -> None:
        return None


def create_auth(
    *,
    mode: str,
    dev_password: str,
    session_secret: str,
    api_keys: set[str],
    oidc_issuer: str = "",
    oidc_client_id: str = "",
    oidc_client_secret: str = "",
) -> AuthAdapter:
    mode = (mode or "dev").strip().lower()
    if mode == "none":
        return NoneAuth()
    if mode == "api_key":
        if not api_keys:
            raise RuntimeError("SPRUCER_API_KEYS required when auth_mode=api_key")
        return ApiKeyAuth(keys=api_keys)
    if mode == "oidc":
        return OidcAuth(
            issuer=oidc_issuer,
            client_id=oidc_client_id,
            client_secret=oidc_client_secret,
            api_keys=api_keys,
        )
    # default / dev
    secret = session_secret or secrets.token_hex(16)
    return DevAuth(password=dev_password or "sprucer-dev", secret=secret)
