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
class FootballPlayerSettings:
    watched: tuple[str, ...] = ()
    rating_change_threshold: float = 0.25


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
    players: FootballPlayerSettings = FootballPlayerSettings()
    poll_upcoming_seconds: float = 1_800.0
    poll_near_match_seconds: float = 300.0
    poll_pre_match_seconds: float = 60.0
    poll_live_seconds: float = 15.0
    poll_half_time_seconds: float = 30.0
    poll_post_match_seconds: float = 60.0
    poll_team_stats_seconds: float = 60.0
    poll_player_stats_seconds: float = 60.0
    live_stale_seconds: float = 60.0
    unavailable_seconds: float = 900.0
    low_quota_remaining: int = 25
    critical_quota_remaining: int = 5
    max_history_samples: int = 96

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
class NewsFeedSettings:
    id: str
    name: str
    url: str
    language: str = "en"
    trust: float = 1.0
    region: str | None = None
    topic: str | None = None


@dataclass(frozen=True, slots=True)
class NewsPresentationSettings:
    ambient_limit: int = 3
    news_scene_seconds: float = 20.0
    major_scene_seconds: float = 45.0
    cooldown_seconds: float = 1_800.0
    notable_threshold: float = 0.55
    important_threshold: float = 0.68
    major_threshold: float = 0.86


@dataclass(frozen=True, slots=True)
class NewsSettings:
    enabled: bool = False
    provider: str = "rss"
    fixture_path: str | None = None
    poll_seconds: float = 300.0
    retention_seconds: float = 172_800.0
    stale_seconds: float = 900.0
    unavailable_seconds: float = 3_600.0
    default_language: str = "en"
    local_regions: tuple[str, ...] = ("DE",)
    feeds: tuple[NewsFeedSettings, ...] = ()
    interests: tuple[tuple[str, float], ...] = ()
    presentation: NewsPresentationSettings = NewsPresentationSettings()

    @property
    def configured(self) -> bool:
        if not self.enabled:
            return False
        if self.provider == "fixture":
            return bool(self.fixture_path)
        return self.provider == "rss" and bool(self.feeds)

    def interest_weight(self, topic: str) -> float:
        return dict(self.interests).get(topic, 1.0)


@dataclass(frozen=True, slots=True)
class PersistenceSettings:
    database_path: Path = Path("~/.local/share/olympus/core.db")
    incident_retention_days: int = 30
    news_memory_retention_days: int = 7

    @property
    def resolved_database_path(self) -> Path:
        return self.database_path.expanduser()


@dataclass(frozen=True, slots=True)
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 8_000


@dataclass(frozen=True, slots=True)
class DisplaySettings:
    directory: Path | None = None

    @property
    def resolved_directory(self) -> Path | None:
        return self.directory.expanduser().resolve() if self.directory is not None else None


@dataclass(frozen=True, slots=True)
class BackupSettings:
    directory: Path = Path("~/.local/share/olympus/backups")
    retention_days: int = 14

    @property
    def resolved_directory(self) -> Path:
        return self.directory.expanduser()


@dataclass(frozen=True, slots=True)
class SecuritySettings:
    require_agent_auth: bool = True
    enrollment_token_ttl_minutes: int = 10
    auth_timeout_seconds: float = 10.0
    revocation_refresh_seconds: float = 30.0
    last_seen_write_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class CoreSettings:
    timezone: str = DEFAULT_TIMEZONE
    server: ServerSettings = ServerSettings()
    display: DisplaySettings = DisplaySettings()
    backup: BackupSettings = BackupSettings()
    weather: WeatherSettings = WeatherSettings()
    calendar: CalendarSettings = CalendarSettings()
    night: NightSettings = NightSettings()
    football: FootballSettings = FootballSettings()
    news: NewsSettings = NewsSettings()
    persistence: PersistenceSettings = PersistenceSettings()
    security: SecuritySettings = SecuritySettings()


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


def _nonnegative_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return min(maximum, max(minimum, float(value)))


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
    server_data = _mapping(data.get("server"))
    display_data = _mapping(data.get("display"))
    backup_data = _mapping(data.get("backup"))
    timezone = _timezone(olympus.get("timezone"))
    weather_data = _mapping(data.get("weather"))
    calendar_data = _mapping(data.get("calendar"))
    night_data = _mapping(data.get("night"))
    football_data = _mapping(data.get("football"))
    matchday_data = _mapping(football_data.get("matchday"))
    player_data = _mapping(football_data.get("players"))
    news_data = _mapping(data.get("news"))
    news_presentation_data = _mapping(news_data.get("presentation"))
    news_interests_data = _mapping(news_data.get("interests"))
    persistence_data = _mapping(data.get("persistence"))
    security_data = _mapping(data.get("security"))
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
    raw_watched = player_data.get("watched", [])
    watched_players = tuple(dict.fromkeys(
        value.strip() for value in raw_watched
        if isinstance(value, str) and value.strip()
    )) if isinstance(raw_watched, list) else ()
    raw_news_feeds = news_data.get("feeds", [])
    news_feeds: list[NewsFeedSettings] = []
    if isinstance(raw_news_feeds, list):
        for value in raw_news_feeds:
            feed = _mapping(value)
            identifier = str(feed.get("id", "")).strip()
            name = str(feed.get("name", "")).strip()
            url = str(feed.get("url", "")).strip()
            if not identifier or not name or not url:
                continue
            topic = str(feed.get("topic", "")).strip().lower() or None
            news_feeds.append(NewsFeedSettings(
                id=identifier,
                name=name,
                url=url,
                language=str(feed.get("language", news_data.get("default_language", "en"))).strip() or "en",
                trust=_bounded_float(feed.get("trust"), 1.0, 0.1, 2.0),
                region=str(feed.get("region", "")).strip().upper() or None,
                topic=topic,
            ))
    raw_regions = news_data.get("local_regions", ["DE"])
    local_regions = tuple(dict.fromkeys(
        str(value).strip().upper() for value in raw_regions if str(value).strip()
    )) if isinstance(raw_regions, list) else ("DE",)
    interests = tuple(
        (str(topic).strip().lower(), _bounded_float(weight, 1.0, 0.25, 2.0))
        for topic, weight in news_interests_data.items()
        if str(topic).strip()
    )

    return CoreSettings(
        timezone=timezone,
        server=ServerSettings(
            host=str(server_data.get("host", "127.0.0.1")).strip() or "127.0.0.1",
            port=min(_positive_int(server_data.get("port"), 8_000), 65_535),
        ),
        display=DisplaySettings(directory=(
            Path(str(display_data["directory"]))
            if display_data.get("directory")
            else None
        )),
        backup=BackupSettings(
            directory=Path(str(
                backup_data.get("directory", "~/.local/share/olympus/backups")
            )),
            retention_days=min(_positive_int(backup_data.get("retention_days"), 14), 365),
        ),
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
            players=FootballPlayerSettings(
                watched=watched_players,
                rating_change_threshold=_positive_float(
                    str(player_data.get("rating_change_threshold")) if player_data.get("rating_change_threshold") is not None else None,
                    0.25,
                ),
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
            poll_team_stats_seconds=_positive_float(
                str(football_data.get("poll_team_stats_seconds")) if football_data.get("poll_team_stats_seconds") is not None else None,
                60.0,
            ),
            poll_player_stats_seconds=_positive_float(
                str(football_data.get("poll_player_stats_seconds")) if football_data.get("poll_player_stats_seconds") is not None else None,
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
            low_quota_remaining=_nonnegative_int(football_data.get("low_quota_remaining"), 25),
            critical_quota_remaining=_nonnegative_int(football_data.get("critical_quota_remaining"), 5),
            max_history_samples=min(_positive_int(football_data.get("max_history_samples"), 96), 512),
        ),
        news=NewsSettings(
            enabled=bool(news_data.get("enabled", False)),
            provider=str(news_data.get("provider", "rss")).strip().lower(),
            fixture_path=os.getenv("OLYMPUS_NEWS_FIXTURE_PATH") or None,
            poll_seconds=_positive_float(
                str(news_data.get("poll_minutes")) if news_data.get("poll_minutes") is not None else None,
                5.0,
            ) * 60,
            retention_seconds=_positive_float(
                str(news_data.get("retention_hours")) if news_data.get("retention_hours") is not None else None,
                48.0,
            ) * 3_600,
            stale_seconds=_positive_float(
                str(news_data.get("stale_minutes")) if news_data.get("stale_minutes") is not None else None,
                15.0,
            ) * 60,
            unavailable_seconds=_positive_float(
                str(news_data.get("unavailable_minutes")) if news_data.get("unavailable_minutes") is not None else None,
                60.0,
            ) * 60,
            default_language=str(news_data.get("default_language", "en")).strip() or "en",
            local_regions=local_regions or ("DE",),
            feeds=tuple(news_feeds),
            interests=interests,
            presentation=NewsPresentationSettings(
                ambient_limit=min(_positive_int(news_presentation_data.get("ambient_limit"), 3), 5),
                news_scene_seconds=_positive_float(
                    str(news_presentation_data.get("news_scene_seconds")) if news_presentation_data.get("news_scene_seconds") is not None else None,
                    20.0,
                ),
                major_scene_seconds=_positive_float(
                    str(news_presentation_data.get("major_scene_seconds")) if news_presentation_data.get("major_scene_seconds") is not None else None,
                    45.0,
                ),
                cooldown_seconds=_positive_float(
                    str(news_presentation_data.get("cooldown_minutes")) if news_presentation_data.get("cooldown_minutes") is not None else None,
                    30.0,
                ) * 60,
                notable_threshold=_bounded_float(news_presentation_data.get("notable_threshold"), 0.55, 0, 1),
                important_threshold=_bounded_float(news_presentation_data.get("important_threshold"), 0.68, 0, 1),
                major_threshold=_bounded_float(news_presentation_data.get("major_threshold"), 0.86, 0, 1),
            ),
        ),
        persistence=PersistenceSettings(
            database_path=Path(str(
                persistence_data.get("database_path", "~/.local/share/olympus/core.db")
            )),
            incident_retention_days=min(
                _positive_int(persistence_data.get("incident_retention_days"), 30), 3650
            ),
            news_memory_retention_days=min(
                _positive_int(persistence_data.get("news_memory_retention_days"), 7), 365
            ),
        ),
        security=SecuritySettings(
            require_agent_auth=bool(security_data.get("require_agent_auth", True)),
            enrollment_token_ttl_minutes=min(
                _positive_int(security_data.get("enrollment_token_ttl_minutes"), 10), 1440
            ),
            auth_timeout_seconds=_bounded_float(
                security_data.get("auth_timeout_seconds"), 10.0, 1.0, 60.0
            ),
            revocation_refresh_seconds=_bounded_float(
                security_data.get("revocation_refresh_seconds"), 30.0, 1.0, 3600.0
            ),
            last_seen_write_seconds=_bounded_float(
                security_data.get("last_seen_write_seconds"), 60.0, 5.0, 3600.0
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
