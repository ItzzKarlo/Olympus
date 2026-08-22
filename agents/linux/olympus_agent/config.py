import os
from pathlib import Path

from olympus_agent_common.config import AgentConfig as CommonAgentConfig


def default_identity_path() -> Path:
    state_home = os.getenv("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / "olympus" / "agent-id"


class AgentConfig(CommonAgentConfig):
    @classmethod
    def from_environment(cls) -> "AgentConfig":
        common = CommonAgentConfig.from_environment(default_identity_path())
        return cls(
            core_ws_url=common.core_ws_url,
            telemetry_interval=common.telemetry_interval,
            reconnect_delay=common.reconnect_delay,
            identity_path=common.identity_path,
            game_background_grace_seconds=common.game_background_grace_seconds,
            integration_port=common.integration_port,
            integration_stale_seconds=common.integration_stale_seconds,
            key_path=common.key_path,
        )
