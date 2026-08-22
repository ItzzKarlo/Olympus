import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from olympus_agent.activity import detect_development_activity
from olympus_agent.identity import load_or_create_agent_id
from olympus_agent.telemetry import normalize_cpu_temperature
from olympus_agent.game_profiles import LINUX_GAME_PROFILES
from olympus_agent_common.games import ProcessInfo, detect_running_game
from olympus_agent_common.telemetry import build_telemetry


class LinuxAgentTests(unittest.TestCase):
    def test_identity_persists_with_linux_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".local" / "state" / "olympus" / "agent-id"
            first = load_or_create_agent_id(path)
            self.assertEqual(first, load_or_create_agent_id(path))
            self.assertRegex(first, r"^linux-[0-9a-f]{32}$")

    def test_linux_ide_process_is_normalized(self) -> None:
        process = SimpleNamespace(info={"name": "idea64"})
        activity = detect_development_activity([process])
        self.assertEqual(activity.application, "IntelliJ IDEA")

    def test_cpu_temperature_prefers_known_sensor(self) -> None:
        readings = {
            "other": [SimpleNamespace(current=91)],
            "coretemp": [SimpleNamespace(current=48), SimpleNamespace(current=52)],
        }
        self.assertEqual(normalize_cpu_temperature(readings), 52)

    def test_missing_optional_metrics_are_omitted(self) -> None:
        telemetry = build_telemetry(
            system={"cpu_percent": 1},
            activity={"mode": "idle"},
            gpu=None,
            temperatures=None,
        )
        self.assertNotIn("gpu", telemetry)
        self.assertNotIn("temperatures", telemetry)

    def test_generic_java_is_not_minecraft(self) -> None:
        process = ProcessInfo(5, "java", ("java", "-jar", "server.jar"))
        self.assertIsNone(detect_running_game([process], LINUX_GAME_PROFILES))

    def test_minecraft_client_command_is_detected(self) -> None:
        process = ProcessInfo(
            6,
            "java",
            ("java", "net.minecraft.client.main.Main", "--username", "Alex"),
        )
        activity = detect_running_game([process], LINUX_GAME_PROFILES)
        self.assertEqual(activity.game.id, "minecraft")


if __name__ == "__main__":
    unittest.main()
