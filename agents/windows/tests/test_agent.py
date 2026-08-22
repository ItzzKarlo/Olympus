import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from olympus_agent.activity import detect_development_activity
from olympus_agent.gpu import collect_nvidia_gpu
from olympus_agent.identity import load_or_create_agent_id
from olympus_agent_common.telemetry import build_telemetry


class FakeNvml:
    NVML_TEMPERATURE_GPU = 0

    def nvmlInit(self) -> None: pass
    def nvmlShutdown(self) -> None: pass
    def nvmlDeviceGetCount(self) -> int: return 1
    def nvmlDeviceGetHandleByIndex(self, _index: int) -> object: return object()
    def nvmlDeviceGetName(self, _handle: object) -> str: return "NVIDIA Test GPU"
    def nvmlDeviceGetUtilizationRates(self, _handle: object) -> SimpleNamespace:
        return SimpleNamespace(gpu=14)
    def nvmlDeviceGetMemoryInfo(self, _handle: object) -> SimpleNamespace:
        return SimpleNamespace(used=1024, total=4096)
    def nvmlDeviceGetTemperature(self, _handle: object, _sensor: int) -> int: return 42


class WindowsAgentTests(unittest.TestCase):
    def test_identity_persists_with_windows_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Olympus" / "agent-id"
            first = load_or_create_agent_id(path)
            self.assertEqual(first, load_or_create_agent_id(path))
            self.assertRegex(first, r"^win-[0-9a-f]{32}$")

    def test_visual_studio_process_is_normalized(self) -> None:
        process = SimpleNamespace(info={"name": "devenv.exe"})
        activity = detect_development_activity([process])
        self.assertEqual(activity.mode, "development")
        self.assertEqual(activity.application, "Visual Studio 2022")

    def test_nvidia_gpu_normalization(self) -> None:
        gpu = collect_nvidia_gpu(FakeNvml())
        self.assertEqual(gpu["name"], "NVIDIA Test GPU")
        self.assertEqual(gpu["temperature_celsius"], 42.0)

    def test_missing_optional_metrics_are_omitted(self) -> None:
        telemetry = build_telemetry(
            system={"cpu_percent": 1},
            activity={"mode": "idle"},
            gpu=None,
            temperatures=None,
        )
        self.assertNotIn("gpu", telemetry)
        self.assertNotIn("temperatures", telemetry)


if __name__ == "__main__":
    unittest.main()
