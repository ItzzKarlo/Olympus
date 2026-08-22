from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from olympus_core.models.monitoring import EventSeverity
from olympus_core.models.football import FootballDisplayEvent


class GameplayEventSource(BaseModel):
    agent_id: str
    integration: str


class GameplayEvent(BaseModel):
    id: str
    type: str
    category: Literal["gameplay"] = "gameplay"
    severity: EventSeverity = EventSeverity.INFO
    timestamp: datetime
    source: GameplayEventSource
    payload: dict[str, Any] = Field(default_factory=dict)


class DisplayEventMessage(BaseModel):
    type: Literal["event"] = "event"
    event: GameplayEvent | FootballDisplayEvent
