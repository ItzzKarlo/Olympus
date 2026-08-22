import unittest
from typing import Any

from olympus_core.agents.registry import AgentRegistry
from olympus_core.display.hub import DisplayHub
from olympus_core.models.monitoring import EventSeverity
from olympus_core.services.events import EventService
from olympus_core.services.state import StateService


class FakeWebSocket:
    def __init__(self, fail_sends: bool = False) -> None:
        self.accepted = False
        self.fail_sends = fail_sends
        self.messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.fail_sends:
            raise RuntimeError("display disconnected")
        self.messages.append(message)


class DisplayHubTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.hub = DisplayHub()
        self.state = StateService(AgentRegistry()).display_state()

    async def test_connect_sends_immediate_full_snapshot(self) -> None:
        display = FakeWebSocket()

        await self.hub.connect(display, self.state)  # type: ignore[arg-type]

        self.assertTrue(display.accepted)
        self.assertEqual(display.messages[0]["type"], "state")
        self.assertEqual(display.messages[0]["mode"], "idle")
        self.assertEqual(self.hub.connection_count, 1)

    async def test_reconnecting_display_receives_active_alert(self) -> None:
        events = EventService()
        await events.raise_incident(
            "service:atlas",
            event_type="service.down",
            severity=EventSeverity.WARNING,
            title="Atlas is down",
            message="Repeated checks failed.",
            source="atlas",
        )
        state = StateService(AgentRegistry(), events=events).display_state()
        display = FakeWebSocket()

        await self.hub.connect(display, state)  # type: ignore[arg-type]

        self.assertEqual(display.messages[0]["alerts"][0]["title"], "Atlas is down")

    async def test_broken_display_does_not_block_healthy_display(self) -> None:
        healthy = FakeWebSocket()
        broken = FakeWebSocket()
        await self.hub.connect(healthy, self.state)  # type: ignore[arg-type]
        await self.hub.connect(broken, self.state)  # type: ignore[arg-type]
        broken.fail_sends = True

        await self.hub.broadcast(self.state)

        self.assertEqual(len(healthy.messages), 2)
        self.assertEqual(self.hub.connection_count, 1)

    async def test_disconnect_removes_display(self) -> None:
        display = FakeWebSocket()
        await self.hub.connect(display, self.state)  # type: ignore[arg-type]

        await self.hub.disconnect(display)  # type: ignore[arg-type]

        self.assertEqual(self.hub.connection_count, 0)


if __name__ == "__main__":
    unittest.main()
