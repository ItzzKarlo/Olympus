from dataclasses import asdict, dataclass
import json
import platform
import socket
from typing import Any


@dataclass(frozen=True, slots=True)
class GameObservation:
    id: str
    name: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ActivityObservation:
    mode: str
    application: str | None = None
    process_name: str | None = None
    game: GameObservation | None = None
    fps: float | None = None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {key: item for key, item in value.items() if item is not None}


def build_hello(
    agent_id: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
) -> dict[str, str]:
    return {
        "type": "hello",
        "agent_id": agent_id,
        "hostname": socket.gethostname(),
        "platform": platform_name,
        "platform_version": platform_version or platform.release(),
        "agent_version": agent_version,
    }


def validate_welcome(message: str, agent_id: str) -> None:
    payload: Any = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("Core returned a non-object welcome message")
    if payload.get("type") != "welcome" or payload.get("agent_id") != agent_id:
        raise ValueError("Core returned an invalid welcome message")
