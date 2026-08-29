import unittest
from unittest.mock import Mock, patch

from olympus_core.monitoring.core_host import CoreHostCollector
from olympus_core.services.monitoring_store import MonitoringStore


async def no_update() -> None:
    return None


class CoreHostCollectorTests(unittest.TestCase):
    @patch("olympus_core.monitoring.core_host._cpu_temperature", return_value=51.25)
    @patch("olympus_core.monitoring.core_host._pi_power_flags", return_value=(True, False))
    @patch("olympus_core.monitoring.core_host.psutil.getloadavg", return_value=(0.5, 0.4, 0.3))
    @patch("olympus_core.monitoring.core_host.psutil.swap_memory")
    @patch("olympus_core.monitoring.core_host.psutil.disk_usage")
    @patch("olympus_core.monitoring.core_host.psutil.virtual_memory")
    @patch("olympus_core.monitoring.core_host.psutil.cpu_percent", return_value=12.5)
    def test_collects_only_available_normalized_host_metrics(
        self,
        _cpu: Mock,
        memory: Mock,
        disk: Mock,
        swap: Mock,
        _load: Mock,
        _power: Mock,
        _temperature: Mock,
    ) -> None:
        memory.return_value = Mock(percent=42.0, used=42, total=100)
        disk.return_value = Mock(percent=61.0, free=39, total=100)
        swap.return_value = Mock(percent=3.0)
        state = CoreHostCollector(MonitoringStore(), 5, no_update).collect_once()

        self.assertEqual(state.system.cpu_percent, 12.5)
        self.assertEqual(state.load_average_1m, 0.5)
        self.assertEqual(state.swap_percent, 3.0)
        self.assertEqual(state.cpu_temperature_celsius, 51.25)
        self.assertTrue(state.throttled)
        self.assertFalse(state.undervoltage)

    @patch("olympus_core.monitoring.core_host.time.monotonic", return_value=5.0)
    @patch("olympus_core.monitoring.core_host._pi_power_flags", return_value=(False, True))
    def test_power_flags_are_checked_immediately_after_early_boot(
        self,
        power_flags: Mock,
        _monotonic: Mock,
    ) -> None:
        collector = CoreHostCollector(MonitoringStore(), 5, no_update)
        self.assertEqual(collector._cached_power_flags(), (False, True))
        power_flags.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
