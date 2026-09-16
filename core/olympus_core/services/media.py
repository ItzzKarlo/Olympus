from datetime import datetime, timezone
from olympus_core.models.media import MediaState


class MediaStateStore:
    """Cloud snapshot plus deterministic selection of authenticated Agent observations."""

    def __init__(self, local_stale_seconds: float = 15.0) -> None:
        self._state: MediaState | None = None
        self._selected: tuple[str, str] | None = None
        self.local_stale_seconds = local_stale_seconds

    def get(self, agents=(), now: datetime | None = None) -> MediaState | None:
        current = now or datetime.now(timezone.utc)
        candidates = {}
        for agent in agents:
            if not agent.online:
                continue
            for state in agent.media_sessions:
                if state.observed_at.tzinfo is None:
                    continue
                age = (current - state.observed_at).total_seconds()
                if not -2 <= age <= self.local_stale_seconds or not state.available:
                    continue
                if state.is_playing and state.playback_status == "playing" and state.track:
                    key = (agent.agent_id, state.session_id or state.provider)
                    candidates[key] = state.model_copy(update={"source": "local", "agent_id": agent.agent_id, "device": agent.hostname})
        if candidates:
            # Retain the selected device while it confirms playback; lexical tie-break on first selection.
            self._selected = self._selected if self._selected in candidates else min(candidates)
            return candidates[self._selected]
        self._selected = None
        state = self._state
        if state and state.observed_at.tzinfo is not None and (current - state.observed_at).total_seconds() > 60:
            return state.model_copy(update={"is_playing": False, "available": False, "playback_status": "stale"})
        return state

    def update(self, state: MediaState) -> None:
        self._state = state
