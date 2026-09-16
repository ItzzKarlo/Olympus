from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from dataclasses import replace
import unittest
import httpx
from olympus_core.integrations.news.rss import RssNewsProvider
from olympus_core.config import NewsSettings, NewsFeedSettings, SpotifySettings
from olympus_core.integrations.spotify import SpotifyApi, SpotifyError, SpotifyCollector
from olympus_core.services.football import FootballStateStore
from olympus_core.integrations.football.collector import MatchdayPolicy
from test_football import SETTINGS, snapshot

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_feed_rate_limit_defers_requests_then_recovers(self):
        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        class Clock:
            @staticmethod
            def now(tz): return now
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={'Retry-After': '900'})
            return httpx.Response(200, content=b'<rss><channel><title>Empty but valid feed</title></channel></rss>')
        settings = NewsSettings(feeds=(NewsFeedSettings('feed', 'Feed', 'https://example.test/feed'),))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = RssNewsProvider(settings, client)
            with patch('olympus_core.integrations.news.rss.datetime', Clock):
                failed = (await provider.fetch())[0]
                self.assertEqual(failed.error, 'http_429')
                self.assertEqual((failed.retry_at - now).total_seconds(), 900)
                now += timedelta(seconds=300)
                self.assertEqual((await provider.fetch())[0].error, 'retry_deferred')
                self.assertEqual(len(calls), 1)
                now += timedelta(seconds=600)
                recovered = (await provider.fetch())[0]
                self.assertTrue(recovered.successful)
                self.assertEqual(recovered.articles, [])

    async def test_spotify_timeout_and_invalid_json_are_distinct(self):
        settings = SpotifySettings(True, 'client', 'secret', 'refresh')
        for failure in ('timeout', 'invalid_json'):
            def handler(request):
                if failure == 'timeout': raise httpx.ReadTimeout('sensitive URL', request=request)
                return httpx.Response(200, text='not json')
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(SpotifyError) as caught:
                    await SpotifyApi(settings, client).fetch_state()
                self.assertEqual(caught.exception.kind, failure)
                self.assertNotIn('sensitive', str(caught.exception))

    def test_football_expires_without_another_network_poll(self):
        now = datetime(2026, 8, 29, 18, tzinfo=timezone.utc)
        store = FootballStateStore(60, 900)
        store.update(MatchdayPolicy(SETTINGS).state(snapshot('2H', now), now))
        self.assertTrue(store.get(now + timedelta(seconds=61)).matchday.stale)
        self.assertIsNone(store.get(now + timedelta(seconds=901)).matchday)
