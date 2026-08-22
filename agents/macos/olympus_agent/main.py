import platform

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.telemetry import collect_telemetry
from olympus_agent_common.protocol import build_hello as common_build_hello
from olympus_agent_common.protocol import validate_welcome
from olympus_agent_common.runtime import run_agent


def build_hello(agent_id: str) -> dict[str, str]:
    return common_build_hello(
        agent_id,
        "macos",
        platform.mac_ver()[0] or platform.release(),
        __version__,
    )


def main() -> None:
    run_agent(
        AgentConfig.from_environment(),
        "mac",
        "macos",
        platform.mac_ver()[0] or platform.release(),
        __version__,
        collect_telemetry,
    )


if __name__ == "__main__":
    main()
