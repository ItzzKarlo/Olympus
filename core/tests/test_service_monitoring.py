import unittest

from olympus_core.models.monitoring import ProbeStatus
from olympus_core.monitoring.config import MonitoringConfig, NetworkConfig, ServiceConfig
from olympus_core.monitoring.probes import ProbeResult
from olympus_core.monitoring.services import ServiceCollector
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore


class SequenceProbe:
    def __init__(self, outcomes: list[bool]) -> None:
        self.outcomes = outcomes

    async def probe(self, _service: ServiceConfig, _timeout: float) -> ProbeResult:
        success = self.outcomes.pop(0)
        return ProbeResult(success, 12.1 if success else None)


async def no_update() -> None:
    return None


class ServiceCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_and_recovery_thresholds_prevent_flapping(self) -> None:
        service = ServiceConfig(
            id="minecraft",
            name="Minecraft",
            type="tcp",
            host="127.0.0.1",
            port=25565,
        )
        config = MonitoringConfig(
            network=NetworkConfig(enabled=False),
            services=(service,),
            service_failure_threshold=2,
            service_recovery_threshold=2,
        )
        store = MonitoringStore()
        events = EventService()
        collector = ServiceCollector(
            config,
            store,
            events,
            SequenceProbe([True, True, False, False, True, True]),
            no_update,
        )

        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.UNKNOWN)
        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.UP)
        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.UP)
        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.DOWN)
        self.assertEqual(len(events.active_alerts()), 1)
        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.DOWN)
        await collector.poll_once()
        self.assertEqual(store.services[service.id].status, ProbeStatus.UP)
        self.assertEqual(events.active_alerts(), [])
        self.assertEqual(len(events.recoveries()), 1)


if __name__ == "__main__":
    unittest.main()
