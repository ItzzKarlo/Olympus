import unittest
from typing import Any

from olympus_core.agents.registry import AgentRegistry
from olympus_core.display.hub import DisplayHub
from olympus_core.models.monitoring import EventSeverity
from olympus_core.services.events import EventService
from olympus_core.services.state import StateService
from olympus_core.models.gameplay import GameplayEvent, GameplayEventSource
from datetime import datetime, timezone


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

    async def test_reconnecting_display_does_not_receive_disabled_alert(self) -> None:
        events = EventService()
        await events.raise_incident(
            "service:nas",
            event_type="service.down",
            severity=EventSeverity.WARNING,
            title="NAS is down",
            message="Repeated checks failed.",
            source="nas",
        )
        state = StateService(AgentRegistry(), events=events).display_state()
        display = FakeWebSocket()

        await self.hub.connect(display, state)  # type: ignore[arg-type]

        self.assertEqual(events.active_alerts()[0].title, "NAS is down")
        self.assertEqual(display.messages[0]["alerts"], [])

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

    async def test_gameplay_event_is_broadcast_as_transient_message(self) -> None:
        display = FakeWebSocket()
        await self.hub.connect(display, self.state)  # type: ignore[arg-type]
        event = GameplayEvent(
            id="event-1",
            type="minecraft.player.healed",
            timestamp=datetime.now(timezone.utc),
            source=GameplayEventSource(agent_id="win", integration="minecraft"),
            payload={"amount": 1},
        )
        await self.hub.broadcast_event(event)
        self.assertEqual(display.messages[-1]["type"], "event")
        self.assertEqual(
            display.messages[-1]["event"]["type"],
            "minecraft.player.healed",
        )


if __name__ == "__main__":
    unittest.main()
