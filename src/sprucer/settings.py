from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPRUCER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8787
    database_url: str = "sqlite:///./data/sprucer.db"
    auth_mode: str = "dev"
    dev_password: str = "sprucer-dev"
    api_keys: str = ""
    session_secret: str = "sprucer-dev-session-change-me"
    # Lab override: allow auth_mode=dev|none when binding 0.0.0.0 (never for public internet).
    allow_insecure_dev: bool = False
    # Set true behind HTTPS so session cookies get the Secure flag.
    cookie_secure: bool = False
    # Set false in production if you do not want /docs and /redoc public.
    docs_enabled: bool = True

    llm_url: str = "http://127.0.0.1:4000/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-coder"

    # Demo mode: self-contained, no external calls or costs. Uses the offline
    # DemoLlm, per-session ephemeral vaults, and disables outbound URL ingest.
    demo: bool = False
    demo_ttl_hours: int = 24
    # Allow outbound job-URL fetches during ingest (disabled by demo compose).
    ingest_url_enabled: bool = True
    # Let a visitor supply their own OpenAI-compatible provider per request.
    byok_enabled: bool = False
    # Optional allowlist of provider hosts for BYO keys (comma-separated). Empty = any public https host.
    byok_allowed_hosts: str = ""

    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://127.0.0.1:3737/v1/auth/oidc/callback"
    oidc_post_login_redirect: str = "http://127.0.0.1:3737/applications"

    cors_origins: str = "http://127.0.0.1:3737,http://localhost:3737"

    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def byok_allowed_host_set(self) -> set[str]:
        return {h.strip().lower() for h in self.byok_allowed_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
