import os
from pathlib import Path

from olympus_agent_common.config import AgentConfig as CommonAgentConfig


def default_identity_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "Olympus" / "agent-id"


class AgentConfig(CommonAgentConfig):
    @classmethod
    def from_environment(cls) -> "AgentConfig":
        common = CommonAgentConfig.from_environment(default_identity_path())
        return cls(
            core_ws_url=common.core_ws_url,
            telemetry_interval=common.telemetry_interval,
            reconnect_delay=common.reconnect_delay,
            identity_path=common.identity_path,
        )
