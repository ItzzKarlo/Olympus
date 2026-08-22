import asyncio
from collections.abc import Callable
import json
import logging
import os
from typing import Any

from websockets.asyncio.client import connect

from olympus_agent_common.config import AgentConfig
from olympus_agent_common.identity import load_or_create_agent_id, load_or_create_device_key
from olympus_agent_common.integrations import LocalIntegrationServer
from olympus_agent_common.protocol import (
    auth_payload,
    build_hello,
    decode_base64url,
    encode_base64url,
    parse_handshake,
    validate_welcome,
)


LOGGER = logging.getLogger("olympus-agent")
TelemetryCollector = Callable[[], dict[str, Any]]


class EnrollmentRequired(RuntimeError):
    pass


async def run_connection(
    config: AgentConfig,
    agent_id: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    collect_telemetry: TelemetryCollector,
    integrations: LocalIntegrationServer | None = None,
) -> None:
    key_path = config.key_path or config.identity_path.with_name("agent-key.pem")
    device_key = load_or_create_device_key(key_path)
    enrollment_token = os.getenv("OLYMPUS_ENROLLMENT_TOKEN") or None
    async with connect(config.core_ws_url) as websocket:
        await websocket.send(
            json.dumps(
                build_hello(
                    agent_id,
                    platform_name,
                    platform_version,
                    agent_version,
                    device_key.public_bytes,
                    enrollment_token,
                )
            )
        )
        response = await websocket.recv()
        handshake = parse_handshake(response)
        if handshake["type"] == "enrollment_required":
            raise EnrollmentRequired(
                f"Core requires device enrollment. Agent {agent_id}. "
                "Create a one-time token on Olympus Core and provide it using "
                "OLYMPUS_ENROLLMENT_TOKEN."
            )
        if handshake["type"] == "auth_challenge":
            if handshake.get("protocol") != "olympus-agent-auth-v1":
                raise ValueError("Core requested an unsupported authentication protocol")
            challenge = decode_base64url(str(handshake.get("challenge", "")))
            if len(challenge) < 32:
                raise ValueError("Core returned an invalid authentication challenge")
            signature = device_key.sign(auth_payload(agent_id, challenge))
            await websocket.send(json.dumps({
                "type": "auth_response",
                "signature": encode_base64url(signature),
            }))
            response = await websocket.recv()
        validate_welcome(response, agent_id)
        LOGGER.info("Connected to Olympus Core as %s", agent_id)

        send_lock = asyncio.Lock()

        async def send(message: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send(json.dumps(message))

        async def forward_integrations() -> None:
            if integrations is None:
                return
            while True:
                await send(await integrations.next_upstream())

        forward_task = asyncio.create_task(
            forward_integrations(), name="olympus-integration-forwarder"
        )
        previous_mode: str | None = None
        try:
            while True:
                try:
                    telemetry = collect_telemetry()
                except Exception as error:
                    LOGGER.warning("Telemetry sample failed (%s)", error)
                    await asyncio.sleep(config.telemetry_interval)
                    continue
                if integrations is not None:
                    telemetry["integrations"] = integrations.snapshot()
                await send(telemetry)
                mode = telemetry["activity"]["mode"]
                if mode != previous_mode:
                    LOGGER.info("Activity changed to %s", mode)
                    previous_mode = mode
                await asyncio.sleep(config.telemetry_interval)
        finally:
            forward_task.cancel()
            await asyncio.gather(forward_task, return_exceptions=True)


async def run_forever(
    config: AgentConfig,
    identity_prefix: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    collect_telemetry: TelemetryCollector,
    integrations: LocalIntegrationServer | None = None,
) -> None:
    agent_id = load_or_create_agent_id(config.identity_path, identity_prefix)
    while True:
        try:
            await run_connection(
                config,
                agent_id,
                platform_name,
                platform_version,
                agent_version,
                collect_telemetry,
                integrations,
            )
        except Exception as error:
            if isinstance(error, EnrollmentRequired):
                LOGGER.warning("%s", error)
                await asyncio.sleep(max(30.0, config.reconnect_delay))
                continue
            LOGGER.warning(
                "Core connection unavailable (%s); retrying in %.1f seconds",
                error,
                config.reconnect_delay,
            )
            await asyncio.sleep(config.reconnect_delay)


def run_agent(
    config: AgentConfig,
    identity_prefix: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    collect_telemetry: TelemetryCollector,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        async def run() -> None:
            integrations = LocalIntegrationServer(
                config.integration_port,
                config.integration_stale_seconds,
            )
            try:
                await integrations.start()
            except OSError as error:
                LOGGER.warning(
                    "Local integration endpoint unavailable (%s); continuing without it",
                    error,
                )
                integrations = None  # type: ignore[assignment]
            try:
                await run_forever(
                    config,
                    identity_prefix,
                    platform_name,
                    platform_version,
                    agent_version,
                    collect_telemetry,
                    integrations,
                )
            finally:
                if integrations is not None:
                    await integrations.stop()

        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("Olympus agent stopped")
