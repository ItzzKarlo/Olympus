from olympus_agent_common.config import AgentConfig as CommonAgentConfig
from olympus_agent_common.paths import agent_paths


class AgentConfig(CommonAgentConfig):
    @classmethod
    def from_environment(cls) -> "AgentConfig":
        common = CommonAgentConfig.from_sources(agent_paths("macos"))
        return cls(
            core_ws_url=common.core_ws_url,
            telemetry_interval=common.telemetry_interval,
            reconnect_delay=common.reconnect_delay,
            identity_path=common.identity_path,
            game_background_grace_seconds=common.game_background_grace_seconds,
            integration_port=common.integration_port,
            integration_stale_seconds=common.integration_stale_seconds,
            key_path=common.key_path,
            display_name=common.display_name,
            config_path=common.config_path,
        )
