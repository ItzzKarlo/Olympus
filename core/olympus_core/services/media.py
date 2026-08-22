from olympus_core.models.media import MediaState


class MediaStateStore:
    """In-memory snapshot shared by collectors and the state resolver."""

    def __init__(self) -> None:
        self._state: MediaState | None = None

    def get(self) -> MediaState | None:
        return self._state

    def update(self, state: MediaState) -> None:
        self._state = state
