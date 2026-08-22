from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AgentPaths:
    platform: str
    config_dir: Path
    data_dir: Path
    log_dir: Path
    config_path: Path
    identity_path: Path
    key_path: Path
    lock_path: Path
    autostart_path: Path
    legacy_identity_path: Path | None = None
    legacy_key_path: Path | None = None


def platform_name(value: str | None = None) -> str:
    current = value or sys.platform
    if current.startswith("win"):
        return "windows"
    if current == "darwin" or current == "macos":
        return "macos"
    if current.startswith("linux"):
        return "linux"
    raise RuntimeError(f"Unsupported Olympus Agent platform: {current}")


def agent_paths(
    value: str | None = None,
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AgentPaths:
    platform = platform_name(value)
    env = environ if environ is not None else os.environ
    user_home = (home or Path.home()).expanduser()
    if platform == "windows":
        roaming = Path(env.get("APPDATA", user_home / "AppData" / "Roaming"))
        local = Path(env.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
        config_dir = roaming / "Olympus"
        data_dir = local / "Olympus"
        autostart = config_dir / "OlympusAgentTask.xml"
        legacy_identity = data_dir / "agent-id"
        legacy_key = data_dir / "agent-key.pem"
    elif platform == "macos":
        config_dir = user_home / "Library" / "Application Support" / "Olympus"
        data_dir = config_dir
        autostart = user_home / "Library" / "LaunchAgents" / "com.itzkarlo.olympus.agent.plist"
        legacy_identity = user_home / ".olympus" / "agent-id"
        legacy_key = user_home / ".olympus" / "agent-key.pem"
    else:
        xdg_config = Path(env.get("XDG_CONFIG_HOME", user_home / ".config"))
        config_dir = xdg_config / "olympus"
        data_dir = Path(env.get("XDG_STATE_HOME", user_home / ".local" / "state")) / "olympus"
        autostart = xdg_config / "systemd" / "user" / "olympus-agent.service"
        legacy_identity = data_dir / "agent-id"
        legacy_key = data_dir / "agent-key.pem"
    return AgentPaths(
        platform=platform,
        config_dir=config_dir,
        data_dir=data_dir,
        log_dir=data_dir / "logs",
        config_path=config_dir / "agent.toml",
        identity_path=data_dir / "agent-id",
        key_path=data_dir / "agent-key.pem",
        lock_path=data_dir / "agent.lock",
        autostart_path=autostart,
        legacy_identity_path=legacy_identity,
        legacy_key_path=legacy_key,
    )
