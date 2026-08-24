from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from olympus_core.config import FootballSettings
from olympus_core.integrations.football.base import FootballProviderError, FootballRateLimitError
from olympus_core.models.football import (
    FootballClock,
    FootballCompetition,
    FootballEventType,
    FootballLineupPlayer,
    FootballLineups,
    FootballMatch,
    FootballMatchEvent,
    FootballPlayer,
    FootballQuotaState,
    FootballScore,
    FootballTeam,
    FootballTeamLineup,
    FootballVenue,
    MatchPeriod,
    MatchPhase,
    ProviderFootballSnapshot,
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _tracked_team(settings: FootballSettings) -> FootballTeam:
    return FootballTeam(
        id=settings.tracked_id,
        name=settings.team_name,
        short_name=settings.team_short_name,
        code=settings.team_code,
    )


def normalize_football_data_team(value: Any, settings: FootballSettings) -> FootballTeam | None:
    team = _mapping(value)
    provider_id = team.get("id")
    name = _text(team.get("name"))
    if provider_id is None or name is None:
        return None
    if str(provider_id) == settings.team_id:
        return _tracked_team(settings)
    return FootballTeam(
        id=f"football-data:{provider_id}",
        name=name,
        short_name=_text(team.get("shortName")) or name,
        code=_text(team.get("tla")),
    )


def normalize_football_data_status(value: Any) -> MatchPhase:
    status = (_text(value) or "").upper()
    if status in {"SCHEDULED", "TIMED"}:
        return MatchPhase.UPCOMING
    if status in {"IN_PLAY", "EXTRA_TIME", "PENALTY_SHOOTOUT", "LIVE"}:
        return MatchPhase.LIVE
    if status == "PAUSED":
        return MatchPhase.HALF_TIME
    if status in {"FINISHED", "AWARDED"}:
        return MatchPhase.FINISHED
    if status == "SUSPENDED":
        return MatchPhase.SUSPENDED
    if status == "POSTPONED":
        return MatchPhase.POSTPONED
    if status == "CANCELLED":
        return MatchPhase.CANCELLED
    return MatchPhase.UNKNOWN


def _period(status: str, minute: int | None) -> MatchPeriod:
    if status == "PAUSED":
        return MatchPeriod.HALF_TIME
    if status == "EXTRA_TIME":
        return MatchPeriod.EXTRA_TIME
    if status == "PENALTY_SHOOTOUT":
        return MatchPeriod.PENALTIES
    if status == "IN_PLAY":
        return MatchPeriod.FIRST_HALF if minute is None or minute <= 45 else MatchPeriod.SECOND_HALF
    return MatchPeriod.UNKNOWN


def normalize_football_data_match(value: Any, settings: FootballSettings) -> FootballMatch | None:
    record = _mapping(value)
    match_id = record.get("id")
    kickoff = _datetime(record.get("utcDate"))
    competition = _mapping(record.get("competition"))
    competition_name = _text(competition.get("name"))
    home = normalize_football_data_team(record.get("homeTeam"), settings)
    away = normalize_football_data_team(record.get("awayTeam"), settings)
    if match_id is None or kickoff is None or competition_name is None or home is None or away is None:
        return None

    status_code = (_text(record.get("status")) or "").upper()
    minute = _integer(record.get("minute"))
    injury_time = _integer(record.get("injuryTime"))
    full_time = _mapping(_mapping(record.get("score")).get("fullTime"))
    venue = _text(record.get("venue"))
    period = _period(status_code, minute)
    return FootballMatch(
        id=str(match_id),
        competition=FootballCompetition(
            id=str(competition.get("id") or competition.get("code") or competition_name),
            name=competition_name,
        ),
        kickoff=kickoff,
        venue=FootballVenue(name=venue) if venue else None,
        home=home,
        away=away,
        status=normalize_football_data_status(status_code),
        clock=FootballClock(minute=minute, added_time=injury_time, period=period)
        if minute is not None or period != MatchPeriod.UNKNOWN else None,
        score=FootballScore(
            home=_integer(full_time.get("home")),
            away=_integer(full_time.get("away")),
        ),
    )


def _player(value: Any) -> FootballPlayer | None:
    player = _mapping(value)
    name = _text(player.get("name"))
    if name is None:
        return None
    identifier = player.get("id")
    return FootballPlayer(
        id=str(identifier) if identifier is not None else None,
        name=name,
        number=_integer(player.get("shirtNumber")),
        position=_text(player.get("position")),
    )


def _event_id(match: FootballMatch, *parts: Any) -> str:
    identity = "|".join([match.id, *(str(part or "") for part in parts)])
    return sha256(identity.encode("utf-8")).hexdigest()[:24]


def normalize_football_data_events(
    value: Any,
    match: FootballMatch,
    settings: FootballSettings,
) -> list[FootballMatchEvent]:
    record = _mapping(value)
    events: list[FootballMatchEvent] = []
    goals = record.get("goals")
    if isinstance(goals, list):
        for raw in goals:
            goal = _mapping(raw)
            team = normalize_football_data_team(goal.get("team"), settings)
            scorer = _player(goal.get("scorer"))
            assist = _player(goal.get("assist"))
            minute = _integer(goal.get("minute"))
            injury_time = _integer(goal.get("injuryTime"))
            if team is None or minute is None:
                continue
            goal_type = (_text(goal.get("type")) or "").upper()
            kind = {
                "OWN": FootballEventType.OWN_GOAL,
                "PENALTY": FootballEventType.PENALTY_GOAL,
            }.get(goal_type, FootballEventType.GOAL)
            score = _mapping(goal.get("score"))
            score_after = FootballScore(
                home=_integer(score.get("home")),
                away=_integer(score.get("away")),
            ) if score else None
            events.append(FootballMatchEvent(
                id=_event_id(match, kind.value, minute, injury_time, team.id if team else None, scorer.id if scorer else None),
                type=kind,
                minute=minute,
                added_time=injury_time,
                team=team,
                player=scorer,
                assist=assist,
                score_after=score_after,
                for_tracked_team=team is not None and team.id == settings.tracked_id,
                detail=goal_type.casefold().replace("_", " ") or None,
            ))

    bookings = record.get("bookings")
    if isinstance(bookings, list):
        for raw in bookings:
            booking = _mapping(raw)
            team = normalize_football_data_team(booking.get("team"), settings)
            player = _player(booking.get("player"))
            minute = _integer(booking.get("minute"))
            card = (_text(booking.get("card")) or "").upper()
            kind = {
                "YELLOW": FootballEventType.YELLOW_CARD,
                "YELLOW_RED": FootballEventType.SECOND_YELLOW,
                "RED": FootballEventType.RED_CARD,
            }.get(card, FootballEventType.UNKNOWN)
            if kind == FootballEventType.UNKNOWN or team is None or minute is None:
                continue
            events.append(FootballMatchEvent(
                id=_event_id(match, kind.value, minute, team.id if team else None, player.id if player else None),
                type=kind,
                minute=minute,
                team=team,
                player=player,
                for_tracked_team=team is not None and team.id == settings.tracked_id,
                detail=card.casefold().replace("_", " ") or None,
            ))

    substitutions = record.get("substitutions")
    if isinstance(substitutions, list):
        for raw in substitutions:
            substitution = _mapping(raw)
            team = normalize_football_data_team(substitution.get("team"), settings)
            player_out = _player(substitution.get("playerOut"))
            player_in = _player(substitution.get("playerIn"))
            minute = _integer(substitution.get("minute"))
            if team is None or minute is None or (player_out is None and player_in is None):
                continue
            events.append(FootballMatchEvent(
                id=_event_id(
                    match,
                    FootballEventType.SUBSTITUTION.value,
                    minute,
                    team.id if team else None,
                    player_out.id if player_out else None,
                    player_in.id if player_in else None,
                ),
                type=FootballEventType.SUBSTITUTION,
                minute=minute,
                team=team,
                player=player_out,
                assist=player_in,
                for_tracked_team=team is not None and team.id == settings.tracked_id,
                detail="substitution",
            ))
    return events


def _lineup(team_data: Any, team: FootballTeam) -> FootballTeamLineup | None:
    data = _mapping(team_data)
    players: list[FootballLineupPlayer] = []
    for key, starter in (("lineup", True), ("bench", False)):
        values = data.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            player = _player(value)
            if player is not None:
                players.append(FootballLineupPlayer(**player.model_dump(), starter=starter))
    if not players:
        return None
    return FootballTeamLineup(
        team=team,
        formation=_text(data.get("formation")),
        players=players,
    )


def normalize_football_data_lineups(value: Any, match: FootballMatch) -> FootballLineups | None:
    record = _mapping(value)
    home = _lineup(record.get("homeTeam"), match.home)
    away = _lineup(record.get("awayTeam"), match.away)
    return FootballLineups(home=home, away=away) if home is not None or away is not None else None


class FootballDataProvider:
    """football-data.org v4 provider for normalized fixture and score data."""

    API_BASE = "https://api.football-data.org/v4"
    # The free plan permits ten requests/minute. One request/minute during a
    # match is responsive enough for a wall display and leaves ample headroom.
    minimum_poll_seconds = 60.0
    post_match_minimum_poll_seconds = 300.0

    def __init__(
        self,
        settings: FootballSettings,
        client: httpx.AsyncClient | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._quota: FootballQuotaState | None = None

    @staticmethod
    def _header_integer(value: str | None) -> int | None:
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    def _capture_quota(self, response: httpx.Response) -> None:
        remaining = self._header_integer(response.headers.get("x-requestsavailable"))
        if remaining is None:
            return
        self._quota = FootballQuotaState(
            minute_remaining=remaining,
            low=remaining <= 2,
            critical=remaining <= 1,
            observed_at=self._clock(),
        )

    async def _get_matches(self, now: datetime) -> list[Any]:
        key = self._settings.football_data_api_key
        if not key:
            raise FootballProviderError("football-data requires OLYMPUS_FOOTBALL_DATA_API_KEY")
        if not self._settings.team_id.isdecimal():
            raise FootballProviderError("football-data team_id must be a numeric provider team ID")
        local_day = now.astimezone(ZoneInfo(self._settings.timezone)).date()
        path = f"/teams/{self._settings.team_id}/matches"
        try:
            response = await self._client.get(
                f"{self.API_BASE}{path}",
                params={
                    "dateFrom": (local_day - timedelta(days=2)).isoformat(),
                    "dateTo": (local_day + timedelta(days=90)).isoformat(),
                    "limit": 100,
                },
                headers={"X-Auth-Token": key},
            )
        except httpx.HTTPError as error:
            raise FootballProviderError(f"football-data request failed for team {self._settings.team_id}") from error
        self._capture_quota(response)
        if response.status_code == 429:
            retry_after = self._header_integer(response.headers.get("retry-after"))
            if retry_after is None:
                retry_after = self._header_integer(response.headers.get("x-requestcounter-reset"))
            raise FootballRateLimitError(
                "football-data rate limit reached",
                float(retry_after) if retry_after is not None else 60.0,
            )
        if response.status_code in {401, 403}:
            raise FootballProviderError(
                f"football-data rejected credentials or subscription access for team {self._settings.team_id}"
            )
        if response.status_code == 404:
            raise FootballProviderError(f"football-data team_id {self._settings.team_id} was not found")
        if response.status_code >= 500:
            raise FootballProviderError(
                f"football-data upstream error {response.status_code} for team {self._settings.team_id}"
            )
        if response.status_code >= 400:
            raise FootballProviderError(
                f"football-data request error {response.status_code} for team {self._settings.team_id}"
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise FootballProviderError("football-data returned malformed JSON") from error
        matches = payload.get("matches") if isinstance(payload, Mapping) else None
        if not isinstance(matches, list):
            raise FootballProviderError("football-data returned a malformed matches response")
        return matches

    async def fetch(self) -> ProviderFootballSnapshot:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Football provider clock must be timezone-aware")
        values = await self._get_matches(now)
        normalized = [
            (match, value)
            for value in values
            if (match := normalize_football_data_match(value, self._settings)) is not None
        ]
        if values and not normalized:
            raise FootballProviderError("football-data returned malformed match records")
        normalized.sort(key=lambda item: item[0].kickoff)
        matches = [item[0] for item in normalized]
        next_match = next(
            (match for match in matches if match.status == MatchPhase.UPCOMING and match.kickoff >= now),
            None,
        )
        active = next((item for item in normalized if item[0].status in {
            MatchPhase.LIVE,
            MatchPhase.HALF_TIME,
            MatchPhase.SUSPENDED,
        }), None)
        if active is None:
            active = next((item for item in reversed(normalized) if (
                item[0].status == MatchPhase.FINISHED
                and timedelta(0) <= now - item[0].kickoff <= timedelta(hours=4)
            )), None)
        if active is None:
            active = next((item for item in normalized if (
                item[0].status == MatchPhase.UPCOMING
                and -timedelta(hours=4) <= item[0].kickoff - now <= timedelta(hours=24)
            )), None)

        match = active[0] if active is not None else None
        raw_match = active[1] if active is not None else None
        tracked_team = next(
            (team for current in matches for team in (current.home, current.away) if team.id == self._settings.tracked_id),
            _tracked_team(self._settings),
        )
        return ProviderFootballSnapshot(
            tracked_team=tracked_team,
            next_match=next_match,
            match=match,
            events=normalize_football_data_events(raw_match, match, self._settings) if match is not None else [],
            lineups=normalize_football_data_lineups(raw_match, match) if match is not None else None,
            statistics=None,
            player_statistics=[],
            quota=self._quota,
            observed_at=now,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
