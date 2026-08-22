import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.agent import AgentHello
from olympus_core.models.telemetry import AgentTelemetry


def hello(agent_id: str = "mac-test") -> AgentHello:
    return AgentHello(
        type="hello",
        agent_id=agent_id,
        hostname="test-mac",
        platform="macos",
        platform_version="15.0",
        agent_version="0.1.0",
    )


def telemetry(mode: str = "idle") -> AgentTelemetry:
    return AgentTelemetry.model_validate(
        {
            "type": "telemetry",
            "system": {
                "cpu_percent": 12.5,
                "ram_percent": 48.0,
                "ram_used_bytes": 8_000_000_000,
                "ram_total_bytes": 16_000_000_000,
            },
            "activity": {
                "mode": mode,
                "application": "Rider" if mode == "development" else None,
                "process_name": "rider" if mode == "development" else None,
            },
        }
    )


def gaming_telemetry(
    game_id: str = "fortnite",
    game_name: str = "Fortnite",
    fps: float | None = None,
) -> AgentTelemetry:
    value = telemetry("gaming").model_dump(mode="json")
    value["activity"].update(
        {
            "application": game_name,
            "process_name": f"{game_id}.exe",
            "game": {"id": game_id, "name": game_name},
            "fps": fps,
        }
    )
    return AgentTelemetry.model_validate(value)


class AgentRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()

    def test_registration_marks_agent_online(self) -> None:
        agent, _ = self.registry.register(hello())

        self.assertTrue(agent.online)
        self.assertEqual(agent.agent_id, "mac-test")
        self.assertEqual(agent.hostname, "test-mac")
        self.assertEqual(agent.connected_at, agent.last_seen)

    def test_telemetry_updates_latest_state(self) -> None:
        self.registry.register(hello())

        agent = self.registry.update("mac-test", telemetry("development"))

        self.assertEqual(agent.system.cpu_percent, 12.5)
        self.assertEqual(agent.activity.application, "Rider")

    def test_disconnect_marks_agent_offline(self) -> None:
        self.registry.register(hello())

        self.registry.disconnect("mac-test")

        self.assertFalse(self.registry.get("mac-test").online)

    def test_stale_disconnect_does_not_override_reconnect(self) -> None:
        _, old_connection = self.registry.register(hello())
        _, new_connection = self.registry.register(hello())

        self.registry.disconnect("mac-test", old_connection)

        self.assertTrue(self.registry.get("mac-test").online)
        self.registry.disconnect("mac-test", new_connection)
        self.assertFalse(self.registry.get("mac-test").online)

    def test_stale_connection_cannot_overwrite_new_telemetry(self) -> None:
        _, old_connection = self.registry.register(hello())
        _, new_connection = self.registry.register(hello())
        self.registry.update("mac-test", telemetry("idle"), new_connection)

        self.registry.update("mac-test", telemetry("development"), old_connection)

        self.assertEqual(self.registry.get("mac-test").activity.mode, "idle")


if __name__ == "__main__":
    unittest.main()
