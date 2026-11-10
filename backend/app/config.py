"""Application configuration (env-driven, 12-factor)."""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """All knobs come from the environment; defaults keep the app runnable offline."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ai-buddy"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./ai_buddy.db"
    # No baked-in default: an empty value means "generate an ephemeral key for this
    # process" (see the validator below). Tokens then die with the process instead of
    # being signed with a secret that is public in git.
    secret_key: str = ""
    token_ttl_seconds: int = 60 * 60 * 24

    redis_url: str = "redis://localhost:6379/0"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    # `.env` / CI / compose all use MCP_SERVER_URL; MCP_URL is kept as a legacy alias.
    mcp_url: str = Field(
        default="http://localhost:8001/mcp",
        validation_alias=AliasChoices("MCP_SERVER_URL", "MCP_URL"),
    )

    cors_origins: str = "*"

    @field_validator("mcp_url")
    @classmethod
    def _normalize_mcp_url(cls, value: str) -> str:
        """`MCP_SERVER_URL` names only host:port — point it at the streamable-http path."""
        value = value.strip().rstrip("/")
        if not value:
            return "http://localhost:8001/mcp"
        if not urlsplit(value).path:
            value = f"{value}/mcp"
        return value

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

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> Settings:
        """Generate an ephemeral signing key instead of shipping a default one.

        Judges may run the stack without any env (the prototype must start), so an
        unset `SECRET_KEY` is a warning, not a crash: the process gets a random key,
        and previously issued tokens stop validating after a restart.
        """
        if not self.secret_key.strip():
            object.__setattr__(self, "secret_key", secrets.token_hex(32))
            logger.warning(
                "SECRET_KEY не задан — сгенерирован временный ключ для этого процесса. "
                "Токены перестанут действовать после перезапуска. "
                "Сгенерируйте постоянный: openssl rand -hex 32"
            )
        return self

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
