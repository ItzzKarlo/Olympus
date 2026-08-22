from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntegrationObserver(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)


class IntegrationSnapshot(BaseModel):
    available: bool
    connected: bool
    last_seen: datetime
    observer: IntegrationObserver
    payload: dict[str, Any] | None = None


class AgentIntegrationState(BaseModel):
    type: Literal["integration_state"]
    integration: str = Field(min_length=1, max_length=128)
    available: bool = True
    observer: IntegrationObserver
    observed_at: datetime
    payload: dict[str, Any]


class AgentIntegrationEvent(BaseModel):
    type: Literal["integration_event"]
    integration: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=192)
    observed_at: datetime
    payload: dict[str, Any]
