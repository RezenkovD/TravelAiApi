from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TravelRequestIn(BaseModel):
    text: str
    num_places: int = Field(default=4)
    exclude: str | None = None


class TravelRequestOut(TravelRequestIn):
    id: int
    created_at: datetime
    response_json: list[dict[str, Any]] = Field(default=[])

    class Config:
        from_attributes = True


class ExcludeUpdate(BaseModel):
    exclude: str
