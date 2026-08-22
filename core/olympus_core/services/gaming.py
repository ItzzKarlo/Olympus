from collections.abc import Callable
from datetime import datetime, timezone

from olympus_core.models.agent import RegisteredAgent
from pydantic import ValidationError

from olympus_core.models.minecraft import MinecraftState
from olympus_core.models.state import GamingIntegration, GamingState
from olympus_core.models.telemetry import ActivityMode
from olympus_core.services.mode_resolver import ModeResolution


class GamingSessionService:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._session: GamingState | None = None
        self._session_key: tuple[str, str] | None = None

    def update(
        self,
        resolution: ModeResolution,
        agents: list[RegisteredAgent],
    ) -> GamingState | None:
        if resolution.mode != ActivityMode.GAMING or resolution.active_device is None:
            self._session = None
            self._session_key = None
            return None
        agent = next(
            (item for item in agents if item.agent_id == resolution.active_device),
            None,
        )
        game = agent.activity.game if agent and agent.activity else None
        if game is None:
            self._session = None
            self._session_key = None
            return None
        key = (agent.agent_id, game.id)
        integration = None
        minecraft = None
        snapshot = agent.integrations.get("minecraft")
        if game.id == "minecraft" and snapshot is not None:
            integration = GamingIntegration(
                type="minecraft",
                available=snapshot.available,
                connected=snapshot.connected,
                last_seen=snapshot.last_seen,
                observer=snapshot.observer,
            )
            if snapshot.available and snapshot.payload is not None:
                try:
                    player_state = MinecraftState.model_validate({
                        **snapshot.payload,
                        "observed_at": snapshot.last_seen,
                    })
                    health = player_state.player.health
                    maximum = player_state.player.max_health
                    minecraft = player_state.model_copy(update={
                        "low_health": health is not None
                        and maximum is not None
                        and maximum > 0
                        and health / maximum <= 0.25,
                    })
                except ValidationError:
                    integration = integration.model_copy(update={"available": False})
        if self._session is None or self._session_key != key:
            self._session = GamingState(
                game=game,
                session_started_at=self._clock(),
                fps=agent.activity.fps,
                integration=integration,
                minecraft=minecraft,
            )
            self._session_key = key
        elif (
            self._session.fps != agent.activity.fps
            or self._session.integration != integration
            or self._session.minecraft != minecraft
        ):
            self._session = self._session.model_copy(
                update={
                    "fps": agent.activity.fps,
                    "integration": integration,
                    "minecraft": minecraft,
                }
            )
        return self._session
