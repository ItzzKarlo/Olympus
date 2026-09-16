from datetime import datetime
from olympus_core.models.football import FootballState


class FootballStateStore:
    def __init__(self, stale_seconds: float = 60, unavailable_seconds: float = 900) -> None:
        self._state: FootballState | None = None
        self.stale_seconds = stale_seconds
        self.unavailable_seconds = unavailable_seconds

    def update(self, state: FootballState) -> None:
        self._state = state

    def get(self, now: datetime | None = None) -> FootballState | None:
        state = self._state
        if state is None or now is None:
            return state
        age = (now - state.observed_at).total_seconds()
        if age <= self.stale_seconds or state.matchday is None:
            return state
        context = state.matchday.model_copy(update={"stale": True, "result": "unknown"})
        expired = age > self.unavailable_seconds
        return state.model_copy(update={"stale": True, "available": state.available and not expired,
            "matchday": None if expired else context})
