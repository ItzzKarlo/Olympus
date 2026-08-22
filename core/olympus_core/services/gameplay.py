from datetime import datetime, timezone
from uuid import uuid4

from olympus_core.models.gameplay import GameplayEvent, GameplayEventSource
from olympus_core.models.integrations import AgentIntegrationEvent, AgentIntegrationState


class GameplayEventService:
    """Normalizes transient integration observations without creating alerts."""

    def __init__(self) -> None:
        self._minecraft_low_health: dict[str, bool] = {}

    def from_integration(
        self,
        agent_id: str,
        message: AgentIntegrationEvent,
    ) -> GameplayEvent:
        event_type = message.event
        prefix = f"{message.integration}."
        if not event_type.startswith(prefix):
            event_type = f"{prefix}{event_type}"
        return self._event(
            agent_id,
            message.integration,
            event_type,
            message.payload,
            message.observed_at,
        )

    def observe_state(
        self,
        agent_id: str,
        message: AgentIntegrationState,
    ) -> GameplayEvent | None:
        if message.integration != "minecraft":
            return None
        player = message.payload.get("player")
        if not isinstance(player, dict):
            return None
        health = player.get("health")
        maximum = player.get("max_health")
        low = (
            isinstance(health, (int, float))
            and not isinstance(health, bool)
            and isinstance(maximum, (int, float))
            and not isinstance(maximum, bool)
            and maximum > 0
            and health / maximum <= 0.25
        )
        previous = self._minecraft_low_health.get(agent_id, False)
        self._minecraft_low_health[agent_id] = low
        if low and not previous:
            return self._event(
                agent_id,
                "minecraft",
                "minecraft.player.low_health",
                {"health": float(health), "max_health": float(maximum)},
                message.observed_at,
            )
        return None

    @staticmethod
    def _event(
        agent_id: str,
        integration: str,
        event_type: str,
        payload: dict[str, object],
        timestamp: datetime | None = None,
    ) -> GameplayEvent:
        return GameplayEvent(
            id=uuid4().hex,
            type=event_type,
            timestamp=timestamp or datetime.now(timezone.utc),
            source=GameplayEventSource(
                agent_id=agent_id,
                integration=integration,
            ),
            payload=payload,
        )
