from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
import httpx
from olympus_core.integrations.spotify import SpotifyApi, SpotifyCollector, SpotifyError
from olympus_core.config import SpotifySettings
from olympus_core.models.media import MediaState, MediaTrack
from olympus_core.services.media import MediaStateStore

SETTINGS = SpotifySettings(True, 'client', 'secret', 'refresh')

class CloudFailures(unittest.IsolatedAsyncioTestCase):
    async def test_statuses_are_distinct_redacted_and_redirects_never_followed(self):
        for status in (301, 401, 403, 429, 500):
            calls = []
            def handler(request):
                calls.append(request.url.host)
                if request.url.host == 'accounts.spotify.com':
                    return httpx.Response(200, json={'access_token': 'secret-token'})
                return httpx.Response(status, headers={'Location': 'https://secret.example/secret-token', 'Retry-After': '123'}, text='secret-token')
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
                api = SpotifyApi(SETTINGS, client)
                with self.assertRaises(SpotifyError) as caught:
                    await api.fetch_state()
                self.assertEqual(caught.exception.status_code, status)
                self.assertNotIn('secret', str(caught.exception))
                self.assertNotIn('secret.example', calls)
                if status == 429:
                    self.assertGreaterEqual(caught.exception.retry_after, 123)
                if status in (301, 401, 403, 429):
                    count = len(calls)
                    with self.assertRaises(SpotifyError):
                        await api.fetch_state()
                    self.assertEqual(len(calls), count)

    async def test_auth_redirect_is_not_json_error(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(301))) as client:
            with self.assertRaisesRegex(SpotifyError, 'authentication: unexpected redirect'):
                await SpotifyApi(SETTINGS, client).fetch_state()

    async def test_queue_failure_preserves_playback(self):
        def handler(request):
            if request.url.host == 'accounts.spotify.com':
                return httpx.Response(200, json={'access_token': 'token'})
            if request.url.path.endswith('/queue'):
                return httpx.Response(403)
            return httpx.Response(200, json={'is_playing': True, 'item': {'name': 'Track'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            state = await SpotifyApi(SETTINGS, client).fetch_state()
            self.assertTrue(state.is_playing)
            self.assertEqual(state.track.title, 'Track')

class Arbitration(unittest.TestCase):
    def test_local_sticky_stale_and_paused_does_not_hide_remote(self):
        now = datetime.now(timezone.utc)
        cloud = MediaState(is_playing=True, observed_at=now, track=MediaTrack(title='Phone'))
        local = MediaState(source='local', session_id='s', playback_status='playing', is_playing=True, observed_at=now, track=MediaTrack(title='Desktop'))
        a = SimpleNamespace(agent_id='a', hostname='Desktop', online=True, media_sessions=[local])
        b = SimpleNamespace(agent_id='b', hostname='Laptop', online=True, media_sessions=[local])
        store = MediaStateStore()
        store.update(cloud)
        self.assertEqual(store.get([b], now).agent_id, 'b')
        self.assertEqual(store.get([a,b], now).agent_id, 'b')
        self.assertIs(store.get([a,b], now + timedelta(seconds=16)), cloud)
        a.media_sessions = [local.model_copy(update={'is_playing': False, 'playback_status': 'paused'})]
        self.assertIs(store.get([a], now), cloud)
        a.media_sessions = [local]
        self.assertEqual(store.get([a], now).source, 'local')
