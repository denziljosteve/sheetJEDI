"""Application configuration via environment variables (prefix: SHEETJEDI_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="SHEETJEDI_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: str = Field(default="development")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="sqlite:///./data/sheetjedi.db")

    secret_key: str = Field(default="")

    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    max_upload_mb: int = Field(default=10)
    upload_retention_minutes: int = Field(default=60)

    history_enabled: bool = Field(default=True)

    provider_timeout_seconds: float = Field(default=60.0)
    model_cache_ttl_seconds: int = Field(default=900)

    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=30)

    @field_validator("env")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
