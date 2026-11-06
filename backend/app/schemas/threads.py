import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, StringConstraints

from app.models.enums import ThreadProcessingStatus
from app.schemas.common import ORMModel
from app.schemas.sources import SourceRead

ExternalId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ThreadRead(ORMModel):
    id: uuid.UUID
    communication_source_id: uuid.UUID
    external_thread_id: str
    title: str | None
    started_at: datetime | None
    last_message_at: datetime | None
    processing_status: ThreadProcessingStatus
    created_at: datetime
    message_count: int = 0


class ThreadDetail(ThreadRead):
    source: SourceRead


class MessageRead(ORMModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    external_message_id: str
    author_external_id: str
    author_display_name: str | None
    content: str
    sent_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    source_url: str | None
    created_at: datetime


class ThreadIngest(BaseModel):
    """A thread as delivered by a connector or the simulated feed (internal use)."""

    external_thread_id: ExternalId
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class MessageIngest(BaseModel):
    """A message as delivered by a connector or the simulated feed (internal use).

    Timestamps must be timezone-aware so ordering is unambiguous across sources.
    """

    external_message_id: ExternalId
    author_external_id: ExternalId
    author_display_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    content: Annotated[str, StringConstraints(min_length=1)]
    sent_at: AwareDatetime
    edited_at: AwareDatetime | None = None
    deleted_at: AwareDatetime | None = None
    source_url: Annotated[str, StringConstraints(max_length=2048)] | None = None
