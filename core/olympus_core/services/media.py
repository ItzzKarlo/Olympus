from datetime import datetime, timezone
from olympus_core.models.media import MediaState


class MediaStateStore:
    """Cloud fallback and sticky selection of authenticated Agent observations."""

    def __init__(self, local_stale_seconds: float = 15.0, cloud_stale_seconds: float = 60.0) -> None:
        self._state: MediaState | None = None
        self._selected: tuple[str, str] | None = None
        self.local_stale_seconds = local_stale_seconds
        self.cloud_stale_seconds = cloud_stale_seconds
        self._last_local: MediaState | None = None
        self._last_local_seen: datetime | None = None

    def get(self, agents=(), now: datetime | None = None) -> MediaState | None:
        current = now or datetime.now(timezone.utc)
        cloud = self._state
        if cloud and cloud.observed_at.tzinfo is not None and (current - cloud.observed_at).total_seconds() > self.cloud_stale_seconds:
            cloud = cloud.model_copy(update={"is_playing": False, "available": False, "playback_status": "stale"})
        candidates = {}
        inactive = {}
        for agent in agents:
            if not agent.online:
                continue
            for state in agent.media_sessions:
                if state.observed_at.tzinfo is None:
                    continue
                age = (current - state.observed_at).total_seconds()
                if not -2 <= age <= self.local_stale_seconds or not state.available:
                    continue
                key = (agent.agent_id, state.session_id or state.provider)
                local = state.model_copy(update={"source": "local", "agent_id": agent.agent_id, "device": agent.hostname})
                if state.is_playing and state.playback_status == "playing" and state.track:
                    candidates[key] = local
                elif state.playback_status in {"paused", "stopped"}:
                    inactive[key] = local
        if candidates:
            self._selected = self._selected if self._selected in candidates else min(candidates)
            selected = candidates[self._selected]
            self._last_local = selected
            self._last_local_seen = current
            # Enrich only an exact Spotify track identity. Never replace local timing/status.
            def track_id(state):
                return (state.track.id or "").rsplit(":", 1)[-1].rsplit("/", 1)[-1] if state.track else ""
            if cloud and cloud.available and "spotify" in selected.provider.casefold() and track_id(selected) and track_id(selected) == track_id(cloud):
                track = selected.track.model_copy(deep=True)
                if track.album is None:
                    track.album = cloud.track.album
                elif not track.album.artwork_url and cloud.track.album:
                    track.album.artwork_url = cloud.track.album.artwork_url
                selected = selected.model_copy(update={"track": track, "queue": cloud.queue, "context": cloud.context})
            return selected
        if inactive:
            # A desktop pause overrides only that known cloud device; phone playback survives.
            if cloud and cloud.available and cloud.is_playing:
                same_device = [inactive[key] for key in sorted(inactive) if cloud.device and cloud.device == inactive[key].device]
                return same_device[0] if same_device else cloud
            self._selected = self._selected if self._selected in inactive else min(inactive)
            self._last_local = None
            return inactive[self._selected]
        if cloud and cloud.available and cloud.is_playing:
            return cloud
        if self._last_local and self._last_local_seen and (current - self._last_local_seen).total_seconds() <= 3 and (current - self._last_local.observed_at).total_seconds() <= self.local_stale_seconds:
            return self._last_local
        self._selected = None
        return cloud

    def update(self, state: MediaState) -> None:
        self._state = state
