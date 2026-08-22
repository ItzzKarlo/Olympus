from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from hashlib import sha256
import math
import re

from olympus_core.config import NewsSettings
from olympus_core.integrations.news.base import NewsFeedResult
from olympus_core.integrations.news.normalization import normalize_headline
from olympus_core.models.news import (
    NewsArticle,
    NewsCluster,
    NewsFeedHealth,
    NewsImportance,
    NewsImportanceLevel,
    NewsState,
    NewsTopic,
)


STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is", "of", "on", "or", "the", "to", "with",
    "am", "an", "auf", "aus", "bei", "das", "der", "die", "ein", "eine", "für", "im", "in", "ist", "mit", "und", "von", "zu",
}
BREAKING_TERMS = {
    "breaking", "developing", "emergency", "evacuation", "explosion", "earthquake", "attack", "resigns", "resigned", "outage",
    "eilmeldung", "notfall", "evakuierung", "explosion", "erdbeben", "angriff", "rücktritt", "zurückgetreten", "ausfall",
}


def _tokens(headline: str) -> set[str]:
    return {token for token in normalize_headline(headline).split() if len(token) > 2 and token not in STOPWORDS}


def _same_story(left: NewsArticle, right: NewsArticle) -> bool:
    if left.canonical_url == right.canonical_url:
        return True
    left_title = normalize_headline(left.headline)
    right_title = normalize_headline(right.headline)
    if left_title == right_title:
        return True
    left_tokens, right_tokens = _tokens(left.headline), _tokens(right.headline)
    common = left_tokens & right_tokens
    union = left_tokens | right_tokens
    if len(common) < 4 or not union:
        return False
    proximity = abs((left.published_at or left.observed_at) - (right.published_at or right.observed_at))
    if proximity > timedelta(hours=12):
        return False
    jaccard = len(common) / len(union)
    sequence = SequenceMatcher(None, left_title, right_title).ratio()
    return jaccard >= 0.75 and sequence >= 0.83


def _representative(articles: list[NewsArticle]) -> NewsArticle:
    return max(
        articles,
        key=lambda article: (
            article.source.trust,
            article.published_at or article.observed_at,
            article.source.id,
        ),
    )


def _cluster_topic(articles: list[NewsArticle], representative: NewsArticle) -> NewsTopic:
    counts: dict[NewsTopic, int] = {}
    for article in articles:
        counts[article.topic] = counts.get(article.topic, 0) + 1
    return max(counts, key=lambda topic: (counts[topic], topic == representative.topic, topic.value))


def _importance(
    articles: list[NewsArticle],
    topic: NewsTopic,
    settings: NewsSettings,
    now: datetime,
) -> NewsImportance:
    sources = {article.source.id: article.source for article in articles}
    latest = max((article.published_at or article.observed_at) for article in articles)
    age_hours = max(0.0, (now - latest).total_seconds() / 3_600)
    recency = 0.24 * max(0.0, 1 - age_hours / 24)
    source_count = 0.08 * min(4, max(0, len(sources) - 1))
    average_trust = sum(source.trust for source in sources.values()) / max(1, len(sources))
    trust = 0.12 * min(1.0, average_trust / 1.5)
    topic_factor = 0.08 if topic in {
        NewsTopic.WORLD, NewsTopic.GERMANY, NewsTopic.LOCAL, NewsTopic.POLITICS,
        NewsTopic.WEATHER, NewsTopic.TRANSPORT,
    } else 0.06
    local = 0.12 if topic in {NewsTopic.GERMANY, NewsTopic.LOCAL} or any(
        source.region in settings.local_regions for source in sources.values()
    ) else 0.0
    corpus = " ".join(article.headline.casefold() for article in articles)
    breaking = 0.10 if any(re.search(rf"\b{re.escape(term)}\b", corpus) for term in BREAKING_TERMS) else 0.0
    span_minutes = (
        max(article.observed_at for article in articles) - min(article.observed_at for article in articles)
    ).total_seconds() / 60
    velocity = 0.12 if len(sources) >= 3 and span_minutes <= 30 else 0.05 if len(sources) >= 2 and span_minutes <= 30 else 0.0
    base = 0.10
    factors = {
        "base": base,
        "recency": recency,
        "source_count": source_count,
        "source_trust": trust,
        "topic": topic_factor,
        "local_relevance": local,
        "developing_language": breaking,
        "source_velocity": velocity,
    }
    interest = settings.interest_weight(topic.value)
    raw_score = sum(factors.values()) * interest
    factors["interest_multiplier"] = interest
    score = min(1.0, max(0.0, raw_score))
    thresholds = settings.presentation
    if score >= thresholds.major_threshold and len(sources) >= 3 and breaking > 0:
        level = NewsImportanceLevel.MAJOR
    elif score >= thresholds.important_threshold:
        level = NewsImportanceLevel.IMPORTANT
    elif score >= thresholds.notable_threshold:
        level = NewsImportanceLevel.NOTABLE
    else:
        level = NewsImportanceLevel.AMBIENT

    # Structured integrations and dedicated weather data remain authoritative.
    normalized = normalize_headline(corpus)
    if topic == NewsTopic.SPORTS and any(value in normalized for value in ("bayern", "fc bayern")):
        level = min(level, NewsImportanceLevel.NOTABLE, key=lambda value: list(NewsImportanceLevel).index(value))
    if topic == NewsTopic.WEATHER and breaking == 0:
        level = min(level, NewsImportanceLevel.NOTABLE, key=lambda value: list(NewsImportanceLevel).index(value))
    return NewsImportance(
        score=round(score, 3),
        level=level,
        factors={key: round(value, 3) for key, value in factors.items()},
    )


class NewsEngine:
    """Bounded, deterministic article memory, clustering, and importance ranking."""

    def __init__(self, settings: NewsSettings) -> None:
        self._settings = settings
        self._articles: dict[str, NewsArticle] = {}
        self._clusters: list[NewsCluster] = []
        self._health: dict[str, NewsFeedHealth] = {
            feed.id: NewsFeedHealth(feed_id=feed.id) for feed in settings.feeds
        }
        self._last_success_at: datetime | None = None

    def _build_clusters(self, now: datetime) -> list[NewsCluster]:
        groups: list[list[NewsArticle]] = []
        for article in sorted(self._articles.values(), key=lambda item: (item.observed_at, item.id)):
            target = next((group for group in groups if any(_same_story(article, existing) for existing in group)), None)
            if target is None:
                groups.append([article])
            else:
                target.append(article)

        previous_by_article = {
            article.id: cluster for cluster in self._clusters for article in cluster.articles
        }
        clusters: list[NewsCluster] = []
        for articles in groups:
            prior = next((previous_by_article[item.id] for item in articles if item.id in previous_by_article), None)
            representative = _representative(articles)
            topic = _cluster_topic(articles, representative)
            source_map = {article.source.id: article.source for article in articles}
            first_seen = min(article.observed_at for article in articles)
            latest_seen = max(article.observed_at for article in articles)
            if prior is not None:
                identifier = prior.id
                first_seen = min(first_seen, prior.first_seen_at)
            else:
                identity = representative.canonical_url or normalize_headline(representative.headline)
                identifier = sha256(identity.encode()).hexdigest()[:24]
            clusters.append(NewsCluster(
                id=identifier,
                headline=representative.headline,
                summary=representative.summary,
                language=representative.language,
                topic=topic,
                articles=sorted(articles, key=lambda item: item.published_at or item.observed_at, reverse=True),
                sources=sorted(source_map.values(), key=lambda item: (-item.trust, item.name)),
                first_seen_at=first_seen,
                latest_seen_at=latest_seen,
                importance=_importance(articles, topic, self._settings, now),
            ))
        return sorted(
            clusters,
            key=lambda cluster: (cluster.importance.score, cluster.latest_seen_at, cluster.id),
            reverse=True,
        )

    def update(self, results: list[NewsFeedResult], now: datetime | None = None) -> NewsState:
        current = now or datetime.now(timezone.utc)
        successful = False
        for result in results:
            health = self._health.setdefault(result.feed.id, NewsFeedHealth(feed_id=result.feed.id))
            if result.successful:
                successful = True
                self._last_success_at = max(self._last_success_at or result.observed_at, result.observed_at)
                self._health[result.feed.id] = health.model_copy(update={
                    "last_success_at": result.observed_at,
                    "last_error": None,
                    "stale": False,
                })
                for article in result.articles:
                    self._articles[article.id] = article
            else:
                last_success = health.last_success_at
                self._health[result.feed.id] = health.model_copy(update={
                    "last_error": result.error,
                    "stale": last_success is None or current - last_success > timedelta(seconds=self._settings.stale_seconds),
                })

        cutoff = current - timedelta(seconds=self._settings.retention_seconds)
        self._articles = {
            identifier: article for identifier, article in self._articles.items()
            if (article.published_at or article.observed_at) >= cutoff
        }
        if len(self._articles) > 300:
            retained = sorted(self._articles.values(), key=lambda item: item.published_at or item.observed_at, reverse=True)[:300]
            self._articles = {article.id: article for article in retained}
        self._clusters = self._build_clusters(current)

        age = math.inf if self._last_success_at is None else (current - self._last_success_at).total_seconds()
        stale = not successful and age > self._settings.stale_seconds
        available = bool(self._clusters) and age <= self._settings.unavailable_seconds
        return NewsState(
            available=available,
            last_updated_at=self._last_success_at,
            stale=stale,
            top_stories=self._clusters[:20],
            ambient=self._clusters[:self._settings.presentation.ambient_limit],
            feed_health=list(self._health.values()),
        )
