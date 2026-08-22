from dataclasses import dataclass
import os


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
