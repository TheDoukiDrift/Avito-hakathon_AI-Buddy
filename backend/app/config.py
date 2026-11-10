"""Application configuration (env-driven, 12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All knobs come from the environment; defaults keep the app runnable offline."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ai-buddy"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./ai_buddy.db"
    secret_key: str = "dev-secret-change-me"
    token_ttl_seconds: int = 60 * 60 * 24

    redis_url: str = "redis://localhost:6379/0"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    mcp_url: str = "http://localhost:8001/mcp"

    cors_origins: str = "*"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        """Accept the URLs people actually paste into docker-compose."""
        if value.startswith("postgres://"):
            value = "postgresql+psycopg://" + value[len("postgres://") :]
        elif value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        elif value.startswith("sqlite:///"):
            value = "sqlite+aiosqlite:///" + value[len("sqlite:///") :]
        return value

    @property
    def llm_enabled(self) -> bool:
        """A real LLM is used only when both a base URL and a key are configured."""
        return bool(self.llm_base_url.strip() and self.llm_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Tests flip env vars between runs."""
    get_settings.cache_clear()
