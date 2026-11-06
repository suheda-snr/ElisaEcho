from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for response models built from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """A page of results with the total count for pagination controls."""

    items: list[T]
    total: int
    limit: int
    offset: int
