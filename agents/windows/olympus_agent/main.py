import platform

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.telemetry import collect_telemetry, configure_game_detection
from olympus_agent_common.cli import AgentApplication, run_cli
from olympus_agent_common.paths import agent_paths


def main(argv: list[str] | None = None) -> int:
    return run_cli(AgentApplication(
        identity_prefix="win",
        platform_name="windows",
        platform_version=platform.version(),
        version=__version__,
        collect_telemetry=collect_telemetry,
        paths=agent_paths("windows"),
        configure=lambda config: configure_game_detection(
            config.game_background_grace_seconds
        ),
    ), argv)


if __name__ == "__main__":
    raise SystemExit(main())
