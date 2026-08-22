from dataclasses import asdict, dataclass
import base64
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
    public_key: bytes | None = None,
    enrollment_token: str | None = None,
) -> dict[str, str]:
    hello = {
        "type": "hello",
        "agent_id": agent_id,
        "hostname": socket.gethostname(),
        "platform": platform_name,
        "platform_version": platform_version or platform.release(),
        "agent_version": agent_version,
    }
    if public_key is not None:
        hello["public_key"] = encode_base64url(public_key)
    if enrollment_token:
        hello["enrollment_token"] = enrollment_token
    return hello


def encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_base64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def auth_payload(agent_id: str, challenge: bytes) -> bytes:
    return b"olympus-agent-auth-v1\0" + agent_id.encode("utf-8") + b"\0" + challenge


def parse_handshake(message: str) -> dict[str, Any]:
    payload: Any = json.loads(message)
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
        raise ValueError("Core returned an invalid authentication message")
    return payload


def validate_welcome(message: str, agent_id: str) -> None:
    payload = parse_handshake(message)
    if payload.get("type") != "welcome" or payload.get("agent_id") != agent_id:
        raise ValueError("Core returned an invalid welcome message")
