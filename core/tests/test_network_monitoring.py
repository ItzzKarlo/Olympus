import unittest

from olympus_core.models.monitoring import ProbeStatus
from olympus_core.monitoring.config import NetworkConfig, TargetConfig
from olympus_core.monitoring.network import NetworkCollector
from olympus_core.monitoring.probes import ProbeResult
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore


class FakeProbes:
    def __init__(self, results: dict[str, ProbeResult]) -> None:
        self.results = results

    async def probe_all(self, _config: NetworkConfig) -> dict[str, ProbeResult]:
        return self.results


async def no_update() -> None:
    return None


class NetworkCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalizes_mixed_network_evidence(self) -> None:
        config = NetworkConfig(failure_threshold=1, recovery_threshold=1)
        events = EventService()
        collector = NetworkCollector(
            config,
            MonitoringStore(),
            events,
            FakeProbes(
                {
                    "gateway": ProbeResult(True, 0.8, host="192.168.178.1", source="auto"),
                    "internet": ProbeResult(True, 14.2),
                    "dns": ProbeResult(True, 8.4),
                    "https": ProbeResult(False),
                }
            ),
            no_update,
        )
        state = await collector.poll_once()

        self.assertEqual(state.gateway.status, ProbeStatus.UP)
        self.assertEqual(state.gateway.host, "192.168.178.1")
        self.assertEqual(state.gateway.source, "auto")
        self.assertEqual(state.dns.status, ProbeStatus.UP)
        self.assertEqual(state.internet.status, ProbeStatus.UP)
        self.assertEqual(state.https.status, ProbeStatus.DOWN)
        self.assertEqual(events.active_alerts()[0].type, "network.https.down")

    async def test_remote_target_failure_uses_diagnostic_language(self) -> None:
        target = TargetConfig("nas", "Home NAS", "10.10.0.20", 443)
        config = NetworkConfig(
            failure_threshold=1,
            recovery_threshold=1,
            targets=(target,),
        )
        events = EventService()
        collector = NetworkCollector(
            config,
            MonitoringStore(),
            events,
            FakeProbes(
                {
                    "gateway": ProbeResult(True, 1),
                    "internet": ProbeResult(True, 12),
                    "dns": ProbeResult(True, 5),
                    "https": ProbeResult(True, 20),
                    "target:nas": ProbeResult(False),
                }
            ),
            no_update,
        )
        await collector.poll_once()
        alert = events.active_alerts()[0]
        self.assertEqual(alert.title, "Home NAS unreachable")
        self.assertIn("Meshnet", alert.message)


if __name__ == "__main__":
    unittest.main()
