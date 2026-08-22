import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timezone
import logging
import time
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx

from olympus_core.config import WeatherSettings
from olympus_core.models.weather import CurrentWeather, DailyWeather, WeatherLocation, WeatherState


logger = logging.getLogger(__name__)


def weather_condition(code: Any) -> str:
    if not isinstance(code, int) or isinstance(code, bool):
        return "unknown"
    if code == 0:
        return "clear"
    if code == 1:
        return "mostly_clear"
    if code == 2:
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57}:
        return "drizzle"
    if code in {61, 63, 66, 80, 81}:
        return "rain"
    if code in {65, 67, 82}:
        return "heavy_rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _percentage(value: Any) -> int | None:
    number = _number(value)
    return max(0, min(100, round(number))) if number is not None else None


def _daylight(value: Any) -> bool | None:
    return bool(value) if isinstance(value, int) and not isinstance(value, bool) and value in {0, 1} else None


def _at(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and len(values) > index else None


def _local_datetime(value: Any, timezone_name: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=ZoneInfo(timezone_name)) if parsed.tzinfo is None else parsed


def _daily(payload: Mapping[str, Any], index: int, timezone_name: str) -> DailyWeather | None:
    raw_date = _at(payload.get("time"), index)
    try:
        parsed_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) else None
    except ValueError:
        parsed_date = None
    if parsed_date is None:
        return None
    return DailyWeather(
        date=parsed_date,
        high_c=_number(_at(payload.get("temperature_2m_max"), index)),
        low_c=_number(_at(payload.get("temperature_2m_min"), index)),
        condition=weather_condition(_at(payload.get("weather_code"), index)),
        sunrise=_local_datetime(_at(payload.get("sunrise"), index), timezone_name),
        sunset=_local_datetime(_at(payload.get("sunset"), index), timezone_name),
        precipitation_probability_max=_percentage(_at(payload.get("precipitation_probability_max"), index)),
    )


def normalize_weather(payload: Any, settings: WeatherSettings, observed_at: datetime | None = None) -> WeatherState:
    value = _mapping(payload)
    current = _mapping(value.get("current"))
    daily = _mapping(value.get("daily"))
    if not current and not daily:
        raise ValueError("Weather response contained no current or daily data")
    latitude = settings.latitude if settings.latitude is not None else _number(value.get("latitude"))
    longitude = settings.longitude if settings.longitude is not None else _number(value.get("longitude"))
    if latitude is None or longitude is None:
        raise ValueError("Weather location is unavailable")
    return WeatherState(
        observed_at=observed_at or datetime.now(timezone.utc),
        location=WeatherLocation(
            latitude=latitude,
            longitude=longitude,
            timezone=settings.timezone,
            name=settings.location_name,
        ),
        current=CurrentWeather(
            temperature_c=_number(current.get("temperature_2m")),
            apparent_temperature_c=_number(current.get("apparent_temperature")),
            condition=weather_condition(current.get("weather_code")),
            precipitation_probability=_percentage(current.get("precipitation_probability")),
            wind_speed_kmh=_number(current.get("wind_speed_10m")),
            is_day=_daylight(current.get("is_day")),
        ) if current else None,
        today=_daily(daily, 0, settings.timezone),
        tomorrow=_daily(daily, 1, settings.timezone),
    )


class WeatherGateway(Protocol):
    async def fetch(self) -> WeatherState: ...
    async def aclose(self) -> None: ...


class OpenMeteoApi:
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, settings: WeatherSettings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(8.0))
        self._owns_client = client is None

    async def fetch(self) -> WeatherState:
        try:
            response = await self._client.get(self.URL, params={
                "latitude": self._settings.latitude,
                "longitude": self._settings.longitude,
                "timezone": self._settings.timezone,
                "forecast_days": 2,
                "current": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,wind_speed_10m,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max",
            })
            response.raise_for_status()
            return normalize_weather(response.json(), self._settings)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise RuntimeError("Weather provider is temporarily unavailable") from error

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class WeatherCollector:
    def __init__(self, settings: WeatherSettings, gateway: WeatherGateway, on_update: Callable[[WeatherState], Awaitable[None]]) -> None:
        self._settings = settings
        self._gateway = gateway
        self._on_update = on_update
        self._stop = asyncio.Event()
        self._last_good: WeatherState | None = None
        self._last_success_at: float | None = None
        self._published: WeatherState | None = None
        self._last_error_log_at = 0.0

    async def _publish(self, state: WeatherState) -> WeatherState:
        if state != self._published:
            self._published = state
            await self._on_update(state)
        return state

    async def poll_once(self, now: float | None = None) -> WeatherState:
        current_time = time.monotonic() if now is None else now
        try:
            state = await self._gateway.fetch()
        except Exception as error:
            if current_time - self._last_error_log_at >= 30:
                logger.warning("Weather temporarily unavailable: %s", error)
                self._last_error_log_at = current_time
            if self._last_good is None or self._last_success_at is None:
                raise
            age = current_time - self._last_success_at
            state = self._last_good.model_copy(update={
                "stale": age > self._settings.stale_seconds,
                "available": age <= self._settings.unavailable_seconds,
            })
            return await self._publish(state)
        self._last_good = state
        self._last_success_at = current_time
        return await self._publish(state)

    async def run(self) -> None:
        logger.info("Weather collector enabled")
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
