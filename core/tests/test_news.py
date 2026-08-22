import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import httpx

from olympus_core.config import (
    NewsFeedSettings,
    NewsPresentationSettings,
    NewsSettings,
    parse_core_config,
)
from olympus_core.integrations.news.base import NewsFeedResult
from olympus_core.integrations.news.collector import NewsCollector
from olympus_core.integrations.news.engine import NewsEngine
from olympus_core.integrations.news.normalization import canonicalize_url, parse_feed
from olympus_core.integrations.news.rss import RssNewsProvider
from olympus_core.models.news import NewsArticle, NewsImportanceLevel, NewsSource, NewsTopic
from olympus_core.persistence.database import Database
from olympus_core.persistence.news_memory import NewsMemoryRepository


NOW = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
FEEDS = (
    NewsFeedSettings(id="reuters", name="Reuters", url="https://news.test/reuters.xml", language="en", trust=1.0),
    NewsFeedSettings(id="tagesschau", name="Tagesschau", url="https://news.test/tagesschau.xml", language="de", trust=1.0, region="DE"),
    NewsFeedSettings(id="bbc", name="BBC", url="https://news.test/bbc.xml", language="en", trust=1.0),
)
SETTINGS = NewsSettings(enabled=True, feeds=FEEDS)


def article(
    source: NewsFeedSettings,
    headline: str,
    *,
    identifier: str | None = None,
    url: str | None = None,
    published_at: datetime = NOW,
    observed_at: datetime = NOW,
    topic: NewsTopic = NewsTopic.WORLD,
) -> NewsArticle:
    identity = identifier or f"{source.id}:{headline}"
    return NewsArticle(
        id=identity,
        provider_id=identity,
        headline=headline,
        source=NewsSource(
            id=source.id, name=source.name, language=source.language,
            trust=source.trust, region=source.region,
        ),
        url=url or f"https://news.test/{source.id}/{abs(hash(identity))}",
        canonical_url=url or f"https://news.test/{source.id}/{abs(hash(identity))}",
        published_at=published_at,
        observed_at=observed_at,
        language=source.language,
        topic=topic,
    )


def result(feed: NewsFeedSettings, *articles: NewsArticle, error: str | None = None, at: datetime = NOW) -> NewsFeedResult:
    return NewsFeedResult(feed=feed, observed_at=at, articles=list(articles), error=error)


class FeedNormalizationTests(unittest.TestCase):
    def test_rss_guid_date_summary_category_and_tracking_cleanup(self) -> None:
        content = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title>
        <item><guid>story-1</guid><title>Rail disruption across Munich</title>
        <link>https://example.com/story/?utm_source=rss&amp;keep=1#fragment</link>
        <pubDate>Sat, 22 Aug 2026 17:30:00 GMT</pubDate>
        <description><![CDATA[<p>Multiple <b>operators</b> report delays.</p><script>bad()</script>]]></description>
        <category>Transport</category></item></channel></rss>"""
        parsed = parse_feed(content, FEEDS[0], NOW)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].provider_id, "story-1")
        self.assertEqual(parsed[0].published_at, datetime(2026, 8, 22, 17, 30, tzinfo=timezone.utc))
        self.assertEqual(parsed[0].canonical_url, "https://example.com/story?keep=1")
        self.assertNotIn("<", parsed[0].summary)
        self.assertNotIn("bad()", parsed[0].summary)
        self.assertEqual(parsed[0].categories, ["Transport"])
        self.assertEqual(parsed[0].topic, NewsTopic.TRANSPORT)

    def test_atom_missing_id_and_date_still_has_stable_article(self) -> None:
        feed = replace(FEEDS[1], topic="technology")
        content = b"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"><title>Technik</title><entry>
        <title>Neue Chip-Forschung in Deutschland</title>
        <link href="https://example.de/chip"/><summary>Kurze Zusammenfassung.</summary>
        </entry></feed>"""
        first = parse_feed(content, feed, NOW)[0]
        second = parse_feed(content, feed, NOW + timedelta(minutes=1))[0]

        self.assertEqual(first.id, second.id)
        self.assertIsNone(first.published_at)
        self.assertEqual(first.language, "de")
        self.assertEqual(first.topic, NewsTopic.TECHNOLOGY)

    def test_malformed_entries_are_skipped_and_malformed_document_fails(self) -> None:
        partial = b"<rss><channel><item><title>No link</title></item><item><title>Good</title><link>https://example.com/good</link></item></channel></rss>"
        self.assertEqual([item.headline for item in parse_feed(partial, FEEDS[0], NOW)], ["Good"])
        with self.assertRaisesRegex(ValueError, "Malformed"):
            parse_feed(b"not xml at all", FEEDS[0], NOW)

    def test_canonical_url_removes_only_obvious_tracking(self) -> None:
        value = canonicalize_url("HTTPS://Example.COM/a/?utm_campaign=x&article=7&fbclid=y#top")
        self.assertEqual(value, "https://example.com/a?article=7")


class ConditionalHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_etag_last_modified_and_304(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(200, headers={"ETag": '"abc"', "Last-Modified": "Sat, 22 Aug 2026 17:00:00 GMT"}, content=(
                    b"<rss><channel><item><title>Story</title><link>https://example.com/story</link></item></channel></rss>"
                ))
            return httpx.Response(304)

        provider = RssNewsProvider(
            replace(SETTINGS, feeds=(FEEDS[0],)),
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        first = await provider.fetch()
        second = await provider.fetch()

        self.assertEqual(len(first[0].articles), 1)
        self.assertTrue(second[0].not_modified)
        self.assertEqual(calls[1].headers["if-none-match"], '"abc"')
        self.assertEqual(calls[1].headers["if-modified-since"], "Sat, 22 Aug 2026 17:00:00 GMT")


class ClusteringAndImportanceTests(unittest.TestCase):
    def test_exact_and_conservative_fuzzy_clustering(self) -> None:
        engine = NewsEngine(SETTINGS)
        shared = "Major rail disruption affects southern Germany today"
        values = [
            result(FEEDS[0], article(FEEDS[0], shared, url="https://wire.test/story?utm_source=rss")),
            result(FEEDS[1], article(FEEDS[1], "Major rail disruption affects southern Germany today", url="https://tag.test/1")),
            result(FEEDS[2], article(FEEDS[2], "Major rail disruption affects southern Germany today as services stop", url="https://bbc.test/1")),
            result(FEEDS[0], article(FEEDS[0], "Germany announces election date", identifier="date")),
            result(FEEDS[1], article(FEEDS[1], "Germany announces election security measures", identifier="security")),
        ]
        state = engine.update(values, NOW)
        sizes = sorted(len(cluster.articles) for cluster in state.top_stories)
        self.assertEqual(sizes, [1, 1, 3])
        clustered = next(cluster for cluster in state.top_stories if len(cluster.articles) == 3)
        self.assertEqual(len(clustered.sources), 3)

    def test_importance_is_transparent_conservative_and_decays(self) -> None:
        ordinary = NewsEngine(SETTINGS).update([
            result(FEEDS[0], article(FEEDS[0], "A routine international standards meeting concludes")),
        ], NOW).top_stories[0]
        self.assertEqual(ordinary.importance.level, NewsImportanceLevel.AMBIENT)
        self.assertIn("recency", ordinary.importance.factors)

        sensational = NewsEngine(SETTINGS).update([
            result(FEEDS[0], article(FEEDS[0], "SHOCKING!!! Breaking update from a single source")),
        ], NOW).top_stories[0]
        self.assertNotEqual(sensational.importance.level, NewsImportanceLevel.MAJOR)

        old = NewsEngine(replace(SETTINGS, retention_seconds=72 * 3_600)).update([
            result(FEEDS[0], article(FEEDS[0], "Old world development", published_at=NOW - timedelta(hours=36))),
        ], NOW).top_stories[0]
        self.assertLess(old.importance.score, ordinary.importance.score)

    def test_multi_source_local_breaking_story_can_be_major(self) -> None:
        headline = "Breaking emergency closes major rail network across Germany"
        state = NewsEngine(SETTINGS).update([
            result(feed, article(feed, headline, identifier=feed.id, topic=NewsTopic.TRANSPORT))
            for feed in FEEDS
        ], NOW)
        cluster = state.top_stories[0]
        self.assertEqual(cluster.importance.level, NewsImportanceLevel.MAJOR)
        self.assertGreaterEqual(cluster.importance.factors["source_count"], 0.16)
        self.assertGreater(cluster.importance.factors["local_relevance"], 0)

    def test_topic_interest_changes_relevance_without_creating_truth_score(self) -> None:
        base = NewsEngine(SETTINGS).update([
            result(FEEDS[0], article(FEEDS[0], "New processor architecture reaches production", topic=NewsTopic.TECHNOLOGY)),
        ], NOW).top_stories[0]
        preferred_settings = replace(SETTINGS, interests=(("technology", 1.3),))
        preferred = NewsEngine(preferred_settings).update([
            result(FEEDS[0], article(FEEDS[0], "New processor architecture reaches production", topic=NewsTopic.TECHNOLOGY)),
        ], NOW).top_stories[0]
        self.assertGreater(preferred.importance.score, base.importance.score)

    def test_bayern_and_routine_weather_stay_below_takeover_level(self) -> None:
        for topic, headline in [
            (NewsTopic.SPORTS, "Breaking FC Bayern wins major Bundesliga match"),
            (NewsTopic.WEATHER, "Germany weather outlook calls for rain tomorrow"),
        ]:
            cluster = NewsEngine(SETTINGS).update([
                result(feed, article(feed, headline, identifier=feed.id, topic=topic)) for feed in FEEDS
            ], NOW).top_stories[0]
            with self.subTest(topic=topic):
                self.assertLessEqual(cluster.importance.level, NewsImportanceLevel.NOTABLE)

    def test_feed_failure_isolated_then_stale_and_unavailable(self) -> None:
        settings = replace(SETTINGS, stale_seconds=60, unavailable_seconds=120)
        engine = NewsEngine(settings)
        initial = engine.update([
            result(FEEDS[0], article(FEEDS[0], "Routine story")),
            result(FEEDS[1], error="broken"),
        ], NOW)
        self.assertTrue(initial.available)
        self.assertTrue(next(item for item in initial.feed_health if item.feed_id == "tagesschau").stale)
        failed = engine.update([result(feed, error="offline", at=NOW + timedelta(minutes=3)) for feed in FEEDS], NOW + timedelta(minutes=3))
        self.assertFalse(failed.available)
        self.assertTrue(failed.stale)
        self.assertTrue(failed.top_stories)


class StubProvider:
    def __init__(self, batches: list[list[NewsFeedResult]]) -> None:
        self.batches = batches

    async def fetch(self) -> list[NewsFeedResult]:
        return self.batches.pop(0)

    async def aclose(self) -> None:
        pass


class PresentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_suppression_then_edge_trigger_and_exact_expiry(self) -> None:
        settings = replace(SETTINGS, presentation=replace(
            SETTINGS.presentation, news_scene_seconds=0.05, major_scene_seconds=0.05,
        ))
        baseline = article(FEEDS[0], "Existing breaking emergency story", identifier="old")
        headline = "International leaders confirm broad emergency response plan"
        additions = [article(feed, headline, identifier=feed.id, topic=NewsTopic.WORLD) for feed in FEEDS]
        provider = StubProvider([
            [result(FEEDS[0], baseline)],
            [result(feed, item) for feed, item in zip(FEEDS, additions)],
            [NewsFeedResult(feed=feed, observed_at=NOW, not_modified=True) for feed in FEEDS],
        ])
        states, events = [], []
        collector = NewsCollector(settings, provider, states.append, events.append)

        initial = await collector.poll_once()
        self.assertIsNone(initial.presentation)
        active = await collector.poll_once()
        self.assertIsNotNone(active.presentation)
        self.assertEqual(len(events), 1)
        repeated = await collector.poll_once()
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(repeated.presentation)
        await asyncio.sleep(0.08)
        self.assertIsNone(states[-1].presentation)
        collector.stop()

    async def test_important_to_major_escalation_can_replace_during_cooldown(self) -> None:
        settings = replace(SETTINGS, presentation=replace(
            SETTINGS.presentation,
            important_threshold=0.65,
            major_threshold=0.80,
            news_scene_seconds=30,
            major_scene_seconds=30,
        ))
        title = "Emergency rail network disruption affects southern Germany today"
        one = article(FEEDS[0], title, identifier="one", topic=NewsTopic.TRANSPORT)
        two = article(FEEDS[1], title, identifier="two", topic=NewsTopic.TRANSPORT)
        three = article(FEEDS[2], title, identifier="three", topic=NewsTopic.TRANSPORT)
        provider = StubProvider([
            [result(FEEDS[0], one)],
            [result(FEEDS[1], two)],
            [result(FEEDS[2], three)],
        ])
        events = []
        collector = NewsCollector(settings, provider, lambda state: None, events.append)
        await collector.poll_once()
        important = await collector.poll_once()
        self.assertEqual(important.presentation.level, NewsImportanceLevel.IMPORTANT)
        major = await collector.poll_once()
        self.assertEqual(major.presentation.level, NewsImportanceLevel.MAJOR)
        self.assertEqual([event.type for event in events], ["news.story.important", "news.story.major"])
        collector.stop()

    async def test_presentation_memory_blocks_restart_repeat_but_allows_escalation(self) -> None:
        settings = replace(SETTINGS, presentation=replace(
            SETTINGS.presentation,
            important_threshold=0.65,
            major_threshold=0.80,
            news_scene_seconds=30,
            major_scene_seconds=30,
        ))
        baseline = article(FEEDS[0], "Routine standards meeting concludes", identifier="baseline")
        title = "Emergency rail network disruption affects southern Germany today"
        one = article(FEEDS[0], title, identifier="one", topic=NewsTopic.TRANSPORT)
        two = article(FEEDS[1], title, identifier="two", topic=NewsTopic.TRANSPORT)
        three = article(FEEDS[2], title, identifier="three", topic=NewsTopic.TRANSPORT)
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "core.db")
            database.initialize()
            memory = NewsMemoryRepository(database)
            first = NewsCollector(
                settings,
                StubProvider([
                    [result(FEEDS[0], baseline)],
                    [result(FEEDS[0], one), result(FEEDS[1], two)],
                ]),
                lambda state: None,
                lambda event: None,
                memory,
            )
            await first.poll_once()
            presented = await first.poll_once()
            self.assertEqual(presented.presentation.level, NewsImportanceLevel.IMPORTANT)
            first.stop()

            restarted = NewsCollector(
                settings,
                StubProvider([
                    [result(FEEDS[0], baseline)],
                    [result(FEEDS[0], one), result(FEEDS[1], two)],
                    [result(FEEDS[2], three)],
                ]),
                lambda state: None,
                lambda event: None,
                memory,
            )
            await restarted.poll_once()
            repeated = await restarted.poll_once()
            self.assertIsNone(repeated.presentation)
            escalated = await restarted.poll_once()
            self.assertEqual(escalated.presentation.level, NewsImportanceLevel.MAJOR)
            restarted.stop()


class NewsConfigTests(unittest.TestCase):
    def test_news_config_is_optional_and_parses_feeds_preferences_and_thresholds(self) -> None:
        self.assertFalse(parse_core_config({}).news.enabled)
        settings = parse_core_config({"news": {
            "enabled": True,
            "poll_minutes": 7,
            "retention_hours": 24,
            "local_regions": ["de", "HR"],
            "feeds": [{
                "id": "source", "name": "Source", "url": "https://example.com/feed.xml",
                "language": "de", "region": "de", "trust": 1.2, "topic": "germany",
            }],
            "interests": {"technology": 1.15},
            "presentation": {"ambient_limit": 2, "major_threshold": 0.9},
        }}).news
        self.assertTrue(settings.configured)
        self.assertEqual(settings.poll_seconds, 420)
        self.assertEqual(settings.retention_seconds, 86_400)
        self.assertEqual(settings.local_regions, ("DE", "HR"))
        self.assertEqual(settings.feeds[0].region, "DE")
        self.assertEqual(settings.interest_weight("technology"), 1.15)
        self.assertEqual(settings.presentation.ambient_limit, 2)
        self.assertEqual(settings.presentation.major_threshold, 0.9)


if __name__ == "__main__":
    unittest.main()
