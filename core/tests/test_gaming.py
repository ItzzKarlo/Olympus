from datetime import datetime, timedelta, timezone
import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.services.gaming import GamingSessionService
from olympus_core.services.state import StateService
from tests.test_registry import gaming_telemetry, hello, telemetry


class GamingSessionTests(unittest.TestCase):
    def test_session_is_stable_until_game_ends_then_restarts(self) -> None:
        current = [datetime(2026, 8, 22, 18, 42, tzinfo=timezone.utc)]
        registry = AgentRegistry()
        gaming = GamingSessionService(clock=lambda: current[0])
        state_service = StateService(registry, gaming=gaming)
        registry.register(hello("win-test"))
        registry.update("win-test", gaming_telemetry(fps=143.7))

        first = state_service.current().gaming
        current[0] += timedelta(minutes=20)
        second = state_service.current().gaming
        self.assertEqual(first.session_started_at, second.session_started_at)
        self.assertEqual(second.fps, 143.7)

        registry.update("win-test", telemetry("idle"))
        self.assertIsNone(state_service.current().gaming)
        current[0] += timedelta(minutes=1)
        registry.update("win-test", gaming_telemetry())
        restarted = state_service.current().gaming
        self.assertEqual(restarted.session_started_at, current[0])


if __name__ == "__main__":
    unittest.main()
