from typing import Protocol

from olympus_core.models.football import ProviderFootballSnapshot


class FootballProvider(Protocol):
    minimum_poll_seconds: float
    post_match_minimum_poll_seconds: float

    async def fetch(self) -> ProviderFootballSnapshot: ...
    async def aclose(self) -> None: ...


class FootballProviderError(RuntimeError):
    pass


class FootballRateLimitError(FootballProviderError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after
