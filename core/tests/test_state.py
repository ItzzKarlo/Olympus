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

    def test_online_development_agent_sets_development_mode(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))

        state = self.state.current()

        self.assertEqual(state.mode, ActivityMode.DEVELOPMENT)
        self.assertEqual(state.active_device, "mac-test")

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


if __name__ == "__main__":
    unittest.main()
