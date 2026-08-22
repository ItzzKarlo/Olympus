import asyncio
from datetime import datetime, timezone

import httpx

from olympus_core.config import NewsSettings
from olympus_core.integrations.news.base import NewsFeedResult
from olympus_core.integrations.news.normalization import parse_feed


class RssNewsProvider:
    """Polite, conditional RSS/Atom provider with per-feed failure isolation."""

    def __init__(self, settings: NewsSettings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            follow_redirects=True,
            headers={"User-Agent": "Olympus/0.14 (+local ambient display)"},
        )
        self._owns_client = client is None
        self._validators: dict[str, tuple[str | None, str | None]] = {}

    async def _fetch_feed(self, feed) -> NewsFeedResult:
        observed_at = datetime.now(timezone.utc)
        etag, modified = self._validators.get(feed.id, (None, None))
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
        try:
            response = await self._client.get(feed.url, headers=headers)
            if response.status_code == 304:
                return NewsFeedResult(feed=feed, observed_at=observed_at, not_modified=True)
            response.raise_for_status()
            articles = parse_feed(response.content, feed, observed_at)
            self._validators[feed.id] = (response.headers.get("ETag"), response.headers.get("Last-Modified"))
            return NewsFeedResult(feed=feed, observed_at=observed_at, articles=articles)
        except Exception as error:
            return NewsFeedResult(feed=feed, observed_at=observed_at, error=str(error)[:240])

    async def fetch(self) -> list[NewsFeedResult]:
        return list(await asyncio.gather(*(self._fetch_feed(feed) for feed in self._settings.feeds)))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
