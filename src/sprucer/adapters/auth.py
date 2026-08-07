from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request, Response

from sprucer.adapters.oidc import OidcClient, sign_session, verify_session


@dataclass
class AuthContext:
    subject: str
    mode: str


class AuthAdapter(Protocol):
    mode: str

    def authenticate(self, request: Request) -> AuthContext: ...

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext: ...

    def logout(self, response: Response) -> None: ...

    def public_config(self) -> dict: ...


class NoneAuth:
    mode = "none"

    def authenticate(self, request: Request) -> AuthContext:
        return AuthContext(subject="anonymous", mode=self.mode)

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        return AuthContext(subject="anonymous", mode=self.mode)

    def logout(self, response: Response) -> None:
        return None

    def public_config(self) -> dict:
        return {"mode": self.mode, "dev_login": False, "oidc_login": False}


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
            path="/",
        )
        return AuthContext(subject="dev", mode=self.mode)

    def logout(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name, path="/")

    def public_config(self) -> dict:
        return {"mode": self.mode, "dev_login": True, "oidc_login": False}


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

    def public_config(self) -> dict:
        return {"mode": self.mode, "dev_login": False, "oidc_login": False, "api_key": True}


class OidcAuth:
    mode = "oidc"
    cookie_name = "sprucer_session"
    state_cookie = "sprucer_oidc_state"

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        session_secret: str,
        api_keys: set[str] | None = None,
        post_login_redirect: str = "http://127.0.0.1:3737/applications",
    ) -> None:
        if not issuer or not client_id:
            raise RuntimeError("OIDC requires SPRUCER_OIDC_ISSUER and SPRUCER_OIDC_CLIENT_ID")
        self.client = OidcClient(
            issuer=issuer,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        self.session_secret = session_secret
        self.api_keys = api_keys or set()
        self.redirect_uri = redirect_uri
        self.post_login_redirect = post_login_redirect

    def authenticate(self, request: Request) -> AuthContext:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token in self.api_keys:
                return AuthContext(subject="api-key", mode="api_key")
        cookie = request.cookies.get(self.cookie_name)
        if cookie:
            sub = verify_session(self.session_secret, cookie)
            if sub:
                return AuthContext(subject=sub, mode=self.mode)
        raise HTTPException(
            status_code=401,
            detail="OIDC session required (or API key). Complete login via the web app.",
        )

    def login(self, response: Response, *, password: str | None = None, api_key: str | None = None) -> AuthContext:
        if api_key and api_key in self.api_keys:
            return AuthContext(subject="api-key", mode="api_key")
        raise HTTPException(status_code=400, detail="Use OIDC login (GET /v1/auth/oidc/start)")

    def logout(self, response: Response) -> None:
        response.delete_cookie(self.cookie_name, path="/")
        response.delete_cookie(self.state_cookie, path="/")

    def public_config(self) -> dict:
        return {
            "mode": self.mode,
            "dev_login": False,
            "oidc_login": True,
            "oidc_start": "/v1/auth/oidc/start",
            "issuer": self.client.issuer,
        }

    def establish_session(self, response: Response, subject: str) -> AuthContext:
        token = sign_session(self.session_secret, subject)
        response.set_cookie(
            self.cookie_name,
            token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 14,
            path="/",
        )
        return AuthContext(subject=subject, mode=self.mode)


def create_auth(
    *,
    mode: str,
    dev_password: str,
    session_secret: str,
    api_keys: set[str],
    oidc_issuer: str = "",
    oidc_client_id: str = "",
    oidc_client_secret: str = "",
    oidc_redirect_uri: str = "http://127.0.0.1:3737/v1/auth/oidc/callback",
    oidc_post_login_redirect: str = "http://127.0.0.1:3737/applications",
) -> AuthAdapter:
    mode = (mode or "dev").strip().lower()
    secret = session_secret or secrets.token_hex(16)
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
            redirect_uri=oidc_redirect_uri,
            session_secret=secret,
            api_keys=api_keys,
            post_login_redirect=oidc_post_login_redirect,
        )
    return DevAuth(password=dev_password or "sprucer-dev", secret=secret)
