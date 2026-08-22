import asyncio
import json
import logging
import platform
import socket
from typing import Any

from websockets.asyncio.client import connect

from olympus_agent import __version__
from olympus_agent.config import AgentConfig
from olympus_agent.identity import load_or_create_agent_id
from olympus_agent.telemetry import collect_telemetry


LOGGER = logging.getLogger("olympus-agent")


def build_hello(agent_id: str) -> dict[str, str]:
    return {
        "type": "hello",
        "agent_id": agent_id,
        "hostname": socket.gethostname(),
        "platform": "macos",
        "platform_version": platform.mac_ver()[0] or platform.release(),
        "agent_version": __version__,
    }


def validate_welcome(message: str, agent_id: str) -> None:
    payload: Any = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("Core returned a non-object welcome message")
    if payload.get("type") != "welcome" or payload.get("agent_id") != agent_id:
        raise ValueError("Core returned an invalid welcome message")


async def run_connection(config: AgentConfig, agent_id: str) -> None:
    async with connect(config.core_ws_url) as websocket:
        await websocket.send(json.dumps(build_hello(agent_id)))
        validate_welcome(await websocket.recv(), agent_id)
        LOGGER.info("Connected to Olympus Core as %s", agent_id)

        previous_mode: str | None = None
        while True:
            try:
                telemetry = collect_telemetry()
            except Exception as error:
                LOGGER.warning("Telemetry sample failed (%s)", error)
                await asyncio.sleep(config.telemetry_interval)
                continue
            await websocket.send(json.dumps(telemetry))
            mode = telemetry["activity"]["mode"]
            if mode != previous_mode:
                LOGGER.info("Activity changed to %s", mode)
                previous_mode = mode
            await asyncio.sleep(config.telemetry_interval)


async def run_forever(config: AgentConfig) -> None:
    agent_id = load_or_create_agent_id(config.identity_path)
    while True:
        try:
            await run_connection(config, agent_id)
        except Exception as error:
            LOGGER.warning(
                "Core connection unavailable (%s); retrying in %.1f seconds",
                error,
                config.reconnect_delay,
            )
            await asyncio.sleep(config.reconnect_delay)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run_forever(AgentConfig.from_environment()))
    except KeyboardInterrupt:
        LOGGER.info("Olympus agent stopped")


if __name__ == "__main__":
    main()
