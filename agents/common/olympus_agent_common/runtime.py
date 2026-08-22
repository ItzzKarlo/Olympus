import asyncio
from collections.abc import Callable
import json
import logging
import os
import signal
from typing import Any

from websockets.asyncio.client import connect

from olympus_agent_common.config import AgentConfig
from olympus_agent_common.identity import DeviceKey, load_or_create_agent_id, load_or_create_device_key
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


async def _authenticate_socket(
    websocket: Any,
    config: AgentConfig,
    agent_id: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    enrollment_token: str | None,
) -> DeviceKey:
    key_path = config.key_path or config.identity_path.with_name("agent-key.pem")
    device_key = load_or_create_device_key(key_path)
    await websocket.send(json.dumps(build_hello(
        agent_id,
        platform_name,
        platform_version,
        agent_version,
        device_key.public_bytes,
        enrollment_token,
        config.display_name,
    )))
    response = await websocket.recv()
    handshake = parse_handshake(response)
    if handshake["type"] == "enrollment_required":
        raise EnrollmentRequired(
            f"Core requires device enrollment. Agent {agent_id}. "
            "Create a one-time token on Olympus Core and run olympus-agent enroll."
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
    return device_key


async def run_connection(
    config: AgentConfig,
    agent_id: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    collect_telemetry: TelemetryCollector,
    integrations: LocalIntegrationServer | None = None,
    stop: asyncio.Event | None = None,
) -> None:
    enrollment_token = os.getenv("OLYMPUS_ENROLLMENT_TOKEN") or None
    async with connect(config.core_ws_url) as websocket:
        await _authenticate_socket(
            websocket, config, agent_id, platform_name, platform_version,
            agent_version, enrollment_token,
        )
        LOGGER.info("Connected to Olympus Core as %s", agent_id)

        send_lock = asyncio.Lock()

        async def send(message: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send(json.dumps(message))

        async def forward_integrations() -> None:
            if integrations is None:
                return
            while stop is None or not stop.is_set():
                await send(await integrations.next_upstream())

        forward_task = asyncio.create_task(
            forward_integrations(), name="olympus-integration-forwarder"
        )
        previous_mode: str | None = None
        try:
            while stop is None or not stop.is_set():
                try:
                    telemetry = collect_telemetry()
                except Exception as error:
                    LOGGER.warning("Telemetry sample failed (%s)", error)
                    if stop is None:
                        await asyncio.sleep(config.telemetry_interval)
                    else:
                        try:
                            await asyncio.wait_for(stop.wait(), config.telemetry_interval)
                        except TimeoutError:
                            pass
                    continue
                if integrations is not None:
                    telemetry["integrations"] = integrations.snapshot()
                await send(telemetry)
                mode = telemetry["activity"]["mode"]
                if mode != previous_mode:
                    LOGGER.info("Activity changed to %s", mode)
                    previous_mode = mode
                if stop is None:
                    await asyncio.sleep(config.telemetry_interval)
                else:
                    try:
                        await asyncio.wait_for(stop.wait(), config.telemetry_interval)
                    except TimeoutError:
                        pass
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
    stop: asyncio.Event | None = None,
) -> None:
    agent_id = load_or_create_agent_id(config.identity_path, identity_prefix)
    while stop is None or not stop.is_set():
        try:
            await run_connection(
                config,
                agent_id,
                platform_name,
                platform_version,
                agent_version,
                collect_telemetry,
                integrations,
                stop,
            )
        except Exception as error:
            if isinstance(error, EnrollmentRequired):
                LOGGER.warning("%s", error)
                delay = max(30.0, config.reconnect_delay)
                if stop is None:
                    await asyncio.sleep(delay)
                else:
                    try:
                        await asyncio.wait_for(stop.wait(), delay)
                    except TimeoutError:
                        pass
                continue
            LOGGER.warning(
                "Core connection unavailable (%s); retrying in %.1f seconds",
                error,
                config.reconnect_delay,
            )
            if stop is None:
                await asyncio.sleep(config.reconnect_delay)
            else:
                try:
                    await asyncio.wait_for(stop.wait(), config.reconnect_delay)
                except TimeoutError:
                    pass


async def enroll_once(
    config: AgentConfig,
    identity_prefix: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    token: str,
) -> tuple[str, str]:
    agent_id = load_or_create_agent_id(config.identity_path, identity_prefix)
    async with connect(config.core_ws_url) as websocket:
        device_key = await _authenticate_socket(
            websocket, config, agent_id, platform_name, platform_version,
            agent_version, token,
        )
    os.environ.pop("OLYMPUS_ENROLLMENT_TOKEN", None)
    return agent_id, device_key.fingerprint


def run_agent(
    config: AgentConfig,
    identity_prefix: str,
    platform_name: str,
    platform_version: str,
    agent_version: str,
    collect_telemetry: TelemetryCollector,
) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        async def run() -> None:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for signal_name in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(signal_name, stop.set)
                except (NotImplementedError, RuntimeError):
                    pass
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
                    stop,
                )
            finally:
                if integrations is not None:
                    await integrations.stop()

        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("Olympus agent stopped")
