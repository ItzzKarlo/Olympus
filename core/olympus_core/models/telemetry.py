from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from olympus_core.models.integrations import IntegrationSnapshot


class ActivityMode(str, Enum):
    IDLE = "idle"
    NIGHT = "night"
    MATCHDAY = "matchday"
    NEWS = "news"
    DEVELOPMENT = "development"
    GAMING = "gaming"
    MEDIA = "media"
    UNKNOWN = "unknown"


class SystemTelemetry(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    ram_used_bytes: int = Field(ge=0)
    ram_total_bytes: int = Field(gt=0)
    uptime_seconds: float | None = Field(default=None, ge=0)


class StorageTelemetry(BaseModel):
    root_used_percent: float = Field(ge=0, le=100)
    root_free_bytes: int = Field(ge=0)
    root_total_bytes: int = Field(gt=0)


class NetworkTelemetry(BaseModel):
    bytes_sent: int = Field(ge=0)
    bytes_received: int = Field(ge=0)


class TemperatureTelemetry(BaseModel):
    cpu_celsius: float | None = None
    gpu_celsius: float | None = None


class GpuTelemetry(BaseModel):
    name: str
    utilization_percent: float | None = Field(default=None, ge=0, le=100)
    memory_used_bytes: int | None = Field(default=None, ge=0)
    memory_total_bytes: int | None = Field(default=None, gt=0)
    temperature_celsius: float | None = None


class GameInfo(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class ActivityTelemetry(BaseModel):
    mode: ActivityMode
    application: str | None = None
    process_name: str | None = None
    game: GameInfo | None = None
    fps: float | None = Field(default=None, gt=0)
class AgentTelemetry(BaseModel):
    type: Literal["telemetry"]
    system: SystemTelemetry
    storage: StorageTelemetry | None = None
    network: NetworkTelemetry | None = None
    temperatures: TemperatureTelemetry | None = None
    gpu: GpuTelemetry | None = None
    activity: ActivityTelemetry
    integrations: dict[str, IntegrationSnapshot] | None = None
