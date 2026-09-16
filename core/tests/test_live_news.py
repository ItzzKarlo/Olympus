from datetime import timedelta
from dataclasses import replace
import unittest
from test_news import NOW, FEEDS, SETTINGS, article, result, StubProvider
from olympus_core.integrations.news.engine import NewsEngine
from olympus_core.integrations.news.collector import NewsCollector
from olympus_core.integrations.news.normalization import parse_feed
from olympus_core.models.news import NewsImportanceLevel
from olympus_core.services.mode_resolver import ModeResolver

class FreshnessTests(unittest.TestCase):
    def test_missing_date_does_not_become_new_and_failure_recovers(self):
        engine = NewsEngine(SETTINGS)
        item = article(FEEDS[0], 'Undated headline', identifier='stable', published_at=None)
        engine.update([result(FEEDS[0], item)], NOW)
        later = NOW + timedelta(hours=2)
        state = engine.update([result(FEEDS[0], item.model_copy(update={'observed_at': later}), at=later)], later)
        self.assertEqual(state.top_stories[0].first_seen_at, NOW)
        failed = engine.update([result(FEEDS[0], error='fetch_failure', at=later + timedelta(hours=2))], later + timedelta(hours=2))
        self.assertTrue(failed.stale)
        self.assertEqual(failed.feed_health[0].consecutive_failures, 1)
        recovered = engine.update([result(FEEDS[0], at=later + timedelta(hours=3))], later + timedelta(hours=3))
        self.assertFalse(recovered.stale)
        self.assertEqual(recovered.feed_health[0].consecutive_failures, 0)

    def test_future_publication_is_unknown(self):
        rss = b'<rss><channel><item><title>Story</title><link>https://example.com/a</link><pubDate>Sat, 22 Aug 2037 17:00:00 GMT</pubDate></item></channel></rss>'
        self.assertIsNone(parse_feed(rss, FEEDS[0], NOW)[0].published_at)

    def test_wire_attribution_is_one_report(self):
        title = 'Breaking earthquake prompts emergency evacuation across coastal region'
        state = NewsEngine(SETTINGS).update([
            result(feed, article(feed, title, summary=f'{feed.name}: Reuters reports evacuation.')) for feed in FEEDS
        ], NOW)
        self.assertEqual(state.top_stories[0].importance.factors['independent_reports'], 1)
        self.assertNotEqual(state.top_stories[0].importance.level, NewsImportanceLevel.MAJOR)

class SceneTests(unittest.IsolatedAsyncioTestCase):
    async def test_commodity_and_entertainment_never_interrupt_even_with_interest(self):
        settings = replace(SETTINGS, interests=(('economy', 2), ('entertainment', 2)))
        from olympus_core.models.news import NewsTopic
        for title, topic in [('Preisexplosion: Kupfer steigt an der Börse', NewsTopic.ECONOMY), ('WWE attack explosion shocks fans', NewsTopic.ENTERTAINMENT)]:
            collector = NewsCollector(settings, StubProvider([[], [result(f, article(f, title, topic=topic)) for f in FEEDS]]), lambda s: None, lambda e: None)
            await collector.poll_once(NOW)
            state = await collector.poll_once(NOW + timedelta(seconds=1))
            self.assertIsNone(state.presentation)
            self.assertEqual(ModeResolver().resolve([], None, news=state).mode.value, 'idle')
