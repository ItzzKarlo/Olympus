import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from olympus_core.config import NewsFeedSettings, NewsSettings
from olympus_core.integrations.news.base import NewsFeedResult
from olympus_core.integrations.news.normalization import canonicalize_url, classify_topic, clean_text
from olympus_core.models.news import NewsArticle, NewsSource


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class FixtureNewsProvider:
    """Development-only file provider for the full Core-to-Display News path."""

    def __init__(self, settings: NewsSettings) -> None:
        self._settings = settings
        self._path = Path(settings.fixture_path or "")

    def _read(self) -> Any:
        return json.loads(self._path.read_text(encoding="utf-8"))

    async def fetch(self) -> list[NewsFeedResult]:
        observed_at = datetime.now(timezone.utc)
        try:
            payload = await asyncio.to_thread(self._read)
        except Exception as error:
            feed = NewsFeedSettings(id="fixture", name="Fixture", url="https://fixture.invalid")
            return [NewsFeedResult(feed=feed, observed_at=observed_at, error=str(error)[:240])]
        values = payload.get("feeds") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            feed = NewsFeedSettings(id="fixture", name="Fixture", url="https://fixture.invalid")
            return [NewsFeedResult(feed=feed, observed_at=observed_at, error="Invalid News fixture")]
        configured = {feed.id: feed for feed in self._settings.feeds}
        results: list[NewsFeedResult] = []
        for block in values:
            if not isinstance(block, dict):
                continue
            identifier = str(block.get("id", "fixture")).strip() or "fixture"
            feed = configured.get(identifier) or NewsFeedSettings(
                id=identifier,
                name=str(block.get("name", identifier)).strip() or identifier,
                url="https://fixture.invalid",
                language=str(block.get("language", self._settings.default_language)),
                trust=float(block.get("trust", 1.0)),
                region=str(block.get("region", "")).strip().upper() or None,
                topic=str(block.get("topic", "")).strip().lower() or None,
            )
            if block.get("error"):
                results.append(NewsFeedResult(feed=feed, observed_at=observed_at, error=str(block["error"])))
                continue
            articles: list[NewsArticle] = []
            for raw in block.get("articles", []):
                if not isinstance(raw, dict):
                    continue
                headline = clean_text(raw.get("headline"), limit=240)
                canonical = canonicalize_url(raw.get("url"))
                if headline is None or canonical is None:
                    continue
                categories = [str(value) for value in raw.get("categories", []) if isinstance(value, str)]
                provider_id = clean_text(raw.get("guid"), limit=500)
                identity = f"{feed.id}|{provider_id or canonical}"
                source = NewsSource(
                    id=feed.id, name=feed.name, language=feed.language,
                    region=feed.region, trust=feed.trust,
                )
                articles.append(NewsArticle(
                    id=sha256(identity.encode()).hexdigest()[:24],
                    provider_id=provider_id,
                    headline=headline,
                    source=source,
                    url=canonical,
                    canonical_url=canonical,
                    published_at=_datetime(raw.get("published_at")),
                    observed_at=observed_at,
                    summary=clean_text(raw.get("summary"), limit=420),
                    language=str(raw.get("language", feed.language)),
                    categories=categories,
                    topic=classify_topic(headline, categories, feed),
                ))
            results.append(NewsFeedResult(
                feed=feed,
                observed_at=observed_at,
                articles=articles,
                not_modified=bool(block.get("not_modified", False)),
            ))
        return results

    async def aclose(self) -> None:
        pass
