import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.telemetry import ActivityMode
from olympus_core.services.state import StateService
from tests.test_registry import hello, telemetry


class StateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.state = StateService(self.registry)

    def test_state_is_idle_without_agents(self) -> None:
        state = self.state.current()

        self.assertEqual(state.mode, ActivityMode.IDLE)
        self.assertIsNone(state.active_device)
        self.assertEqual(state.machines, {})
        self.assertEqual(state.timezone, "UTC")
        self.assertIsNone(state.weather)
        self.assertIsNone(state.calendar)

    def test_ambient_context_does_not_create_a_primary_mode(self) -> None:
        state = StateService(self.registry, timezone="Europe/Berlin").current()
        self.assertEqual(state.mode, ActivityMode.IDLE)
        self.assertEqual(state.timezone, "Europe/Berlin")

    def test_online_development_agent_sets_development_mode(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))

        state = self.state.current()

        self.assertEqual(state.mode, ActivityMode.DEVELOPMENT)
        self.assertEqual(state.active_device, "mac-test")
        self.assertEqual(state.machines["mac-test"].agent_id, "mac-test")
        self.assertEqual(state.machines["mac-test"].platform, "macos")

    def test_idle_agent_does_not_set_development_mode(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("idle"))

        self.assertEqual(self.state.current().mode, ActivityMode.IDLE)

    def test_offline_development_agent_does_not_set_development_mode(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.registry.disconnect("mac-test")

        state = self.state.current()

        self.assertEqual(state.mode, ActivityMode.IDLE)
        self.assertIsNone(state.active_device)
        self.assertFalse(state.machines["mac-test"].online)

    def test_display_state_is_typed_and_contains_registered_machines(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))

        state = self.state.display_state()

        self.assertEqual(state.type, "state")
        self.assertEqual(state.mode, ActivityMode.DEVELOPMENT)
        self.assertEqual(state.active_device, "mac-test")
        self.assertIn("mac-test", state.machines)
        self.assertIsNone(state.media)
        self.assertIsNotNone(state.generated_at.tzinfo)

    def test_disconnected_agent_changes_display_state_to_idle(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.registry.disconnect("mac-test")

        state = self.state.display_state()

        self.assertEqual(state.mode, ActivityMode.IDLE)
        self.assertFalse(state.machines["mac-test"].online)


if __name__ == "__main__":
    unittest.main()
