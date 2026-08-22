from olympus_core.models.news import NewsState


class NewsStateStore:
    def __init__(self) -> None:
        self._state: NewsState | None = None

    def update(self, state: NewsState) -> None:
        self._state = state

    def get(self) -> NewsState | None:
        return self._state
