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

    # Google Gemini (knowledge discovery). Optional: without a key the API runs,
    # but thread analysis reports "Gemini not configured" instead of guessing.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = 60.0
    # Total attempts per analysis request, including the first (bounded retries).
    gemini_max_attempts: int = 3
    # Embeddings for semantic search. Stored and query vectors always use the same model
    # and the database dimension (768). Supported families: gemini-embedding-2 (task given
    # as text prefix) and gemini-embedding-001 (task_type parameter).
    gemini_embedding_model: str = "gemini-embedding-2"

    # Slack (Socket Mode). The slack-worker service connects only when SLACK_ENABLED=true and
    # both tokens are set. Tokens never leave the backend.
    slack_enabled: bool = False
    slack_bot_token: SecretStr | None = None  # xoxb-...
    slack_app_token: SecretStr | None = None  # xapp-... (connections:write)
    # Only needed for HTTP Events API request verification; Socket Mode does not use it.
    slack_signing_secret: SecretStr | None = None
    # Optional bootstrap allowlist: channel IDs to enable for monitoring at worker start.
    slack_channel_ids: Annotated[list[str], NoDecode] = []

    # Hybrid search.
    # Semantic matches are kept only if cosine similarity >= this floor AND within the margin
    # of the best match. Calibrated on the demo data with gemini-embedding-2 (unrelated
    # queries scored <= 0.62, relevant top hits >= 0.68); re-check after changing models.
    search_min_similarity: float = 0.65
    search_similarity_margin: float = 0.06
    # Candidates fetched per retriever before rank fusion.
    search_candidate_pool: int = 20

    # Discovery pipeline (in-process, development MVP).
    # Wait this long after the last message in a thread before analyzing it, so a
    # burst of messages becomes one Gemini call. Keep it above the per-thread message
    # gap of the simulated feed (interval x number of interleaved threads).
    discovery_debounce_seconds: float = 12.0
    discovery_max_concurrent_analyses: int = 2
    # Delay between simulated messages.
    simulation_message_interval_seconds: float = 2.0

    @field_validator("cors_origins", "slack_channel_ids", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator(
        "database_url", "gemini_api_key", "slack_bot_token", "slack_app_token", "slack_signing_secret",
        mode="before",
    )
    @classmethod
    def empty_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def slack_configured(self) -> bool:
        return self.slack_enabled and self.slack_bot_token is not None and self.slack_app_token is not None

    @property
    def is_development(self) -> bool:
        return self.environment in DEVELOPMENT_ENVIRONMENTS


@lru_cache
def get_settings() -> Settings:
    return Settings()
