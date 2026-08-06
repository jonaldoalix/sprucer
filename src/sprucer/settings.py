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

    llm_url: str = "http://127.0.0.1:4000/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-coder"

    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://127.0.0.1:3737/api/auth/callback"

    cors_origins: str = "http://127.0.0.1:3737,http://localhost:3737"

    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
