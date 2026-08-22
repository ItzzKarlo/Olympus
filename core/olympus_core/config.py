from dataclasses import dataclass
import os
from pathlib import Path
import logging
import tomllib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_float(value: str | None, default: float) -> float:
    try:
        parsed = float(value or default)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True, slots=True)
class SpotifySettings:
    enabled: bool
    client_id: str | None
    client_secret: str | None
    refresh_token: str | None
    poll_seconds: float = 5.0
    stale_seconds: float = 25.0

    @classmethod
    def from_environment(cls) -> "SpotifySettings":
        poll_seconds = _positive_float(
            os.getenv("OLYMPUS_SPOTIFY_POLL_SECONDS"), 5.0
        )
        return cls(
            enabled=_enabled(os.getenv("OLYMPUS_SPOTIFY_ENABLED")),
            client_id=os.getenv("OLYMPUS_SPOTIFY_CLIENT_ID") or None,
            client_secret=os.getenv("OLYMPUS_SPOTIFY_CLIENT_SECRET") or None,
            refresh_token=os.getenv("OLYMPUS_SPOTIFY_REFRESH_TOKEN") or None,
            poll_seconds=poll_seconds,
            stale_seconds=max(20.0, poll_seconds * 4),
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)


@dataclass(frozen=True, slots=True)
class WeatherSettings:
    enabled: bool = False
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "UTC"
    location_name: str | None = None
    poll_seconds: float = 600.0
    stale_seconds: float = 1_800.0
    unavailable_seconds: float = 21_600.0

    @property
    def configured(self) -> bool:
        return self.enabled and self.latitude is not None and self.longitude is not None


@dataclass(frozen=True, slots=True)
class CalendarSettings:
    enabled: bool = False
    provider: str = "google"
    timezone: str = "UTC"
    lookahead_days: int = 7
    poll_seconds: float = 300.0
    stale_seconds: float = 1_800.0
    unavailable_seconds: float = 21_600.0
    calendar_ids: tuple[str, ...] = ("primary",)
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None

    @property
    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    @property
    def configured(self) -> bool:
        return self.enabled and self.provider == "google" and self.has_credentials


@dataclass(frozen=True, slots=True)
class CoreSettings:
    timezone: str = "UTC"
    weather: WeatherSettings = WeatherSettings()
    calendar: CalendarSettings = CalendarSettings()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _timezone(value: Any, fallback: str = "UTC") -> str:
    candidate = value.strip() if isinstance(value, str) and value.strip() else fallback
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone %s; using %s", candidate, fallback)
        return fallback
    return candidate


def _coordinate(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if minimum <= parsed <= maximum else None


def _positive_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default


def parse_core_config(data: dict[str, Any]) -> CoreSettings:
    olympus = _mapping(data.get("olympus"))
    timezone = _timezone(olympus.get("timezone"))
    weather_data = _mapping(data.get("weather"))
    calendar_data = _mapping(data.get("calendar"))
    weather_timezone = _timezone(weather_data.get("timezone"), timezone)
    calendar_timezone = _timezone(calendar_data.get("timezone"), timezone)
    weather_poll = _positive_float(
        str(weather_data.get("poll_minutes")) if weather_data.get("poll_minutes") is not None else None,
        10.0,
    ) * 60
    calendar_poll = _positive_float(
        str(calendar_data.get("poll_minutes")) if calendar_data.get("poll_minutes") is not None else None,
        5.0,
    ) * 60
    raw_ids = calendar_data.get("calendar_ids", ["primary"])
    calendar_ids = tuple(
        value.strip() for value in raw_ids
        if isinstance(value, str) and value.strip()
    ) if isinstance(raw_ids, list) else ("primary",)

    return CoreSettings(
        timezone=timezone,
        weather=WeatherSettings(
            enabled=bool(weather_data.get("enabled", False)),
            latitude=_coordinate(weather_data.get("latitude"), -90, 90),
            longitude=_coordinate(weather_data.get("longitude"), -180, 180),
            timezone=weather_timezone,
            location_name=(
                weather_data["location_name"].strip()
                if isinstance(weather_data.get("location_name"), str)
                and weather_data["location_name"].strip()
                else None
            ),
            poll_seconds=weather_poll,
        ),
        calendar=CalendarSettings(
            enabled=bool(calendar_data.get("enabled", False)),
            provider=str(calendar_data.get("provider", "google")).lower(),
            timezone=calendar_timezone,
            lookahead_days=min(_positive_int(calendar_data.get("lookahead_days"), 7), 31),
            poll_seconds=calendar_poll,
            calendar_ids=calendar_ids or ("primary",),
            client_id=os.getenv("OLYMPUS_GOOGLE_CLIENT_ID") or None,
            client_secret=os.getenv("OLYMPUS_GOOGLE_CLIENT_SECRET") or None,
            refresh_token=os.getenv("OLYMPUS_GOOGLE_REFRESH_TOKEN") or None,
        ),
    )


def load_core_config(path: Path | None = None) -> CoreSettings:
    config_path = path or Path(os.getenv("OLYMPUS_CONFIG", "config.toml"))
    if not config_path.exists():
        return CoreSettings()
    try:
        with config_path.open("rb") as file:
            return parse_core_config(tomllib.load(file))
    except (OSError, tomllib.TOMLDecodeError) as error:
        logger.warning("Core configuration is invalid; using defaults: %s", error)
        return CoreSettings()
