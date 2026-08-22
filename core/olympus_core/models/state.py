from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from olympus_core.models.media import MediaState
from olympus_core.models.monitoring import (
    ActiveAlert,
    CoreHostState,
    NetworkState,
    RecoveryNotice,
    ServiceState,
)
from olympus_core.models.telemetry import (
    ActivityMode,
    ActivityTelemetry,
    GpuTelemetry,
    GameInfo,
    NetworkTelemetry,
    StorageTelemetry,
    SystemTelemetry,
    TemperatureTelemetry,
)
from olympus_core.models.integrations import IntegrationObserver
from olympus_core.models.minecraft import MinecraftState
from olympus_core.models.weather import WeatherState
from olympus_core.models.calendar import CalendarState
from olympus_core.models.time_policy import TimePolicyState


class MachineState(BaseModel):
    agent_id: str
    hostname: str
    platform: str
    platform_version: str
    online: bool
    last_seen: datetime
    system: SystemTelemetry | None
    storage: StorageTelemetry | None
    network: NetworkTelemetry | None
    temperatures: TemperatureTelemetry | None
    gpu: GpuTelemetry | None
    activity: ActivityTelemetry | None


class GamingIntegration(BaseModel):
    type: str
    available: bool
    connected: bool
    last_seen: datetime
    observer: IntegrationObserver


class GamingState(BaseModel):
    game: GameInfo
    session_started_at: datetime
    fps: float | None = None
    integration: GamingIntegration | None = None
    minecraft: MinecraftState | None = None


class OlympusState(BaseModel):
    mode: ActivityMode
    active_device: str | None
    machines: dict[str, MachineState]
    timezone: str = "UTC"
    weather: WeatherState | None = None
    calendar: CalendarState | None = None
    time_policy: TimePolicyState
    media: MediaState | None = None
    core_host: CoreHostState | None = None
    network: NetworkState | None = None
    services: dict[str, ServiceState] = Field(default_factory=dict)
    alerts: list[ActiveAlert] = Field(default_factory=list)
    recoveries: list[RecoveryNotice] = Field(default_factory=list)
    gaming: GamingState | None = None


class DisplayState(OlympusState):
    type: Literal["state"] = "state"
    generated_at: datetime
