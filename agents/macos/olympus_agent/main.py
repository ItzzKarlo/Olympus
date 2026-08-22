import platform

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.telemetry import collect_telemetry
from olympus_agent_common.protocol import build_hello as common_build_hello
from olympus_agent_common.protocol import validate_welcome
from olympus_agent_common.runtime import run_connection as common_run_connection
from olympus_agent_common.runtime import run_forever as common_run_forever
from olympus_agent_common.cli import AgentApplication, run_cli
from olympus_agent_common.paths import agent_paths


def build_hello(agent_id: str) -> dict[str, str]:
    return common_build_hello(
        agent_id,
        "macos",
        platform.mac_ver()[0] or platform.release(),
        __version__,
    )


async def run_connection(config: AgentConfig, agent_id: str) -> None:
    await common_run_connection(
        config,
        agent_id,
        "macos",
        platform.mac_ver()[0] or platform.release(),
        __version__,
        collect_telemetry,
    )


async def run_forever(config: AgentConfig) -> None:
    await common_run_forever(
        config,
        "mac",
        "macos",
        platform.mac_ver()[0] or platform.release(),
        __version__,
        collect_telemetry,
    )


def main(argv: list[str] | None = None) -> int:
    return run_cli(AgentApplication(
        identity_prefix="mac",
        platform_name="macos",
        platform_version=platform.mac_ver()[0] or platform.release(),
        version=__version__,
        collect_telemetry=collect_telemetry,
        paths=agent_paths("macos"),
    ), argv)


if __name__ == "__main__":
    raise SystemExit(main())
