from olympus_core.models.football import FootballState


class FootballStateStore:
    def __init__(self) -> None:
        self._state: FootballState | None = None

    def update(self, state: FootballState) -> None:
        self._state = state

    def get(self) -> FootballState | None:
        return self._state
