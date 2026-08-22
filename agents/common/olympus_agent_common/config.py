from dataclasses import dataclass
import os
from pathlib import Path
import socket
import tomllib
from typing import Any, Mapping
from urllib.parse import urlsplit

from olympus_agent_common.paths import AgentPaths


DEFAULT_CORE_WS = "ws://127.0.0.1:8000/ws/agents"


def validate_display_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 255 or any(not character.isprintable() for character in name):
        raise ValueError("Display name must contain between 1 and 255 printable characters")
    return name


def validate_core_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"ws", "wss"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Core URL must be a ws:// or wss:// URL without credentials, query, or fragment")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("Core URL contains an invalid port") from error
    return candidate


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw_value = env.get(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _port(env: Mapping[str, str], name: str, default: int) -> int:
    raw_value = env.get(name)
    try:
        value = int(raw_value) if raw_value is not None else default
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= value <= 65_535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return value


def read_config_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            value = tomllib.load(file)
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Agent configuration is invalid: {error}") from error
    return value


def write_config_file(path: Path, core_url: str, display_name: str) -> None:
    validated_url = validate_core_url(core_url)
    name = validate_display_name(display_name)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    escaped_url = validated_url.replace("\\", "\\\\").replace('"', '\\"')
    escaped_name = name.replace("\\", "\\\\").replace('"', '\\"')
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        f'[core]\nurl = "{escaped_url}"\n\n[agent]\ndisplay_name = "{escaped_name}"\n',
        encoding="utf-8",
    )
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    core_ws_url: str
    telemetry_interval: float
    reconnect_delay: float
    identity_path: Path
    game_background_grace_seconds: float = 15.0
    integration_port: int = 38_765
    integration_stale_seconds: float = 5.0
    key_path: Path | None = None
    display_name: str | None = None
    config_path: Path | None = None

    @classmethod
    def from_sources(
        cls,
        paths: AgentPaths,
        *,
        core_url_override: str | None = None,
        display_name_override: str | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "AgentConfig":
        env = environ if environ is not None else os.environ
        data = read_config_file(paths.config_path)
        core = data.get("core") if isinstance(data.get("core"), dict) else {}
        agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
        configured_url = core.get("url") if isinstance(core.get("url"), str) else None
        configured_name = agent.get("display_name") if isinstance(agent.get("display_name"), str) else None
        url = (
            core_url_override
            or env.get("OLYMPUS_CORE_URL")
            or env.get("OLYMPUS_CORE_WS")
            or configured_url
            or DEFAULT_CORE_WS
        )
        name = validate_display_name(
            display_name_override
            or env.get("OLYMPUS_AGENT_DISPLAY_NAME")
            or configured_name
            or socket.gethostname()
        )
        return cls(
            core_ws_url=validate_core_url(url),
            telemetry_interval=_positive_float(env, "OLYMPUS_TELEMETRY_INTERVAL", 2.0),
            reconnect_delay=_positive_float(env, "OLYMPUS_RECONNECT_DELAY", 3.0),
            identity_path=Path(env.get("OLYMPUS_AGENT_ID_PATH", str(paths.identity_path))).expanduser(),
            game_background_grace_seconds=_positive_float(
                env, "OLYMPUS_GAME_BACKGROUND_GRACE_SECONDS", 15.0
            ),
            integration_port=_port(env, "OLYMPUS_INTEGRATION_PORT", 38_765),
            integration_stale_seconds=_positive_float(
                env, "OLYMPUS_INTEGRATION_STALE_SECONDS", 5.0
            ),
            key_path=Path(env.get("OLYMPUS_AGENT_KEY_PATH", str(paths.key_path))).expanduser(),
            display_name=name,
            config_path=paths.config_path,
        )

    @classmethod
    def from_environment(cls, default_identity_path: Path) -> "AgentConfig":
        # Compatibility for platform wrappers and existing integrations.
        paths = AgentPaths(
            platform="legacy",
            config_dir=default_identity_path.parent,
            data_dir=default_identity_path.parent,
            log_dir=default_identity_path.parent / "logs",
            config_path=default_identity_path.parent / "agent.toml",
            identity_path=default_identity_path,
            key_path=default_identity_path.with_name("agent-key.pem"),
            lock_path=default_identity_path.with_name("agent.lock"),
            autostart_path=default_identity_path.with_name("autostart"),
        )
        return cls.from_sources(paths)
