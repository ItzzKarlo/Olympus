import unittest

import httpx

from olympus_core.config import SpotifySettings
from olympus_core.integrations.spotify import SpotifyApi, SpotifyCollector
from olympus_core.models.media import MediaState, MediaTrack


SETTINGS = SpotifySettings(
    enabled=True,
    client_id="client",
    client_secret="secret",
    refresh_token="refresh",
    poll_seconds=5,
    stale_seconds=25,
)


def track(track_id: str, title: str) -> dict:
    return {
        "id": track_id,
        "name": title,
        "duration_ms": 215_000,
        "artists": [{"id": "artist-1", "name": "The Olympians"}],
        "album": {
            "id": "album-1",
            "name": "Mountains",
            "images": [{"url": "https://images.example/art.jpg"}],
        },
    }


class SpotifyApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalizes_current_track_context_and_limited_queue(self) -> None:
        context_requests = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal context_requests
            if request.url.host == "accounts.spotify.com":
                return httpx.Response(
                    200, json={"access_token": "token", "expires_in": 3600}
                )
            if request.url.path == "/v1/me/player":
                return httpx.Response(
                    200,
                    json={
                        "is_playing": True,
                        "progress_ms": 142_000,
                        "item": track("track-1", "Ambrosia"),
                        "context": {
                            "type": "playlist",
                            "uri": "spotify:playlist:playlist-1",
                        },
                    },
                )
            if request.url.path == "/v1/playlists/playlist-1":
                context_requests += 1
                return httpx.Response(200, json={"name": "Late Summer"})
            if request.url.path == "/v1/me/player/queue":
                return httpx.Response(
                    200,
                    json={
                        "queue": [track(str(index), f"Track {index}") for index in range(5)]
                    },
                )
            raise AssertionError(f"Unexpected request: {request.url}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        api = SpotifyApi(SETTINGS, client)
        first = await api.fetch_state()
        second = await api.fetch_state()
        await client.aclose()

        self.assertTrue(first.is_playing)
        self.assertEqual(first.progress_ms, 142_000)
        self.assertEqual(first.track.title, "Ambrosia")
        self.assertEqual(first.track.artists[0].name, "The Olympians")
        self.assertEqual(first.track.album.name, "Mountains")
        self.assertEqual(first.track.album.artwork_url, "https://images.example/art.jpg")
        self.assertEqual(first.context.name, "Late Summer")
        self.assertEqual(len(first.queue), 3)
        self.assertEqual(first.queue[0].title, "Track 0")
        self.assertEqual(context_requests, 1)
        self.assertEqual(second.context.name, "Late Summer")

    async def test_missing_playback_is_inactive(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "accounts.spotify.com":
                return httpx.Response(200, json={"access_token": "token"})
            return httpx.Response(204)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state = await SpotifyApi(SETTINGS, client).fetch_state()
        await client.aclose()

        self.assertFalse(state.is_playing)
        self.assertIsNone(state.track)

    async def test_paused_playback_keeps_track_and_progress(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "accounts.spotify.com":
                return httpx.Response(200, json={"access_token": "token"})
            if request.url.path == "/v1/me/player":
                return httpx.Response(
                    200,
                    json={
                        "is_playing": False,
                        "progress_ms": 33_000,
                        "item": track("track-1", "Paused"),
                        "context": None,
                    },
                )
            return httpx.Response(200, json={"queue": []})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state = await SpotifyApi(SETTINGS, client).fetch_state()
        await client.aclose()

        self.assertFalse(state.is_playing)
        self.assertEqual(state.progress_ms, 33_000)
        self.assertEqual(state.track.title, "Paused")


class FakeGateway:
    def __init__(self, outcomes: list[MediaState | Exception]) -> None:
        self.outcomes = outcomes

    async def fetch_state(self) -> MediaState:
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def aclose(self) -> None:
        return None


class SpotifyCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporary_failure_retains_recent_state_then_expires(self) -> None:
        playing = MediaState(
            is_playing=True,
            track=MediaTrack(title="Still playing", duration_ms=120_000),
        )
        updates: list[MediaState] = []

        async def update(state: MediaState) -> None:
            updates.append(state)

        collector = SpotifyCollector(
            SETTINGS,
            FakeGateway([playing, RuntimeError("offline"), RuntimeError("offline")]),
            update,
        )
        self.assertIs(await collector.poll_once(now=100), playing)
        self.assertIs(await collector.poll_once(now=110), playing)
        expired = await collector.poll_once(now=130)

        self.assertEqual(updates, [playing, expired])
        self.assertFalse(expired.available)
        self.assertFalse(expired.is_playing)


if __name__ == "__main__":
    unittest.main()
