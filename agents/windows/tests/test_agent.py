import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import os

from olympus_agent.activity import detect_development_activity
from olympus_agent.gpu import collect_nvidia_gpu
from olympus_agent.fps import PresentMonCsvFpsProvider
from olympus_agent.game_profiles import WINDOWS_GAME_PROFILES
from olympus_agent.identity import load_or_create_agent_id
from olympus_agent_common.telemetry import build_telemetry
from olympus_agent_common.games import ForegroundGameDetector, ProcessInfo


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

    def test_known_games_and_launcher_exclusion(self) -> None:
        cases = [
            ("FortniteClient-Win64-Shipping.exe", "fortnite"),
            ("Among Us.exe", "among-us"),
            ("Goat2-Win64-Shipping.exe", "goat-simulator-3"),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                detector = ForegroundGameDetector(WINDOWS_GAME_PROFILES, 15)
                activity = detector.detect([ProcessInfo(42, name)], 42)
                self.assertEqual(activity.game.id, expected)

        detector = ForegroundGameDetector(WINDOWS_GAME_PROFILES, 15)
        self.assertIsNone(
            detector.detect([ProcessInfo(42, "EpicGamesLauncher.exe")], 42)
        )

    def test_minecraft_detection_is_conservative(self) -> None:
        detector = ForegroundGameDetector(WINDOWS_GAME_PROFILES, 15)
        generic_java = ProcessInfo(8, "javaw.exe", ("javaw", "-jar", "idea.jar"))
        self.assertIsNone(detector.detect([generic_java], 8))

        minecraft = ProcessInfo(
            9,
            "javaw.exe",
            ("javaw", "net.minecraft.client.main.Main", "--username", "Alex"),
        )
        activity = detector.detect([minecraft], 9)
        self.assertEqual(activity.game.id, "minecraft")

    def test_background_grace_preserves_then_releases_game(self) -> None:
        current_time = [100.0]
        detector = ForegroundGameDetector(
            WINDOWS_GAME_PROFILES,
            15,
            clock=lambda: current_time[0],
        )
        fortnite = ProcessInfo(42, "FortniteClient-Win64-Shipping.exe")
        self.assertEqual(detector.detect([fortnite], 42).mode, "gaming")
        current_time[0] = 114
        self.assertEqual(detector.detect([fortnite], 99).mode, "gaming")
        current_time[0] = 116
        self.assertIsNone(detector.detect([fortnite], 99))

    def test_presentmon_csv_provider_is_optional_and_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presentmon.csv"
            path.write_text(
                "Application,ProcessID,FrameTime\n"
                "FortniteClient-Win64-Shipping.exe,42,8.0\n"
                "FortniteClient-Win64-Shipping.exe,42,8.0\n",
                encoding="utf-8",
            )
            os.utime(path, None)
            provider = PresentMonCsvFpsProvider(path)
            self.assertEqual(
                provider.latest_fps("FortniteClient-Win64-Shipping.exe"),
                125.0,
            )


if __name__ == "__main__":
    unittest.main()
