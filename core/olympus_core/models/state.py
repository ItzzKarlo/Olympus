from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from olympus_core.models.media import MediaState
from olympus_core.models.telemetry import ActivityMode, ActivityTelemetry, SystemTelemetry


class MachineState(BaseModel):
    agent_id: str
    hostname: str
    platform: str
    platform_version: str
    online: bool
    last_seen: datetime
    system: SystemTelemetry | None
    activity: ActivityTelemetry | None


class OlympusState(BaseModel):
    mode: ActivityMode
    active_device: str | None
    machines: dict[str, MachineState]
    media: MediaState | None = None


class DisplayState(OlympusState):
    type: Literal["state"] = "state"
    generated_at: datetime
