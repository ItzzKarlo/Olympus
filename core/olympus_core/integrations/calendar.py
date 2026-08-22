import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, time, timezone
import logging
import time as monotonic_time
from typing import Any, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from olympus_core.config import CalendarSettings
from olympus_core.models.calendar import CalendarEvent, CalendarSnapshot


logger = logging.getLogger(__name__)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _datetime(value: Any, timezone_name: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=ZoneInfo(timezone_name)) if parsed.tzinfo is None else parsed


def _date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def normalize_google_event(value: Any, calendar_id: str, calendar_name: str, timezone_name: str) -> CalendarEvent | None:
    event = _mapping(value)
    if event.get("status") == "cancelled":
        return None
    event_id = _text(event.get("id"))
    start_data = _mapping(event.get("start"))
    end_data = _mapping(event.get("end"))
    if event_id is None:
        return None
    all_day = _text(start_data.get("date")) is not None
    start_date = _date(start_data.get("date")) if all_day else None
    end_date = _date(end_data.get("date")) if all_day else None
    start = _datetime(start_data.get("dateTime"), timezone_name) if not all_day else None
    end = _datetime(end_data.get("dateTime"), timezone_name) if not all_day else None
    if (all_day and start_date is None) or (not all_day and (start is None or end is None)):
        return None
    return CalendarEvent(
        id=f"{calendar_id}:{event_id}",
        title=_text(event.get("summary")) or "Busy",
        start=start,
        end=end,
        start_date=start_date,
        end_date=end_date,
        all_day=all_day,
        location=_text(event.get("location")),
        calendar_id=calendar_id,
        calendar_name=calendar_name,
    )


class CalendarGateway(Protocol):
    async def fetch(self) -> CalendarSnapshot: ...
    async def aclose(self) -> None: ...


class GoogleCalendarApi:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, settings: CalendarSettings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    async def _refresh_access_token(self) -> None:
        if not self._settings.has_credentials:
            raise RuntimeError("Google Calendar credentials are incomplete")
        try:
            response = await self._client.post(self.TOKEN_URL, data={
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
                "refresh_token": self._settings.refresh_token,
                "grant_type": "refresh_token",
            })
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("Google authentication is temporarily unavailable") from error
        token = _text(_mapping(payload).get("access_token"))
        if token is None:
            raise RuntimeError("Google authentication returned no access token")
        expires = _mapping(payload).get("expires_in")
        lifetime = int(expires) if isinstance(expires, (int, float)) else 3_600
        self._access_token = token
        self._token_expires_at = monotonic_time.monotonic() + max(30, lifetime - 30)
        logger.info("Google Calendar authentication refreshed")

    async def _get(self, url: str, params: dict[str, Any], retry_auth: bool = True) -> Mapping[str, Any]:
        if self._access_token is None or monotonic_time.monotonic() >= self._token_expires_at:
            await self._refresh_access_token()
        try:
            response = await self._client.get(url, params=params, headers={"Authorization": f"Bearer {self._access_token}"})
        except httpx.HTTPError as error:
            raise RuntimeError("Google Calendar is temporarily unavailable") from error
        if response.status_code == 401 and retry_auth:
            self._access_token = None
            await self._refresh_access_token()
            return await self._get(url, params, retry_auth=False)
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("Google Calendar returned an invalid response") from error
        if not isinstance(payload, Mapping):
            raise RuntimeError("Google Calendar returned an invalid response")
        return payload

    async def fetch(self) -> CalendarSnapshot:
        zone = ZoneInfo(self._settings.timezone)
        local_now = datetime.now(timezone.utc).astimezone(zone)
        window_start = datetime.combine(local_now.date(), time.min, zone)
        window_end = datetime.combine(
            date.fromordinal(local_now.date().toordinal() + self._settings.lookahead_days),
            time.min,
            zone,
        )
        events: list[CalendarEvent] = []
        for calendar_id in self._settings.calendar_ids:
            page_token: str | None = None
            while True:
                params: dict[str, Any] = {
                    "timeMin": window_start.isoformat(),
                    "timeMax": window_end.isoformat(),
                    "timeZone": self._settings.timezone,
                    "singleEvents": "true",
                    "showDeleted": "false",
                    "orderBy": "startTime",
                    "maxResults": 2500,
                    "fields": "nextPageToken,summary,items(id,summary,status,start,end,location,recurringEventId)",
                }
                if page_token is not None:
                    params["pageToken"] = page_token
                payload = await self._get(
                    f"{self.API_BASE}/calendars/{quote(calendar_id, safe='')}/events",
                    params,
                )
                calendar_name = _text(payload.get("summary")) or ("Primary" if calendar_id == "primary" else calendar_id)
                items = payload.get("items") if isinstance(payload.get("items"), list) else []
                for item in items:
                    normalized = normalize_google_event(item, calendar_id, calendar_name, self._settings.timezone)
                    if normalized is not None:
                        events.append(normalized)
                page_token = _text(payload.get("nextPageToken"))
                if page_token is None:
                    break

        def key(event: CalendarEvent) -> tuple[datetime, str]:
            if event.start is not None:
                return event.start.astimezone(timezone.utc), event.title.casefold()
            day = event.start_date or date.max
            return datetime.combine(day, time.min, timezone.utc), event.title.casefold()

        events.sort(key=key)
        return CalendarSnapshot(observed_at=datetime.now(timezone.utc), events=events)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class CalendarCollector:
    def __init__(self, settings: CalendarSettings, gateway: CalendarGateway, on_update: Callable[[CalendarSnapshot], Awaitable[None]]) -> None:
        self._settings = settings
        self._gateway = gateway
        self._on_update = on_update
        self._stop = asyncio.Event()
        self._last_good: CalendarSnapshot | None = None
        self._last_success_at: float | None = None
        self._published: CalendarSnapshot | None = None
        self._last_error_log_at = 0.0

    async def _publish(self, state: CalendarSnapshot) -> CalendarSnapshot:
        if state != self._published:
            self._published = state
            await self._on_update(state)
        return state

    async def poll_once(self, now: float | None = None) -> CalendarSnapshot:
        current_time = monotonic_time.monotonic() if now is None else now
        try:
            state = await self._gateway.fetch()
        except Exception as error:
            if current_time - self._last_error_log_at >= 30:
                logger.warning("Calendar temporarily unavailable: %s", error)
                self._last_error_log_at = current_time
            if self._last_good is None or self._last_success_at is None:
                raise
            age = current_time - self._last_success_at
            return await self._publish(self._last_good.model_copy(update={
                "stale": age > self._settings.stale_seconds,
                "available": age <= self._settings.unavailable_seconds,
            }))
        self._last_good = state
        self._last_success_at = current_time
        return await self._publish(state)

    async def run(self) -> None:
        logger.info("Google Calendar collector enabled")
        try:
            while not self._stop.is_set():
                try:
                    await self.poll_once()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(self._stop.wait(), self._settings.poll_seconds)
                except TimeoutError:
                    pass
        finally:
            await self._gateway.aclose()

    def stop(self) -> None:
        self._stop.set()
