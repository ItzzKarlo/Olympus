from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import time
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from olympus_core.config import FootballSettings
from olympus_core.integrations.football.base import FootballProviderError, FootballRateLimitError
from olympus_core.integrations.football.normalization import (
    normalize_events,
    normalize_fixture,
    normalize_lineups,
    normalize_statistics,
)
from olympus_core.models.football import MatchPhase, ProviderFootballSnapshot


class ApiFootballProvider:
    """Small API-Football v3 boundary; provider payloads stop here."""

    API_BASE = "https://v3.football.api-sports.io"

    def __init__(
        self,
        settings: FootballSettings,
        client: httpx.AsyncClient | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic_clock or time.monotonic
        self._schedule: list[Any] = []
        self._schedule_refreshed_at: float | None = None

    async def _get(self, path: str, params: dict[str, Any]) -> list[Any]:
        if not self._settings.api_key:
            raise FootballProviderError("API-Football key is missing")
        try:
            response = await self._client.get(
                f"{self.API_BASE}{path}",
                params=params,
                headers={"x-apisports-key": self._settings.api_key},
            )
        except httpx.HTTPError as error:
            raise FootballProviderError("API-Football is temporarily unavailable") from error
        if response.status_code == 429:
            retry = response.headers.get("retry-after")
            try:
                retry_after = float(retry) if retry is not None else None
            except ValueError:
                retry_after = None
            raise FootballRateLimitError("API-Football rate limit reached", retry_after)
        if response.status_code in {401, 403}:
            raise FootballProviderError("API-Football rejected the configured credentials")
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise FootballProviderError("API-Football returned an invalid response") from error
        if not isinstance(payload, Mapping):
            raise FootballProviderError("API-Football returned an invalid response")
        errors = payload.get("errors")
        if (isinstance(errors, Mapping) and errors) or (isinstance(errors, list) and errors):
            raise FootballProviderError("API-Football reported a provider error")
        values = payload.get("response")
        if not isinstance(values, list):
            raise FootballProviderError("API-Football returned an invalid response")
        return values

    async def _refresh_schedule(self, now: datetime) -> None:
        local_day = now.astimezone(ZoneInfo(self._settings.timezone)).date()
        values = await self._get("/fixtures", {
            "team": self._settings.team_id,
            "from": (local_day - timedelta(days=2)).isoformat(),
            "to": (local_day + timedelta(days=90)).isoformat(),
            "timezone": self._settings.timezone,
        })
        self._schedule = values
        self._schedule_refreshed_at = self._monotonic()

    async def fetch(self) -> ProviderFootballSnapshot:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Football provider clock must be timezone-aware")
        if (
            self._schedule_refreshed_at is None
            or self._monotonic() - self._schedule_refreshed_at >= self._settings.poll_upcoming_seconds
        ):
            await self._refresh_schedule(now)

        matches = [
            match for value in self._schedule
            if (match := normalize_fixture(value, self._settings)) is not None
        ]
        matches.sort(key=lambda match: match.kickoff)
        next_match = next(
            (match for match in matches if match.status == MatchPhase.UPCOMING and match.kickoff >= now),
            None,
        )
        active = next(
            (match for match in matches if match.status in {MatchPhase.LIVE, MatchPhase.HALF_TIME, MatchPhase.SUSPENDED}),
            None,
        )
        if active is None:
            active = next(
                (
                    match for match in reversed(matches)
                    if match.status == MatchPhase.FINISHED
                    and timedelta(0) <= now - match.kickoff <= timedelta(hours=4)
                ),
                None,
            )
        if active is None and next_match is not None and next_match.kickoff - now <= timedelta(hours=24):
            active = next_match

        detail: Any = None
        if active is not None:
            details = await self._get("/fixtures", {"id": active.id, "timezone": self._settings.timezone})
            detail = details[0] if details else None
            normalized = normalize_fixture(detail, self._settings)
            if normalized is not None:
                active = normalized
                if normalized.status == MatchPhase.UPCOMING:
                    next_match = normalized

        tracked_team = next(
            (team for match in matches for team in (match.home, match.away) if team.id == self._settings.tracked_id),
            None,
        )
        if tracked_team is None:
            from olympus_core.models.football import FootballTeam
            tracked_team = FootballTeam(
                id=self._settings.tracked_id,
                name=self._settings.team_name,
                short_name=self._settings.team_short_name,
                code=self._settings.team_code,
            )
        return ProviderFootballSnapshot(
            tracked_team=tracked_team,
            next_match=next_match,
            match=active,
            events=normalize_events(detail.get("events") if isinstance(detail, Mapping) else None, active, self._settings)
            if active is not None else [],
            lineups=normalize_lineups(detail.get("lineups") if isinstance(detail, Mapping) else None, active, self._settings)
            if active is not None else None,
            statistics=normalize_statistics(detail.get("statistics") if isinstance(detail, Mapping) else None, active, self._settings)
            if active is not None else None,
            observed_at=now,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
