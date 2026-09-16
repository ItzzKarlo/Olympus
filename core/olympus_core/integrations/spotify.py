import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
import logging
import math
from email.utils import parsedate_to_datetime
import time
from typing import Any, Protocol

import httpx

from olympus_core.config import SpotifySettings
from olympus_core.models.media import (
    MediaAlbum,
    MediaArtist,
    MediaContext,
    MediaQueueTrack,
    MediaState,
    MediaTrack,
)


logger = logging.getLogger(__name__)
JsonObject = Mapping[str, Any]


class SpotifyError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def _object(value: Any) -> JsonObject:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _integer(value: Any) -> int:
    return max(0, value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _artwork_url(album: JsonObject) -> str | None:
    images = [_object(image) for image in _list(album.get("images"))]
    return next((_text(image.get("url")) for image in images if image), None)


def normalize_track(value: Any) -> MediaTrack | None:
    track = _object(value)
    title = _text(track.get("name"))
    if title is None:
        return None

    artists = [
        MediaArtist(id=_text(artist.get("id")), name=name)
        for artist in (_object(item) for item in _list(track.get("artists")))
        if (name := _text(artist.get("name"))) is not None
    ]
    album_data = _object(track.get("album"))
    album_name = _text(album_data.get("name"))
    album = (
        MediaAlbum(
            id=_text(album_data.get("id")),
            name=album_name,
            artwork_url=_artwork_url(album_data),
        )
        if album_name is not None
        else None
    )
    return MediaTrack(
        id=_text(track.get("id")) or _text(track.get("uri")),
        title=title,
        artists=artists,
        duration_ms=_integer(track.get("duration_ms")),
        album=album,
    )


def normalize_queue_track(value: Any) -> MediaQueueTrack | None:
    track = _object(value)
    normalized = normalize_track(track)
    if normalized is None:
        return None
    return MediaQueueTrack(
        id=normalized.id,
        title=normalized.title,
        artists=[artist.name for artist in normalized.artists],
        duration_ms=normalized.duration_ms,
        artwork_url=normalized.album.artwork_url if normalized.album else None,
    )


def _fallback_track_identity(
    title: str,
    artists: list[str],
    duration_ms: int,
) -> tuple[str, str, tuple[str, ...], int]:
    return (
        "metadata",
        title.strip().casefold(),
        tuple(artist.strip().casefold() for artist in artists),
        duration_ms,
    )


def _current_track_identity(track: MediaTrack) -> tuple[object, ...]:
    if track.id:
        return ("spotify", track.id)
    return _fallback_track_identity(
        track.title,
        [artist.name for artist in track.artists],
        track.duration_ms,
    )


def _queue_track_identity(track: MediaQueueTrack) -> tuple[object, ...]:
    if track.id:
        return ("spotify", track.id)
    return _fallback_track_identity(
        track.title,
        track.artists,
        track.duration_ms,
    )


class SpotifyGateway(Protocol):
    async def fetch_state(self) -> MediaState: ...

    async def aclose(self) -> None: ...


class SpotifyApi:
    API_BASE = "https://api.spotify.com/v1"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(
        self,
        settings: SpotifySettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(8.0))
        self._owns_client = client is None
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._context_cache: dict[str, str] = {}
        self._blocked_until = 0.0

    def _check_response(self, response: httpx.Response, endpoint: str) -> None:
        status = response.status_code
        if status < 300:
            return
        retry = None
        if status == 429:
            raw = response.headers.get("Retry-After", "60")
            try:
                retry = float(raw)
            except ValueError:
                try:
                    retry = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    retry = 60.0
            retry = max(1.0, retry) if math.isfinite(retry) else 60.0
        elif status in {400, 401, 403} or 300 <= status < 400:
            retry = 300.0
        if retry is not None:
            self._blocked_until = time.monotonic() + retry
        outcome = "unexpected redirect" if status < 400 else {
            400: "credentials rejected", 401: "unauthorized", 403: "forbidden", 429: "rate limited",
        }.get(status, "upstream error" if status >= 500 else "request rejected")
        # Never include response bodies, URLs, Location, or authentication headers.
        raise SpotifyError(f"Spotify {endpoint}: {outcome}", status, retry)


    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _refresh_access_token(self) -> None:
        if not self._settings.has_credentials:
            raise SpotifyError("Spotify credentials are incomplete")
        try:
            response = await self._client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._settings.refresh_token,
                },
                auth=(self._settings.client_id, self._settings.client_secret),
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise SpotifyError("Spotify authentication is unavailable") from exc
        self._check_response(response, "authentication")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SpotifyError("Spotify authentication returned invalid JSON") from exc
        token = _text(_object(payload).get("access_token"))
        if token is None:
            raise SpotifyError("Spotify authentication response had no access token")
        expires_in = _integer(_object(payload).get("expires_in")) or 3600
        self._access_token = token
        self._access_token_expires_at = time.monotonic() + max(30, expires_in - 30)
        logger.info("Spotify authentication refreshed")

    async def _request(
        self,
        path: str,
        *,
        allow_empty: bool = False,
        retry_auth: bool = True,
    ) -> JsonObject | None:
        if time.monotonic() < self._blocked_until:
            raise SpotifyError("Spotify retry deferred", retry_after=self._blocked_until - time.monotonic())
        if (
            self._access_token is None
            or time.monotonic() >= self._access_token_expires_at
        ):
            await self._refresh_access_token()

        try:
            response = await self._client.get(
                f"{self.API_BASE}{path}",
                headers={"Authorization": f"Bearer {self._access_token}"},
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise SpotifyError("Spotify API is temporarily unavailable") from exc

        if response.status_code == 401 and retry_auth:
            self._access_token = None
            await self._refresh_access_token()
            return await self._request(
                path, allow_empty=allow_empty, retry_auth=False
            )
        if response.status_code == 204 and allow_empty:
            return None
        self._check_response(response, "playback")
        try:
            value = response.json()
        except ValueError as exc:
            raise SpotifyError("Spotify API returned invalid JSON") from exc
        if not isinstance(value, Mapping):
            raise SpotifyError("Spotify API returned an invalid response")
        return value

    async def _resolve_context(self, value: Any) -> MediaContext | None:
        context = _object(value)
        context_type = _text(context.get("type"))
        uri = _text(context.get("uri"))
        if context_type is None:
            return None

        name = self._context_cache.get(uri or "")
        parts = (uri or "").split(":")
        context_id = parts[-1] if len(parts) >= 3 else None
        supported = {"playlist", "album", "artist", "show"}
        if name is None and context_id and context_type in supported:
            try:
                metadata = await self._request(f"/{context_type}s/{context_id}")
                name = _text(_object(metadata).get("name"))
            except SpotifyError:
                # Context names are enriching metadata; playback itself should survive.
                name = None
            if name is not None and uri is not None:
                if len(self._context_cache) >= 128:
                    self._context_cache.pop(next(iter(self._context_cache)))
                self._context_cache[uri] = name

        return MediaContext(type=context_type, name=name, uri=uri)

    async def fetch_state(self) -> MediaState:
        playback = await self._request("/me/player", allow_empty=True)
        observed_at = datetime.now(timezone.utc)
        if playback is None:
            return MediaState(observed_at=observed_at)

        track = normalize_track(playback.get("item"))
        context = await self._resolve_context(playback.get("context"))
        queue: list[MediaQueueTrack] = []
        if track is not None:
            try:
                queue_payload = await self._request("/me/player/queue")
            except SpotifyError:
                queue_payload = None
            seen = {_current_track_identity(track)}
            for item in _list(_object(queue_payload).get("queue")):
                normalized = normalize_queue_track(item)
                if normalized is None:
                    continue
                identity = _queue_track_identity(normalized)
                if identity in seen:
                    continue
                seen.add(identity)
                queue.append(normalized)
                if len(queue) == 3:
                    break

        return MediaState(
            is_playing=bool(playback.get("is_playing")),
            playback_status="playing" if playback.get("is_playing") else "paused" if track else "stopped",
            device=_text(_object(playback.get("device")).get("name")),
            observed_at=observed_at,
            progress_ms=_integer(playback.get("progress_ms")),
            track=track,
            context=context,
            queue=queue,
        )


class SpotifyCollector:
    def __init__(
        self,
        settings: SpotifySettings,
        gateway: SpotifyGateway,
        on_update: Callable[[MediaState], Awaitable[None]],
        local_playing: Callable[[], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._local_playing = local_playing or (lambda: False)
        self._gateway = gateway
        self._on_update = on_update
        self._stop = asyncio.Event()
        self._last_good_state: MediaState | None = None
        self._last_success_at: float | None = None
        self._was_playing = False
        self._last_error_log_at = 0.0
        self._consecutive_failures = 0
        self._retry_after = 0.0
        self.health = "unknown"

    async def poll_once(self, now: float | None = None) -> MediaState:
        current_time = time.monotonic() if now is None else now
        try:
            state = await self._gateway.fetch_state()
        except Exception as exc:
            self._consecutive_failures += 1
            self._retry_after = exc.retry_after or 0.0 if isinstance(exc, SpotifyError) else 0.0
            self.health = f"http_{exc.status_code}" if isinstance(exc, SpotifyError) and exc.status_code else "unavailable"
            if current_time - self._last_error_log_at >= 30:
                logger.warning("Spotify unavailable (%s)", self.health)
                self._last_error_log_at = current_time
            if (
                self._last_good_state is not None
                and self._last_success_at is not None
                and current_time - self._last_success_at
                <= self._settings.stale_seconds
            ):
                return self._last_good_state
            unavailable = MediaState.unavailable()
            await self._on_update(unavailable)
            return unavailable

        self.health = "playing" if state.is_playing else "inactive"
        self._retry_after = 0.0
        self._last_good_state = state
        self._last_success_at = current_time
        self._consecutive_failures = 0
        if state.is_playing != self._was_playing:
            logger.info(
                "Spotify playback became %s",
                "active" if state.is_playing else "inactive",
            )
            self._was_playing = state.is_playing
        await self._on_update(state)
        return state

    def poll_interval(self, state: MediaState) -> float:
        if self._consecutive_failures:
            return max(
                self._settings.poll_seconds,
                self._retry_after,
                min(
                    300.0,
                    self._settings.poll_seconds * (2 ** min(8, self._consecutive_failures - 1)),
                ),
            )
        if self._local_playing():
            return self._settings.local_poll_seconds
        return (
            self._settings.active_poll_seconds
            if state.available and state.is_playing
            else self._settings.poll_seconds
        )

    async def run(self) -> None:
        logger.info("Spotify collector enabled")
        try:
            while not self._stop.is_set():
                state = await self.poll_once()
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_interval(state)
                    )
                except TimeoutError:
                    pass
        finally:
            await self._gateway.aclose()

    def stop(self) -> None:
        self._stop.set()
