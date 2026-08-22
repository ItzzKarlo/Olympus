from datetime import datetime, timedelta, timezone
import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import NightSettings
from olympus_core.services.gaming import GamingSessionService
from olympus_core.services.state import StateService
from olympus_core.services.time_policy import TimePolicyService
from olympus_core.models.integrations import IntegrationObserver, IntegrationSnapshot
from tests.test_registry import gaming_telemetry, hello, telemetry


class GamingSessionTests(unittest.TestCase):
    def test_policy_boundary_does_not_reset_active_game_session(self) -> None:
        current = [datetime(2026, 8, 17, 19, 59, tzinfo=timezone.utc)]
        registry = AgentRegistry()
        gaming = GamingSessionService(clock=lambda: current[0])
        state_service = StateService(
            registry,
            gaming=gaming,
            timezone="Europe/Zagreb",
            time_policy=TimePolicyService(NightSettings(), "Europe/Zagreb"),
            clock=lambda: current[0],
        )
        registry.register(hello("win-test"))
        registry.update("win-test", gaming_telemetry())

        before = state_service.current()
        current[0] += timedelta(minutes=2)
        after = state_service.current()

        self.assertFalse(before.time_policy.is_night)
        self.assertTrue(after.time_policy.is_night)
        self.assertEqual(before.mode, after.mode)
        self.assertEqual(before.gaming.session_started_at, after.gaming.session_started_at)

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

    def test_minecraft_integration_enriches_then_falls_back_to_generic(self) -> None:
        registry = AgentRegistry()
        state_service = StateService(registry)
        registry.register(hello("win-minecraft"))
        registry.update(
            "win-minecraft",
            gaming_telemetry("minecraft", "Minecraft"),
        )
        self.assertEqual(state_service.current().mode, "gaming")
        self.assertIsNone(state_service.current().gaming.minecraft)

        agent = registry.get("win-minecraft")
        agent.integrations["minecraft"] = IntegrationSnapshot(
            available=True,
            connected=True,
            last_seen=datetime.now(timezone.utc),
            observer=IntegrationObserver(
                id="minecraft-fabric",
                name="Minecraft Fabric",
                version="0.1.0",
            ),
            payload={
                "connection": {
                    "type": "multiplayer",
                    "server_name": "Hermes SMP",
                    "server_address": "minecraft.local",
                    "world_name": None,
                },
                "world": {"dimension": "mod:moon", "biome": "mod:crystal_fields"},
                "player": {
                    "position": {"x": -1432.4, "y": 71, "z": 825.8},
                    "health": 5,
                    "max_health": 20,
                    "food": 14,
                    "max_food": 20,
                    "armor": 16,
                    "experience": {"level": 38, "progress": 0.42},
                    "game_mode": "survival",
                },
            },
        )
        enriched = state_service.current().gaming
        self.assertTrue(enriched.integration.available)
        self.assertEqual(enriched.minecraft.world.dimension, "mod:moon")
        self.assertTrue(enriched.minecraft.low_health)

        agent.integrations["minecraft"] = agent.integrations["minecraft"].model_copy(
            update={"available": False, "connected": False, "payload": None}
        )
        fallback = state_service.current()
        self.assertEqual(fallback.mode, "gaming")
        self.assertEqual(fallback.gaming.game.id, "minecraft")
        self.assertIsNone(fallback.gaming.minecraft)


if __name__ == "__main__":
    unittest.main()
