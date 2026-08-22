import platform

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.telemetry import collect_telemetry, configure_game_detection
from olympus_agent_common.runtime import run_agent


def main() -> None:
    config = AgentConfig.from_environment()
    configure_game_detection(config.game_background_grace_seconds)
    run_agent(
        config,
        "win",
        "windows",
        platform.version(),
        __version__,
        collect_telemetry,
    )


if __name__ == "__main__":
    main()
