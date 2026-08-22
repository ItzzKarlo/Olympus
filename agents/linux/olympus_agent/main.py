import platform

from olympus_agent import __version__
from olympus_agent.telemetry import collect_telemetry
from olympus_agent_common.cli import AgentApplication, run_cli
from olympus_agent_common.paths import agent_paths


def main(argv: list[str] | None = None) -> int:
    return run_cli(AgentApplication(
        identity_prefix="linux",
        platform_name="linux",
        platform_version=platform.release(),
        version=__version__,
        collect_telemetry=collect_telemetry,
        paths=agent_paths("linux"),
    ), argv)


if __name__ == "__main__":
    raise SystemExit(main())
