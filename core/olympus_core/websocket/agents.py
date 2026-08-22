import asyncio
import hmac
import logging
import secrets
import time
from collections.abc import Awaitable, Callable

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import SecuritySettings
from olympus_core.models.agent import (
    AgentAuthChallenge,
    AgentAuthResponse,
    AgentEnrollmentRequired,
    AgentHello,
    AgentWelcome,
)
from olympus_core.models.gameplay import GameplayEvent
from olympus_core.models.integrations import AgentIntegrationEvent, AgentIntegrationState
from olympus_core.models.telemetry import AgentTelemetry
from olympus_core.persistence.devices import DeviceRepository
from olympus_core.persistence.enrollment import EnrollmentError, EnrollmentRepository
from olympus_core.security import decode_base64url, encode_base64url, verify_agent_signature
from olympus_core.services.gameplay import GameplayEventService


POLICY_VIOLATION = 1008
logger = logging.getLogger(__name__)


async def _close(websocket: WebSocket, reason: str) -> None:
    await websocket.close(code=POLICY_VIOLATION, reason=reason)


async def _authenticate(
    websocket: WebSocket,
    hello: AgentHello,
    settings: SecuritySettings,
    devices: DeviceRepository,
    enrollment: EnrollmentRepository,
) -> bool:
    if not settings.require_agent_auth:
        return True
    if not hello.public_key:
        await websocket.send_json(
            AgentEnrollmentRequired(agent_id=hello.agent_id).model_dump(mode="json")
        )
        await _close(websocket, "Device enrollment required")
        return False
    try:
        claimed_key = decode_base64url(hello.public_key)
        if len(claimed_key) != 32:
            raise ValueError("Invalid key length")
    except ValueError:
        logger.warning("Agent authentication rejected for %s: malformed public key", hello.agent_id)
        await _close(websocket, "Authentication failed")
        return False

    device = devices.get(hello.agent_id)
    if device is None or device.revoked:
        if not hello.enrollment_token:
            await websocket.send_json(
                AgentEnrollmentRequired(agent_id=hello.agent_id).model_dump(mode="json")
            )
            await _close(websocket, "Device enrollment required")
            return False
        try:
            enrollment.enroll(
                token=hello.enrollment_token,
                agent_id=hello.agent_id,
                display_name=hello.hostname,
                platform=hello.platform,
                public_key=claimed_key,
            )
        except EnrollmentError as error:
            logger.warning("Agent enrollment rejected for %s: %s", hello.agent_id, error)
            await _close(websocket, "Enrollment failed")
            return False
        logger.info("Agent %s enrolled with trusted device identity", hello.agent_id)
        return True

    if not hmac.compare_digest(device.public_key, hello.public_key):
        logger.warning("Agent authentication rejected for %s: key mismatch", hello.agent_id)
        await _close(websocket, "Authentication failed")
        return False

    challenge = secrets.token_bytes(32)
    await websocket.send_json(
        AgentAuthChallenge(challenge=encode_base64url(challenge)).model_dump(mode="json")
    )
    try:
        response = AgentAuthResponse.model_validate(
            await asyncio.wait_for(websocket.receive_json(), settings.auth_timeout_seconds)
        )
        signature = decode_base64url(response.signature)
    except (TimeoutError, ValidationError, ValueError):
        logger.warning("Agent authentication rejected for %s: invalid response", hello.agent_id)
        await _close(websocket, "Authentication failed")
        return False
    if not verify_agent_signature(claimed_key, hello.agent_id, challenge, signature):
        logger.warning("Agent authentication rejected for %s: invalid signature", hello.agent_id)
        await _close(websocket, "Authentication failed")
        return False
    try:
        devices.record_authenticated(hello.agent_id)
    except Exception as error:
        logger.error("Could not persist authentication for %s: %s", hello.agent_id, error)
        await _close(websocket, "Authentication unavailable")
        return False
    return True


async def handle_agent_socket(
    websocket: WebSocket,
    registry: AgentRegistry,
    publish_state: Callable[[], Awaitable[None]],
    publish_event: Callable[[GameplayEvent], Awaitable[None]] | None = None,
    gameplay: GameplayEventService | None = None,
    security: SecuritySettings | None = None,
    devices: DeviceRepository | None = None,
    enrollment: EnrollmentRepository | None = None,
) -> None:
    await websocket.accept()
    agent_id: str | None = None
    connection_id: str | None = None
    authenticated = False
    settings = security or SecuritySettings(require_agent_auth=False)

    try:
        try:
            hello = AgentHello.model_validate(
                await asyncio.wait_for(websocket.receive_json(), settings.auth_timeout_seconds)
            )
        except (TimeoutError, ValidationError, ValueError):
            await _close(websocket, "Valid hello required")
            return

        if settings.require_agent_auth:
            if devices is None or enrollment is None:
                logger.error("Agent authentication is enabled without persistence services")
                await _close(websocket, "Authentication unavailable")
                return
            authenticated = await _authenticate(websocket, hello, settings, devices, enrollment)
            if not authenticated:
                return
        else:
            authenticated = True

        agent_id = hello.agent_id
        _, connection_id = registry.register(hello)
        await websocket.send_json(AgentWelcome(agent_id=agent_id).model_dump(mode="json"))
        await publish_state()

        gameplay = gameplay or GameplayEventService()
        next_trust_check = time.monotonic() + settings.revocation_refresh_seconds
        next_seen_write = time.monotonic() + settings.last_seen_write_seconds
        while True:
            timeout = max(0.1, next_trust_check - time.monotonic())
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout)
            except TimeoutError:
                message = None

            now_monotonic = time.monotonic()
            if settings.require_agent_auth and now_monotonic >= next_trust_check:
                device = devices.get(agent_id) if devices is not None else None
                if device is None or device.revoked:
                    logger.info("Closing revoked Agent connection for %s", agent_id)
                    await _close(websocket, "Device trust revoked")
                    return
                next_trust_check = now_monotonic + settings.revocation_refresh_seconds
            if message is None:
                continue

            message_type = message.get("type") if isinstance(message, dict) else None
            try:
                if message_type == "telemetry":
                    registry.update(agent_id, AgentTelemetry.model_validate(message), connection_id)
                    await publish_state()
                elif message_type == "integration_state":
                    integration_state = AgentIntegrationState.model_validate(message)
                    registry.update_integration(agent_id, integration_state, connection_id)
                    event = gameplay.observe_state(agent_id, integration_state)
                    await publish_state()
                    if event is not None and publish_event is not None:
                        await publish_event(event)
                elif message_type == "integration_event":
                    integration_event = AgentIntegrationEvent.model_validate(message)
                    if publish_event is not None:
                        await publish_event(gameplay.from_integration(agent_id, integration_event))
                else:
                    raise ValueError("Unsupported agent message")
            except (ValidationError, ValueError, TypeError):
                await _close(websocket, "Valid agent message required")
                return

            if settings.require_agent_auth and devices is not None and now_monotonic >= next_seen_write:
                try:
                    devices.touch_last_seen(agent_id, settings.last_seen_write_seconds)
                except Exception as error:
                    logger.warning("Could not persist last-seen for %s: %s", agent_id, error)
                next_seen_write = now_monotonic + settings.last_seen_write_seconds
    except WebSocketDisconnect:
        pass
    finally:
        if authenticated and agent_id is not None:
            registry.disconnect(agent_id, connection_id)
            if settings.require_agent_auth and devices is not None:
                try:
                    devices.touch_last_seen(agent_id, settings.last_seen_write_seconds, force=True)
                except Exception as error:
                    logger.warning("Could not persist disconnect for %s: %s", agent_id, error)
            await publish_state()
