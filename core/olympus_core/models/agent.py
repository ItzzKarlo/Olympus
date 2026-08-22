from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from olympus_core.models.telemetry import ActivityTelemetry, SystemTelemetry


class AgentHello(BaseModel):
    type: Literal["hello"]
    agent_id: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=64)
    platform_version: str = Field(min_length=1, max_length=128)
    agent_version: str = Field(min_length=1, max_length=32)


class AgentWelcome(BaseModel):
    type: Literal["welcome"] = "welcome"
    agent_id: str


class RegisteredAgent(BaseModel):
    agent_id: str
    hostname: str
    platform: str
    platform_version: str
    agent_version: str

    online: bool
    connected_at: datetime
    last_seen: datetime
    system: SystemTelemetry | None = None
    activity: ActivityTelemetry | None = None
