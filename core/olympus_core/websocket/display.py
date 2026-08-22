from starlette.websockets import WebSocket, WebSocketDisconnect

from olympus_core.display.hub import DisplayHub
from olympus_core.services.state import StateService


async def handle_display_socket(
    websocket: WebSocket,
    display_hub: DisplayHub,
    state_service: StateService,
) -> None:
    connected = False
    try:
        await display_hub.connect(websocket, state_service.display_state())
        connected = True
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if connected:
            await display_hub.disconnect(websocket)
