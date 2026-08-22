from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from olympus_core.config import NewsFeedSettings
from olympus_core.models.news import NewsArticle


@dataclass(slots=True)
class NewsFeedResult:
    feed: NewsFeedSettings
    observed_at: datetime
    articles: list[NewsArticle] = field(default_factory=list)
    not_modified: bool = False
    error: str | None = None

    @property
    def successful(self) -> bool:
        return self.error is None


class NewsProvider(Protocol):
    async def fetch(self) -> list[NewsFeedResult]: ...

    async def aclose(self) -> None: ...
