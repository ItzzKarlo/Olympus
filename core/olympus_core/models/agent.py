from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from olympus_core.models.telemetry import (
    ActivityTelemetry,
    GpuTelemetry,
    NetworkTelemetry,
    StorageTelemetry,
    SystemTelemetry,
    TemperatureTelemetry,
)
from olympus_core.models.integrations import IntegrationSnapshot


class AgentHello(BaseModel):
    type: Literal["hello"]
    agent_id: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=64)
    platform_version: str = Field(min_length=1, max_length=128)
    agent_version: str = Field(min_length=1, max_length=32)
    public_key: str | None = Field(default=None, min_length=40, max_length=64)
    enrollment_token: str | None = Field(default=None, min_length=32, max_length=128)


class AgentAuthChallenge(BaseModel):
    type: Literal["auth_challenge"] = "auth_challenge"
    protocol: Literal["olympus-agent-auth-v1"] = "olympus-agent-auth-v1"
    challenge: str


class AgentAuthResponse(BaseModel):
    type: Literal["auth_response"]
    signature: str = Field(min_length=80, max_length=128)


class AgentEnrollmentRequired(BaseModel):
    type: Literal["enrollment_required"] = "enrollment_required"
    agent_id: str
    message: str = "Core requires device enrollment."


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
    storage: StorageTelemetry | None = None
    network: NetworkTelemetry | None = None
    temperatures: TemperatureTelemetry | None = None
    gpu: GpuTelemetry | None = None
    activity: ActivityTelemetry | None = None
    integrations: dict[str, IntegrationSnapshot] = Field(default_factory=dict)
