from datetime import datetime, timezone
import unittest

from olympus_core.models.integrations import (
    AgentIntegrationEvent,
    AgentIntegrationState,
    IntegrationObserver,
)
from olympus_core.services.gameplay import GameplayEventService


OBSERVER = IntegrationObserver(
    id="minecraft-fabric",
    name="Minecraft Fabric",
    version="0.1.0",
)


def state(health: float, maximum: float = 20) -> AgentIntegrationState:
    return AgentIntegrationState(
        type="integration_state",
        integration="minecraft",
        observer=OBSERVER,
        observed_at=datetime.now(timezone.utc),
        payload={"player": {"health": health, "max_health": maximum}},
    )


class GameplayEventTests(unittest.TestCase):
    def test_low_health_is_an_edge_event(self) -> None:
        service = GameplayEventService()
        self.assertIsNone(service.observe_state("win", state(6)))
        event = service.observe_state("win", state(5))
        self.assertEqual(event.type, "minecraft.player.low_health")
        self.assertIsNone(service.observe_state("win", state(4)))
        self.assertIsNone(service.observe_state("win", state(8)))
        self.assertEqual(
            service.observe_state("win", state(5)).type,
            "minecraft.player.low_health",
        )

    def test_integration_event_is_gameplay_not_infrastructure_alert(self) -> None:
        service = GameplayEventService()
        message = AgentIntegrationEvent(
            type="integration_event",
            integration="minecraft",
            event="minecraft.player.damage_taken",
            observed_at=datetime.now(timezone.utc),
            payload={"amount": 3, "health_after": 17},
        )
        event = service.from_integration("win", message)
        self.assertEqual(event.category, "gameplay")
        self.assertEqual(event.source.agent_id, "win")
        self.assertEqual(event.payload["amount"], 3)


if __name__ == "__main__":
    unittest.main()
