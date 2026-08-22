from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_CORE_WS = "ws://127.0.0.1:8000/ws/agents"


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _port(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    try:
        value = int(raw_value) if raw_value is not None else default
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= value <= 65_535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return value


@dataclass(frozen=True, slots=True)
class AgentConfig:
    core_ws_url: str
    telemetry_interval: float
    reconnect_delay: float
    identity_path: Path
    game_background_grace_seconds: float = 15.0
    integration_port: int = 38_765
    integration_stale_seconds: float = 5.0

    @classmethod
    def from_environment(cls, default_identity_path: Path) -> "AgentConfig":
        return cls(
            core_ws_url=os.getenv("OLYMPUS_CORE_WS", DEFAULT_CORE_WS),
            telemetry_interval=_positive_float("OLYMPUS_TELEMETRY_INTERVAL", 2.0),
            reconnect_delay=_positive_float("OLYMPUS_RECONNECT_DELAY", 3.0),
            identity_path=Path(
                os.getenv("OLYMPUS_AGENT_ID_PATH", str(default_identity_path))
            ).expanduser(),
            game_background_grace_seconds=_positive_float(
                "OLYMPUS_GAME_BACKGROUND_GRACE_SECONDS", 15.0
            ),
            integration_port=_port("OLYMPUS_INTEGRATION_PORT", 38_765),
            integration_stale_seconds=_positive_float(
                "OLYMPUS_INTEGRATION_STALE_SECONDS", 5.0
            ),
        )
