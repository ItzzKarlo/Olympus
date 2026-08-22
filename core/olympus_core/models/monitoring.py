from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from olympus_core.models.telemetry import StorageTelemetry, SystemTelemetry


class ProbeStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class ProbeState(BaseModel):
    status: ProbeStatus = ProbeStatus.UNKNOWN
    latency_ms: float | None = Field(default=None, ge=0)
    last_checked: datetime | None = None


class NetworkTargetState(ProbeState):
    id: str
    name: str


class NetworkState(BaseModel):
    gateway: ProbeState = Field(default_factory=ProbeState)
    dns: ProbeState = Field(default_factory=ProbeState)
    internet: ProbeState = Field(default_factory=ProbeState)
    https: ProbeState = Field(default_factory=ProbeState)
    targets: dict[str, NetworkTargetState] = Field(default_factory=dict)


class ServiceState(BaseModel):
    id: str
    name: str
    status: ProbeStatus = ProbeStatus.UNKNOWN
    latency_ms: float | None = Field(default=None, ge=0)
    last_checked: datetime | None = None
    last_changed: datetime | None = None


class CoreHostState(BaseModel):
    hostname: str
    platform: str
    observed_at: datetime
    system: SystemTelemetry
    storage: StorageTelemetry


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class OlympusEvent(BaseModel):
    id: str
    type: str
    severity: EventSeverity
    timestamp: datetime
    title: str
    message: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActiveAlert(BaseModel):
    id: str
    incident_key: str
    type: str
    severity: EventSeverity
    title: str
    message: str
    source: str
    started_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class RecoveryNotice(BaseModel):
    id: str
    incident_key: str
    type: str
    title: str
    message: str
    source: str
    recovered_at: datetime
    downtime_seconds: float = Field(ge=0)
    expires_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
