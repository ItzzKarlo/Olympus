from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import parse_core_config
from olympus_core.models.monitoring import EventSeverity
from olympus_core.persistence.database import Database
from olympus_core.persistence.incidents import IncidentRepository
from olympus_core.services.events import EventService
from olympus_core.services.state import StateService


class EventServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_alert_interruption_gate_defaults_off_and_can_be_reenabled(self) -> None:
        self.assertFalse(
            parse_core_config({}).presentation.alert_interruptions_enabled
        )
        self.assertTrue(parse_core_config({
            "presentation": {"alert_interruptions_enabled": True}
        }).presentation.alert_interruptions_enabled)

    async def test_incident_is_deduplicated_but_interruptions_default_off(self) -> None:
        events = EventService()
        started = datetime(2026, 8, 22, 17, 0, tzinfo=timezone.utc)
        first = await events.raise_incident(
            "service:nas",
            event_type="service.down",
            severity=EventSeverity.CRITICAL,
            title="NAS is down",
            message="Repeated checks failed.",
            source="nas",
            timestamp=started,
        )
        duplicate = await events.raise_incident(
            "service:nas",
            event_type="service.down",
            severity=EventSeverity.CRITICAL,
            title="NAS is down",
            message="Repeated checks failed.",
            source="nas",
            timestamp=started + timedelta(seconds=5),
        )

        state = StateService(AgentRegistry(), events=events).display_state()
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(len(events.active_alerts()), 1)
        self.assertEqual(state.alerts, [])
        enabled = StateService(
            AgentRegistry(),
            events=events,
            alert_interruptions_enabled=True,
        ).display_state()
        self.assertEqual(enabled.alerts[0].title, "NAS is down")

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

    async def test_active_incident_keeps_original_start_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "core.db")
            database.initialize()
            incidents = IncidentRepository(database)
            started = datetime(2026, 8, 22, 22, 0, tzinfo=timezone.utc)
            first = EventService(incidents=incidents)
            await first.raise_incident(
                "network:internet",
                event_type="network.internet.down",
                severity=EventSeverity.CRITICAL,
                title="Internet unavailable",
                message="External probe failed.",
                source="network",
                timestamp=started,
            )

            restarted = EventService(incidents=incidents)
            restarted.restore({"network:internet"})
            restored = await restarted.raise_incident(
                "network:internet",
                event_type="network.internet.down",
                severity=EventSeverity.CRITICAL,
                title="Internet unavailable",
                message="External probe failed.",
                source="network",
                timestamp=started + timedelta(minutes=10),
            )
            recovery = await restarted.resolve_incident(
                "network:internet",
                event_type="network.internet.restored",
                title="Internet restored",
                message="Connectivity is stable.",
                source="network",
                timestamp=started + timedelta(minutes=15),
            )
            self.assertEqual(restored.started_at, started)
            self.assertEqual(recovery.downtime_seconds, 900)
            self.assertEqual(incidents.active(), [])

    async def test_removed_monitor_is_resolved_without_ghost_alert(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "core.db")
            database.initialize()
            incidents = IncidentRepository(database)
            events = EventService(incidents=incidents)
            await events.raise_incident(
                "service:removed",
                event_type="service.down",
                severity=EventSeverity.WARNING,
                title="Removed is down",
                message="Failed.",
                source="removed",
            )
            restarted = EventService(incidents=incidents)
            restarted.restore(set())
            self.assertEqual(restarted.active_alerts(), [])


if __name__ == "__main__":
    unittest.main()
