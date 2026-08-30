import asyncio
from dataclasses import replace
import unittest
from unittest.mock import patch

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
    active_poll_seconds=1.5,
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

    async def test_queue_excludes_current_and_deduplicates_stable_ids_in_order(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "accounts.spotify.com":
                return httpx.Response(200, json={"access_token": "token"})
            if request.url.path == "/v1/me/player":
                return httpx.Response(200, json={
                    "is_playing": True,
                    "item": track("current", "Repeat"),
                    "context": None,
                })
            if request.url.path == "/v1/me/player/queue":
                return httpx.Response(200, json={"queue": [
                    track("current", "Repeat"),
                    track("next-1", "Same title"),
                    track("next-1", "Same title"),
                    track("next-2", "Same title"),
                    track("next-3", "Finale"),
                ]})
            raise AssertionError(f"Unexpected request: {request.url}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state = await SpotifyApi(SETTINGS, client).fetch_state()
        await client.aclose()

        self.assertEqual([item.id for item in state.queue], ["next-1", "next-2", "next-3"])
        self.assertEqual([item.title for item in state.queue[:2]], ["Same title", "Same title"])

    async def test_queue_missing_id_fallback_uses_full_track_metadata(self) -> None:
        current = track("placeholder", "Repeat")
        current.pop("id")
        current["uri"] = "spotify:track:repeat-uri"
        repeated = dict(current)
        different_recording = track("placeholder", "Repeat")
        different_recording.pop("id")
        different_recording["artists"] = [{"name": "Different artist"}]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "accounts.spotify.com":
                return httpx.Response(200, json={"access_token": "token"})
            if request.url.path == "/v1/me/player":
                return httpx.Response(200, json={
                    "is_playing": True,
                    "item": current,
                    "context": None,
                })
            if request.url.path == "/v1/me/player/queue":
                return httpx.Response(200, json={"queue": [
                    repeated,
                    repeated,
                    different_recording,
                    track("unique", "After repeat"),
                ]})
            raise AssertionError(f"Unexpected request: {request.url}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state = await SpotifyApi(SETTINGS, client).fetch_state()
        await client.aclose()

        self.assertEqual(
            [(item.id, item.title, item.artists) for item in state.queue],
            [
                (None, "Repeat", ["Different artist"]),
                ("unique", "After repeat", ["The Olympians"]),
            ],
        )


class SpotifySettingsTests(unittest.TestCase):
    def test_active_poll_default_targets_near_real_time_without_changing_inactive_poll(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = SpotifySettings.from_environment()
        self.assertEqual(settings.active_poll_seconds, 1.5)
        self.assertEqual(settings.poll_seconds, 5.0)


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
        self.assertEqual(collector.poll_interval(playing), 1.5)
        retained = await collector.poll_once(now=110)
        self.assertIs(retained, playing)
        self.assertEqual(collector.poll_interval(retained), 5)
        expired = await collector.poll_once(now=130)

        self.assertEqual(updates, [playing, expired])
        self.assertFalse(expired.available)
        self.assertFalse(expired.is_playing)
        self.assertEqual(collector.poll_interval(expired), 10)

    async def test_run_never_overlaps_gateway_polls(self) -> None:
        class TrackingGateway:
            def __init__(self) -> None:
                self.active = 0
                self.max_active = 0

            async def fetch_state(self) -> MediaState:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return MediaState(
                    is_playing=True,
                    track=MediaTrack(title="Live", duration_ms=120_000),
                )

            async def aclose(self) -> None:
                return None

        gateway = TrackingGateway()
        updates = 0
        collector: SpotifyCollector

        async def update(_state: MediaState) -> None:
            nonlocal updates
            updates += 1
            if updates == 3:
                collector.stop()

        collector = SpotifyCollector(
            replace(SETTINGS, poll_seconds=0.01, active_poll_seconds=0.01),
            gateway,
            update,
        )
        await asyncio.wait_for(collector.run(), timeout=1)

        self.assertEqual(updates, 3)
        self.assertEqual(gateway.max_active, 1)


if __name__ == "__main__":
    unittest.main()
