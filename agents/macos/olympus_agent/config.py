from pathlib import Path

from olympus_agent_common.config import AgentConfig as CommonAgentConfig


class AgentConfig(CommonAgentConfig):
    @classmethod
    def from_environment(cls) -> "AgentConfig":
        common = CommonAgentConfig.from_environment(
            Path.home() / ".olympus" / "agent-id"
        )
        return cls(
            core_ws_url=common.core_ws_url,
            telemetry_interval=common.telemetry_interval,
            reconnect_delay=common.reconnect_delay,
            identity_path=common.identity_path,
            game_background_grace_seconds=common.game_background_grace_seconds,
        )
