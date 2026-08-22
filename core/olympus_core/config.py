from dataclasses import dataclass
from datetime import time
import os
from pathlib import Path
import logging
import tomllib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)
DEFAULT_TIMEZONE = "Europe/Berlin"


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
    timezone: str = DEFAULT_TIMEZONE
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
    timezone: str = DEFAULT_TIMEZONE
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
class NightSettings:
    enabled: bool = True
    weekday_start: time = time(22, 0)
    weekend_start: time = time(0, 0)
    end: time = time(7, 30)
    weekend_days: tuple[int, ...] = (4, 5)


@dataclass(frozen=True, slots=True)
class FootballMatchdaySettings:
    pre_match_minutes: int = 60
    post_match_minutes: int = 20


@dataclass(frozen=True, slots=True)
class FootballSettings:
    enabled: bool = False
    provider: str = "api-football"
    team_id: str = "157"
    tracked_id: str = "bayern"
    team_name: str = "FC Bayern München"
    team_short_name: str = "Bayern"
    team_code: str = "FCB"
    timezone: str = DEFAULT_TIMEZONE
    api_key: str | None = None
    fixture_path: str | None = None
    matchday: FootballMatchdaySettings = FootballMatchdaySettings()
    poll_upcoming_seconds: float = 1_800.0
    poll_near_match_seconds: float = 300.0
    poll_pre_match_seconds: float = 60.0
    poll_live_seconds: float = 15.0
    poll_half_time_seconds: float = 30.0
    poll_post_match_seconds: float = 60.0
    live_stale_seconds: float = 60.0
    unavailable_seconds: float = 900.0

    @property
    def configured(self) -> bool:
        if not self.enabled or not self.team_id:
            return False
        return (
            self.provider == "api-football" and bool(self.api_key)
        ) or (
            self.provider == "fixture" and bool(self.fixture_path)
        )


@dataclass(frozen=True, slots=True)
class CoreSettings:
    timezone: str = DEFAULT_TIMEZONE
    weather: WeatherSettings = WeatherSettings()
    calendar: CalendarSettings = CalendarSettings()
    night: NightSettings = NightSettings()
    football: FootballSettings = FootballSettings()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _timezone(value: Any, fallback: str = DEFAULT_TIMEZONE) -> str:
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


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _clock_time(value: Any, setting: str, default: time) -> time:
    if value is None:
        return default
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError(f"{setting} must use HH:MM")
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return time(hour, minute)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{setting} must be a valid 24-hour HH:MM time") from error


def _weekend_days(value: Any) -> tuple[int, ...]:
    if value is None:
        return (4, 5)
    if not isinstance(value, list):
        raise ValueError("night.weekend_days must be a list of weekday names")
    days: list[int] = []
    for item in value:
        key = item.strip().lower() if isinstance(item, str) else ""
        if key not in WEEKDAYS:
            raise ValueError(f"Invalid night weekend day: {item!r}")
        if WEEKDAYS[key] not in days:
            days.append(WEEKDAYS[key])
    return tuple(days)


def parse_core_config(data: dict[str, Any]) -> CoreSettings:
    olympus = _mapping(data.get("olympus"))
    timezone = _timezone(olympus.get("timezone"))
    weather_data = _mapping(data.get("weather"))
    calendar_data = _mapping(data.get("calendar"))
    night_data = _mapping(data.get("night"))
    football_data = _mapping(data.get("football"))
    matchday_data = _mapping(football_data.get("matchday"))
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
        night=NightSettings(
            enabled=bool(night_data.get("enabled", True)),
            weekday_start=_clock_time(night_data.get("weekday_start"), "night.weekday_start", time(22, 0)),
            weekend_start=_clock_time(night_data.get("weekend_start"), "night.weekend_start", time(0, 0)),
            end=_clock_time(night_data.get("end"), "night.end", time(7, 30)),
            weekend_days=_weekend_days(night_data.get("weekend_days")),
        ),
        football=FootballSettings(
            enabled=bool(football_data.get("enabled", False)),
            provider=str(football_data.get("provider", "api-football")).strip().lower(),
            team_id=str(football_data.get("team_id", "157")).strip(),
            tracked_id=str(football_data.get("tracked_id", "bayern")).strip() or "bayern",
            team_name=str(football_data.get("team_name", "FC Bayern München")).strip() or "FC Bayern München",
            team_short_name=str(football_data.get("team_short_name", "Bayern")).strip() or "Bayern",
            team_code=str(football_data.get("team_code", "FCB")).strip() or "FCB",
            timezone=_timezone(football_data.get("timezone"), timezone),
            api_key=os.getenv("OLYMPUS_FOOTBALL_API_KEY") or None,
            fixture_path=os.getenv("OLYMPUS_FOOTBALL_FIXTURE_PATH") or None,
            matchday=FootballMatchdaySettings(
                pre_match_minutes=_positive_int(matchday_data.get("pre_match_minutes"), 60),
                post_match_minutes=_positive_int(matchday_data.get("post_match_minutes"), 20),
            ),
            poll_upcoming_seconds=_positive_float(
                str(football_data.get("poll_upcoming_minutes")) if football_data.get("poll_upcoming_minutes") is not None else None,
                30.0,
            ) * 60,
            poll_near_match_seconds=_positive_float(
                str(football_data.get("poll_near_match_minutes")) if football_data.get("poll_near_match_minutes") is not None else None,
                5.0,
            ) * 60,
            poll_pre_match_seconds=_positive_float(
                str(football_data.get("poll_pre_match_seconds")) if football_data.get("poll_pre_match_seconds") is not None else None,
                60.0,
            ),
            poll_live_seconds=_positive_float(
                str(football_data.get("poll_live_seconds")) if football_data.get("poll_live_seconds") is not None else None,
                15.0,
            ),
            poll_half_time_seconds=_positive_float(
                str(football_data.get("poll_half_time_seconds")) if football_data.get("poll_half_time_seconds") is not None else None,
                30.0,
            ),
            poll_post_match_seconds=_positive_float(
                str(football_data.get("poll_post_match_seconds")) if football_data.get("poll_post_match_seconds") is not None else None,
                60.0,
            ),
            live_stale_seconds=_positive_float(
                str(football_data.get("live_stale_seconds")) if football_data.get("live_stale_seconds") is not None else None,
                60.0,
            ),
            unavailable_seconds=_positive_float(
                str(football_data.get("unavailable_seconds")) if football_data.get("unavailable_seconds") is not None else None,
                900.0,
            ),
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
