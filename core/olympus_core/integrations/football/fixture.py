import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from olympus_core.config import FootballSettings
from olympus_core.integrations.football.base import FootballProviderError
from olympus_core.integrations.football.normalization import (
    normalize_events,
    normalize_fixture,
    normalize_lineups,
    normalize_player_statistics,
    normalize_statistics,
)
from olympus_core.models.football import FootballQuotaState, FootballTeam, MatchPhase, ProviderFootballSnapshot


class FixtureFootballProvider:
    """Development-only file provider for end-to-end Matchday simulation."""

    def __init__(self, settings: FootballSettings) -> None:
        self._settings = settings
        self._path = Path(settings.fixture_path or "")

    def _read(self) -> Any:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise FootballProviderError("Development football fixture is unavailable") from error

    async def fetch(self) -> ProviderFootballSnapshot:
        payload = await asyncio.to_thread(self._read)
        values = payload.get("response") if isinstance(payload, Mapping) else None
        if not isinstance(values, list) or not values:
            raise FootballProviderError("Development football fixture is invalid")
        raw = values[0]
        match = normalize_fixture(raw, self._settings)
        if match is None:
            raise FootballProviderError("Development football fixture is invalid")
        tracked = match.home if match.home.id == self._settings.tracked_id else match.away
        quota_data = payload.get("olympus_quota") if isinstance(payload, Mapping) else None
        quota = None
        if isinstance(quota_data, Mapping):
            remaining = quota_data.get("daily_remaining")
            quota = FootballQuotaState(
                daily_limit=quota_data.get("daily_limit") if isinstance(quota_data.get("daily_limit"), int) else None,
                daily_remaining=remaining if isinstance(remaining, int) else None,
                minute_limit=quota_data.get("minute_limit") if isinstance(quota_data.get("minute_limit"), int) else None,
                minute_remaining=quota_data.get("minute_remaining") if isinstance(quota_data.get("minute_remaining"), int) else None,
                low=isinstance(remaining, int) and remaining <= self._settings.low_quota_remaining,
                critical=isinstance(remaining, int) and remaining <= self._settings.critical_quota_remaining,
                observed_at=datetime.now(timezone.utc),
            )
        return ProviderFootballSnapshot(
            tracked_team=tracked,
            next_match=match if match.status == MatchPhase.UPCOMING else None,
            match=match,
            events=normalize_events(raw.get("events") if isinstance(raw, Mapping) else None, match, self._settings),
            lineups=normalize_lineups(raw.get("lineups") if isinstance(raw, Mapping) else None, match, self._settings),
            statistics=normalize_statistics(raw.get("statistics") if isinstance(raw, Mapping) else None, match, self._settings),
            player_statistics=normalize_player_statistics(raw.get("players") if isinstance(raw, Mapping) else None, match, self._settings),
            quota=quota,
            observed_at=datetime.now(timezone.utc),
        )

    async def aclose(self) -> None:
        pass
