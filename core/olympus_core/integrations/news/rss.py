import asyncio
from datetime import datetime, timedelta, timezone
import math
from email.utils import parsedate_to_datetime

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
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, datetime] = {}
        self._validators: dict[str, tuple[str | None, str | None]] = {}

    async def _fetch_feed(self, feed) -> NewsFeedResult:
        observed_at = datetime.now(timezone.utc)
        retry_at = self._retry_at.get(feed.id)
        if retry_at and observed_at < retry_at:
            return NewsFeedResult(feed=feed, observed_at=observed_at, error="retry_deferred", retry_at=retry_at)
        etag, modified = self._validators.get(feed.id, (None, None))
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
        try:
            response = await self._client.get(feed.url, headers=headers)
            if response.status_code == 304:
                self._failures.pop(feed.id, None)
                self._retry_at.pop(feed.id, None)
                return NewsFeedResult(feed=feed, observed_at=observed_at, not_modified=True)
            response.raise_for_status()
            articles = parse_feed(response.content, feed, observed_at)
            self._failures.pop(feed.id, None)
            self._retry_at.pop(feed.id, None)
            self._validators[feed.id] = (response.headers.get("ETag"), response.headers.get("Last-Modified"))
            return NewsFeedResult(feed=feed, observed_at=observed_at, articles=articles)
        except Exception as error:
            count = min(6, self._failures.get(feed.id, 0) + 1)
            self._failures[feed.id] = count
            delay = min(1800, self._settings.poll_seconds * 2 ** (count - 1))
            if isinstance(error, httpx.HTTPStatusError) and error.response.status_code in {429, 503}:
                raw = error.response.headers.get("Retry-After", "0")
                try:
                    restriction = float(raw)
                except ValueError:
                    try:
                        restriction = (parsedate_to_datetime(raw) - observed_at).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        restriction = 0
                if math.isfinite(restriction):
                    delay = max(delay, min(restriction, 86400 * 30))
            self._retry_at[feed.id] = observed_at + timedelta(seconds=delay)
            return NewsFeedResult(feed=feed, observed_at=observed_at, retry_at=self._retry_at[feed.id], error=f"http_{error.response.status_code}" if isinstance(error, httpx.HTTPStatusError) else "parse_failure" if isinstance(error, ValueError) else "fetch_failure")

    async def fetch(self) -> list[NewsFeedResult]:
        return list(await asyncio.gather(*(self._fetch_feed(feed) for feed in self._settings.feeds)))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
