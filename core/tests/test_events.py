from datetime import datetime, timedelta, timezone
import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.monitoring import EventSeverity
from olympus_core.services.events import EventService
from olympus_core.services.state import StateService


class EventServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_incident_is_deduplicated_and_exposed_in_display_state(self) -> None:
        events = EventService()
        started = datetime(2026, 8, 22, 17, 0, tzinfo=timezone.utc)
        first = await events.raise_incident(
            "service:atlas",
            event_type="service.down",
            severity=EventSeverity.CRITICAL,
            title="Atlas is down",
            message="Repeated checks failed.",
            source="atlas",
            timestamp=started,
        )
        duplicate = await events.raise_incident(
            "service:atlas",
            event_type="service.down",
            severity=EventSeverity.CRITICAL,
            title="Atlas is down",
            message="Repeated checks failed.",
            source="atlas",
            timestamp=started + timedelta(seconds=5),
        )

        state = StateService(AgentRegistry(), events=events).display_state()
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(len(state.alerts), 1)
        self.assertEqual(state.alerts[0].title, "Atlas is down")

    async def test_recovery_resolves_alert_and_calculates_downtime(self) -> None:
        events = EventService(recovery_seconds=6)
        started = datetime(2026, 8, 22, 17, 0, tzinfo=timezone.utc)
        await events.raise_incident(
            "network:internet",
            event_type="network.internet.down",
            severity=EventSeverity.CRITICAL,
            title="Internet unavailable",
            message="External probe failed.",
            source="network",
            timestamp=started,
        )
        recovery = await events.resolve_incident(
            "network:internet",
            event_type="network.internet.restored",
            title="Internet restored",
            message="Connectivity is stable.",
            source="network",
            timestamp=started + timedelta(seconds=102),
        )

        self.assertEqual(events.active_alerts(), [])
        self.assertEqual(recovery.downtime_seconds, 102)
        self.assertEqual(events.recoveries(started + timedelta(seconds=103)), [recovery])
        self.assertEqual(events.recoveries(started + timedelta(seconds=109)), [])


if __name__ == "__main__":
    unittest.main()
