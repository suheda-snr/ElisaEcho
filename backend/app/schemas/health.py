from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["connected", "not_configured", "misconfigured", "unreachable"]
    # Whether the pgvector extension is installed (only known when connected).
    pgvector: bool | None = None
    # Human-readable, secret-free explanation when unavailable.
    detail: str | None = None
