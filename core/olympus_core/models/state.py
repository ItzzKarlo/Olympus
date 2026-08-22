from pydantic import BaseModel

from olympus_core.models.telemetry import ActivityMode, ActivityTelemetry, SystemTelemetry


class MachineState(BaseModel):
    hostname: str
    online: bool
    system: SystemTelemetry | None
    activity: ActivityTelemetry | None


class OlympusState(BaseModel):
    mode: ActivityMode
    active_device: str | None
    machines: dict[str, MachineState]
