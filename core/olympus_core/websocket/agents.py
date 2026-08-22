from collections.abc import Awaitable, Callable

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.agent import AgentHello, AgentWelcome
from olympus_core.models.telemetry import AgentTelemetry
from olympus_core.models.gameplay import GameplayEvent
from olympus_core.models.integrations import AgentIntegrationEvent, AgentIntegrationState
from olympus_core.services.gameplay import GameplayEventService


POLICY_VIOLATION = 1008


async def handle_agent_socket(
    websocket: WebSocket,
    registry: AgentRegistry,
    publish_state: Callable[[], Awaitable[None]],
    publish_event: Callable[[GameplayEvent], Awaitable[None]] | None = None,
    gameplay: GameplayEventService | None = None,
) -> None:
    await websocket.accept()
    agent_id: str | None = None
    connection_id: str | None = None

    try:
        try:
            hello = AgentHello.model_validate(await websocket.receive_json())
        except (ValidationError, ValueError):
            await websocket.close(code=POLICY_VIOLATION, reason="Valid hello required")
            return

        agent_id = hello.agent_id
        _, connection_id = registry.register(hello)
        welcome = AgentWelcome(agent_id=agent_id)
        await websocket.send_json(welcome.model_dump(mode="json"))
        await publish_state()

        gameplay = gameplay or GameplayEventService()
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type") if isinstance(message, dict) else None
            try:
                if message_type == "telemetry":
                    telemetry = AgentTelemetry.model_validate(message)
                    registry.update(agent_id, telemetry, connection_id)
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
                        await publish_event(
                            gameplay.from_integration(agent_id, integration_event)
                        )
                else:
                    raise ValueError("Unsupported agent message")
            except (ValidationError, ValueError, TypeError):
                await websocket.close(
                    code=POLICY_VIOLATION,
                    reason="Valid agent message required",
                )
                return
    except WebSocketDisconnect:
        pass
    finally:
        if agent_id is not None:
            registry.disconnect(agent_id, connection_id)
            await publish_state()
