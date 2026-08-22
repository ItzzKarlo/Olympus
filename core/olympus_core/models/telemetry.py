from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ActivityMode(str, Enum):
    IDLE = "idle"
    DEVELOPMENT = "development"
    GAMING = "gaming"
    MEDIA = "media"
    UNKNOWN = "unknown"


class SystemTelemetry(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    ram_used_bytes: int = Field(ge=0)
    ram_total_bytes: int = Field(gt=0)


class ActivityTelemetry(BaseModel):
    mode: ActivityMode
    application: str | None = None
    process_name: str | None = None


class AgentTelemetry(BaseModel):
    type: Literal["telemetry"]
    system: SystemTelemetry
    activity: ActivityTelemetry
