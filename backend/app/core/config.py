"""Typed application settings loaded from environment variables and `.env`."""

from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Environments in which development-only features (write endpoints, seeding) are allowed.
DEVELOPMENT_ENVIRONMENTS = frozenset({"development", "test"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Elisa Echo API"
    environment: str = "development"
    api_prefix: str = "/api"

    # Comma-separated list in the environment, e.g.
    # CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # PostgreSQL (Tiger Data). Optional so the API still starts without a database.
    # Accepts postgres://, postgresql:// or postgresql+psycopg:// URLs.
    database_url: SecretStr | None = None
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_connect_timeout_seconds: int = 5

    # Phase 3. Optional for now.
    gemini_api_key: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def is_development(self) -> bool:
        return self.environment in DEVELOPMENT_ENVIRONMENTS


@lru_cache
def get_settings() -> Settings:
    return Settings()
