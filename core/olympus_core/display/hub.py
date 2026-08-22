import asyncio

from starlette.websockets import WebSocket

from olympus_core.models.state import DisplayState
from olympus_core.models.gameplay import DisplayEventMessage, GameplayEvent


class DisplayHub:
    """Tracks display sockets and publishes complete interpreted snapshots."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._send_lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket, state: DisplayState) -> None:
        await websocket.accept()
        async with self._send_lock:
            await websocket.send_json(state.model_dump(mode="json"))
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._send_lock:
            self._connections.discard(websocket)

    async def broadcast(self, state: DisplayState) -> None:
        payload = state.model_dump(mode="json")
        await self._broadcast_payload(payload)

    async def broadcast_event(self, event: GameplayEvent) -> None:
        payload = DisplayEventMessage(event=event).model_dump(mode="json")
        await self._broadcast_payload(payload)

    async def _broadcast_payload(self, payload: dict[str, object]) -> None:
        async with self._send_lock:
            disconnected: list[WebSocket] = []
            for websocket in tuple(self._connections):
                try:
                    await websocket.send_json(payload)
                except Exception:
                    disconnected.append(websocket)

            for websocket in disconnected:
                self._connections.discard(websocket)
