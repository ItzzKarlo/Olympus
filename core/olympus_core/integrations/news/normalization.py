import calendar
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from olympus_core.config import NewsFeedSettings
from olympus_core.models.news import NewsArticle, NewsSource, NewsTopic


TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}
TOPIC_KEYWORDS: dict[NewsTopic, tuple[str, ...]] = {
    NewsTopic.GERMANY: ("germany", "german", "deutschland", "bundestag", "bundesrat"),
    NewsTopic.LOCAL: ("munich", "münchen", "bavaria", "bayern", "zagreb", "croatia", "kroatien"),
    NewsTopic.POLITICS: ("election", "government", "minister", "parliament", "wahl", "regierung", "kanzler"),
    NewsTopic.ECONOMY: ("economy", "inflation", "market", "bank", "wirtschaft", "börse"),
    NewsTopic.TECHNOLOGY: ("technology", "software", "cyber", "internet", "ai", "chip", "technologie"),
    NewsTopic.SCIENCE: ("science", "research", "space", "climate", "wissenschaft", "forschung"),
    NewsTopic.WEATHER: ("weather", "storm", "flood", "wildfire", "wetter", "sturm", "hochwasser"),
    NewsTopic.TRANSPORT: ("rail", "train", "airport", "transport", "verkehr", "bahn", "zug"),
    NewsTopic.SPORTS: ("football", "bundesliga", "champions league", "sport", "bayern munich", "fc bayern"),
    NewsTopic.ENTERTAINMENT: ("film", "music", "television", "celebrity", "kino", "musik"),
}


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored_depth += 1
            return
        if tag in {"br", "p", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored_depth > 0:
            self.ignored_depth -= 1


def clean_text(value: Any, *, limit: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    parser = _PlainText()
    try:
        parser.feed(value)
        text = " ".join("".join(parser.parts).split())
    except Exception:
        text = " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())
    if not text:
        return None
    if limit is not None and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return text


def canonicalize_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = urlencode([
        (key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMETERS and not key.casefold().startswith("utm_")
    ])
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, query, ""))


def normalize_headline(value: str) -> str:
    return " ".join(re.findall(r"[\wÀ-ž]+", value.casefold()))


def _published(entry: Any) -> datetime | None:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(field)
        if value:
            try:
                return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
            except (OverflowError, TypeError, ValueError):
                continue
    return None


def classify_topic(headline: str, categories: list[str], feed: NewsFeedSettings) -> NewsTopic:
    configured = (feed.topic or "").casefold()
    if configured in {topic.value for topic in NewsTopic}:
        return NewsTopic(configured)
    category_corpus = " ".join(categories).casefold()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if topic.value in category_corpus or any(re.search(rf"\b{re.escape(keyword)}\b", category_corpus) for keyword in keywords):
            return topic
    corpus = headline.casefold()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", corpus) for keyword in keywords):
            return topic
    return NewsTopic.WORLD if "world" in corpus else NewsTopic.OTHER


def normalize_entry(entry: Any, feed: NewsFeedSettings, observed_at: datetime) -> NewsArticle | None:
    headline = clean_text(entry.get("title"), limit=240)
    canonical = canonicalize_url(entry.get("link"))
    if headline is None or canonical is None:
        return None
    provider_id = clean_text(entry.get("id") or entry.get("guid"), limit=500)
    categories = [
        value for tag in entry.get("tags", [])
        if (value := clean_text(tag.get("term") if isinstance(tag, dict) else None, limit=80))
    ]
    identity = f"{feed.id}|{provider_id or canonical or normalize_headline(headline)}"
    source = NewsSource(
        id=feed.id, name=feed.name, language=feed.language,
        region=feed.region, trust=feed.trust,
    )
    try:
        return NewsArticle(
            id=sha256(identity.encode()).hexdigest()[:24],
            provider_id=provider_id,
            headline=headline,
            source=source,
            url=canonical,
            canonical_url=canonical,
            published_at=_published(entry),
            observed_at=observed_at,
            summary=clean_text(entry.get("summary") or entry.get("description"), limit=420),
            language=feed.language,
            categories=categories,
            topic=classify_topic(headline, categories, feed),
        )
    except ValueError:
        return None


def parse_feed(content: bytes, feed: NewsFeedSettings, observed_at: datetime) -> list[NewsArticle]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Malformed RSS/Atom feed: {parsed.bozo_exception}")
    return [article for entry in parsed.entries[:50] if (article := normalize_entry(entry, feed, observed_at))]
