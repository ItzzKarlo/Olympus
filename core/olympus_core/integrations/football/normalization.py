from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from olympus_core.config import FootballSettings
from olympus_core.models.football import (
    FootballClock,
    FootballCompetition,
    FootballEventType,
    FootballLineupPlayer,
    FootballLineups,
    FootballMatch,
    FootballMatchEvent,
    FootballPlayer,
    FootballScore,
    FootballStatistics,
    FootballTeam,
    FootballTeamLineup,
    FootballTeamStatistics,
    FootballVenue,
    MatchPeriod,
    MatchPhase,
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    if isinstance(value, str):
        cleaned = value.strip().removesuffix("%")
        try:
            return round(float(cleaned))
        except ValueError:
            return None
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().removesuffix("%"))
        except ValueError:
            return None
    return None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def normalize_status(value: Any) -> MatchPhase:
    code = (_text(value) or "").upper()
    if code in {"NS", "TBD"}:
        return MatchPhase.UPCOMING
    if code in {"1H", "2H", "ET", "BT", "P", "LIVE"}:
        return MatchPhase.LIVE
    if code == "HT":
        return MatchPhase.HALF_TIME
    if code in {"FT", "AET", "PEN"}:
        return MatchPhase.FINISHED
    if code in {"SUSP", "INT"}:
        return MatchPhase.SUSPENDED
    if code == "PST":
        return MatchPhase.POSTPONED
    if code in {"CANC", "ABD", "AWD", "WO"}:
        return MatchPhase.CANCELLED
    return MatchPhase.UNKNOWN


def normalize_period(value: Any) -> MatchPeriod:
    code = (_text(value) or "").upper()
    return {
        "1H": MatchPeriod.FIRST_HALF,
        "HT": MatchPeriod.HALF_TIME,
        "2H": MatchPeriod.SECOND_HALF,
        "ET": MatchPeriod.EXTRA_TIME,
        "P": MatchPeriod.PENALTIES,
        "BT": MatchPeriod.BREAK,
    }.get(code, MatchPeriod.UNKNOWN)


def _tracked_team(settings: FootballSettings) -> FootballTeam:
    return FootballTeam(
        id=settings.tracked_id,
        name=settings.team_name,
        short_name=settings.team_short_name,
        code=settings.team_code,
    )


def normalize_team(value: Any, settings: FootballSettings) -> FootballTeam | None:
    team = _mapping(value)
    provider_id = team.get("id")
    name = _text(team.get("name"))
    if provider_id is None or name is None:
        return None
    if str(provider_id) == settings.team_id:
        return _tracked_team(settings)
    return FootballTeam(
        id=f"api-football:{provider_id}",
        name=name,
        short_name=name,
        code=_text(team.get("code")),
    )


def normalize_fixture(value: Any, settings: FootballSettings) -> FootballMatch | None:
    record = _mapping(value)
    fixture = _mapping(record.get("fixture"))
    league = _mapping(record.get("league"))
    teams = _mapping(record.get("teams"))
    status = _mapping(fixture.get("status"))
    goals = _mapping(record.get("goals"))
    fixture_id = fixture.get("id")
    kickoff = _datetime(fixture.get("date"))
    home = normalize_team(teams.get("home"), settings)
    away = normalize_team(teams.get("away"), settings)
    competition_name = _text(league.get("name"))
    if fixture_id is None or kickoff is None or home is None or away is None or competition_name is None:
        return None
    elapsed = _integer(status.get("elapsed"))
    extra = _integer(status.get("extra"))
    period = normalize_period(status.get("short"))
    venue_name = _text(_mapping(fixture.get("venue")).get("name"))
    return FootballMatch(
        id=str(fixture_id),
        competition=FootballCompetition(id=str(league.get("id") or competition_name), name=competition_name),
        kickoff=kickoff,
        venue=FootballVenue(name=venue_name) if venue_name else None,
        home=home,
        away=away,
        status=normalize_status(status.get("short")),
        clock=FootballClock(minute=elapsed, added_time=extra, period=period)
        if elapsed is not None or period != MatchPeriod.UNKNOWN else None,
        score=FootballScore(home=_integer(goals.get("home")), away=_integer(goals.get("away"))),
    )


def normalize_event_type(event_type: Any, detail: Any) -> FootballEventType:
    category = (_text(event_type) or "").casefold()
    normalized_detail = (_text(detail) or "").casefold()
    if category == "goal":
        if "missed" in normalized_detail:
            return FootballEventType.MISSED_PENALTY
        if "own" in normalized_detail:
            return FootballEventType.OWN_GOAL
        if "penalty" in normalized_detail:
            return FootballEventType.PENALTY_GOAL
        return FootballEventType.GOAL
    if category == "card":
        if "yellow-red" in normalized_detail or "second yellow" in normalized_detail:
            return FootballEventType.SECOND_YELLOW
        if "red" in normalized_detail:
            return FootballEventType.RED_CARD
        if "yellow" in normalized_detail:
            return FootballEventType.YELLOW_CARD
    if category in {"subst", "substitution"}:
        return FootballEventType.SUBSTITUTION
    if category == "var":
        return FootballEventType.VAR
    return FootballEventType.UNKNOWN


def _player(value: Any) -> FootballPlayer | None:
    player = _mapping(value)
    name = _text(player.get("name"))
    if name is None:
        return None
    identifier = player.get("id")
    return FootballPlayer(id=str(identifier) if identifier is not None else None, name=name)


def normalize_events(values: Any, match: FootballMatch, settings: FootballSettings) -> list[FootballMatchEvent]:
    if not isinstance(values, list):
        return []
    result: list[FootballMatchEvent] = []
    home_score = 0
    away_score = 0
    for raw in values:
        event = _mapping(raw)
        time_data = _mapping(event.get("time"))
        team = normalize_team(event.get("team"), settings)
        kind = normalize_event_type(event.get("type"), event.get("detail"))
        minute = _integer(time_data.get("elapsed"))
        added = _integer(time_data.get("extra"))
        player = _player(event.get("player"))
        assist = _player(event.get("assist"))
        detail = _text(event.get("detail"))
        identity = "|".join([
            match.id,
            kind.value,
            str(minute),
            str(added),
            team.id if team else "",
            player.id if player and player.id else player.name if player else "",
            assist.id if assist and assist.id else assist.name if assist else "",
            detail or "",
        ])
        score_after = None
        if kind in {FootballEventType.GOAL, FootballEventType.OWN_GOAL, FootballEventType.PENALTY_GOAL} and team:
            if team.id == match.home.id:
                home_score += 1
            elif team.id == match.away.id:
                away_score += 1
            score_after = FootballScore(home=home_score, away=away_score)
        result.append(FootballMatchEvent(
            id=sha256(identity.encode("utf-8")).hexdigest()[:24],
            type=kind,
            minute=minute,
            added_time=added,
            team=team,
            player=player,
            assist=assist,
            score_after=score_after,
            for_tracked_team=team is not None and team.id == settings.tracked_id,
            detail=detail,
        ))
    return result


def _lineup_players(values: Any, starter: bool) -> list[FootballLineupPlayer]:
    if not isinstance(values, list):
        return []
    players: list[FootballLineupPlayer] = []
    for value in values:
        player = _mapping(_mapping(value).get("player"))
        name = _text(player.get("name"))
        if name is None:
            continue
        identifier = player.get("id")
        players.append(FootballLineupPlayer(
            id=str(identifier) if identifier is not None else None,
            name=name,
            number=_integer(player.get("number")),
            position=_text(player.get("pos")),
            starter=starter,
        ))
    return players


def normalize_lineups(values: Any, match: FootballMatch, settings: FootballSettings) -> FootballLineups | None:
    if not isinstance(values, list):
        return None
    sides: dict[str, FootballTeamLineup] = {}
    for value in values:
        lineup = _mapping(value)
        team = normalize_team(lineup.get("team"), settings)
        if team is None:
            continue
        side = "home" if team.id == match.home.id else "away" if team.id == match.away.id else ""
        if not side:
            continue
        sides[side] = FootballTeamLineup(
            team=team,
            formation=_text(lineup.get("formation")),
            players=[
                *_lineup_players(lineup.get("startXI"), True),
                *_lineup_players(lineup.get("substitutes"), False),
            ],
        )
    return FootballLineups(home=sides.get("home"), away=sides.get("away")) if sides else None


STAT_FIELDS = {
    "ball possession": "possession_percent",
    "total shots": "shots",
    "shots on goal": "shots_on_target",
    "corner kicks": "corners",
    "fouls": "fouls",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "offsides": "offsides",
    "total passes": "passes",
    "passes %": "pass_accuracy_percent",
}


def _team_statistics(values: Any) -> FootballTeamStatistics:
    data: dict[str, float | int | None] = {}
    if isinstance(values, list):
        for value in values:
            statistic = _mapping(value)
            field = STAT_FIELDS.get((_text(statistic.get("type")) or "").casefold())
            if field is None:
                continue
            raw = statistic.get("value")
            data[field] = _number(raw) if field.endswith("percent") else _integer(raw)
    return FootballTeamStatistics(**data)


def normalize_statistics(values: Any, match: FootballMatch, settings: FootballSettings) -> FootballStatistics | None:
    if not isinstance(values, list):
        return None
    sides: dict[str, FootballTeamStatistics] = {}
    for value in values:
        entry = _mapping(value)
        team = normalize_team(entry.get("team"), settings)
        if team is None:
            continue
        side = "home" if team.id == match.home.id else "away" if team.id == match.away.id else ""
        if side:
            sides[side] = _team_statistics(entry.get("statistics"))
    return FootballStatistics(home=sides.get("home"), away=sides.get("away")) if sides else None
