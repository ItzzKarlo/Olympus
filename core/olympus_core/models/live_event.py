from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LiveEvent(BaseModel):
    """Small future boundary for structured events that outrank generic News."""

    id: str
    type: str
    title: str
    status: str
    started_at: datetime | None = None
    updated_at: datetime
    provider: str
    summary: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
