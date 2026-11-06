import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import SourceType
from app.schemas.common import ORMModel


class SourceCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    source_type: SourceType
    external_source_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    enabled: bool = True


class SourceRead(ORMModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    external_source_id: str
    enabled: bool
    created_at: datetime
