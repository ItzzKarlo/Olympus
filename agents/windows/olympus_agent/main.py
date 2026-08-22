import platform

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.telemetry import collect_telemetry
from olympus_agent_common.runtime import run_agent


def main() -> None:
    run_agent(
        AgentConfig.from_environment(),
        "win",
        "windows",
        platform.version(),
        __version__,
        collect_telemetry,
    )


if __name__ == "__main__":
    main()
