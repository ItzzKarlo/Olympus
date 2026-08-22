from dataclasses import dataclass
from datetime import datetime

from olympus_core.config import FootballSettings
from olympus_core.models.football import (
    FootballEventType,
    FootballLineupPlayer,
    FootballLineups,
    FootballMatchEvent,
    FootballMatchFlowPoint,
    FootballPlayer,
    FootballPlayerRatingHistory,
    FootballPlayerStatistics,
    FootballRatingSample,
    FootballResult,
    FootballStatistics,
    FootballStatisticsSnapshot,
    FootballTeamStatistics,
    MatchPhase,
    MatchdayContext,
    ProviderFootballSnapshot,
    WatchedPlayerState,
    WatchedPlayerStatus,
)


@dataclass(frozen=True, slots=True)
class RatingChange:
    player: FootballPlayer
    previous: float
    current: float
    delta: float


def result_for_tracked_team(context: MatchdayContext) -> FootballResult:
    home = context.match.score.home
    away = context.match.score.away
    if home is None or away is None or context.phase not in {MatchPhase.FINISHED, MatchPhase.POST_MATCH}:
        return FootballResult.UNKNOWN
    tracked_home = context.match.home.id == context.tracked_team.id
    tracked_score, opponent_score = (home, away) if tracked_home else (away, home)
    if tracked_score > opponent_score:
        return FootballResult.WIN
    if tracked_score < opponent_score:
        return FootballResult.LOSS
    return FootballResult.DRAW


def _delta(current: int | None, previous: int | None) -> float:
    if current is None:
        return 0.0
    return float(max(0, current - (previous or 0)))


def calculate_match_flow(
    previous: FootballStatistics | None,
    current: FootballStatistics | None,
    events: list[FootballMatchEvent],
    *,
    tracked_home: bool,
    previous_weight: float | None,
    minute: int | None,
    observed_at: datetime,
) -> FootballMatchFlowPoint | None:
    """Create an honest, bounded activity weight from supported stats/events."""
    current_home = current.home if current else None
    current_away = current.away if current else None
    previous_home = previous.home if previous else None
    previous_away = previous.away if previous else None

    def activity(now: FootballTeamStatistics | None, before: FootballTeamStatistics | None) -> float:
        if now is None:
            return 0.0
        return (
            _delta(now.shots, before.shots if before else None)
            + 2.0 * _delta(now.shots_on_target, before.shots_on_target if before else None)
            + 0.6 * _delta(now.corners, before.corners if before else None)
        )

    home_activity = activity(current_home, previous_home)
    away_activity = activity(current_away, previous_away)
    event_activity = False
    for event in events:
        weight = {
            FootballEventType.GOAL: 4.0,
            FootballEventType.OWN_GOAL: 4.0,
            FootballEventType.PENALTY_GOAL: 4.0,
            FootballEventType.RED_CARD: 1.0,
            FootballEventType.SECOND_YELLOW: 1.0,
            FootballEventType.YELLOW_CARD: 0.2,
            FootballEventType.SUBSTITUTION: 0.1,
        }.get(event.type, 0.0)
        if weight <= 0:
            continue
        event_activity = True
        if event.team and event.team.id:
            if event.for_tracked_team == tracked_home:
                home_activity += weight
            else:
                away_activity += weight

    has_statistics = current_home is not None or current_away is not None
    statistics_changed = current is not None and current != previous
    if home_activity + away_activity > 0:
        target = home_activity / (home_activity + away_activity)
        basis = "combined" if event_activity and has_statistics else "events" if event_activity else "statistics"
        home_possession = current_home.possession_percent if current_home else None
        away_possession = current_away.possession_percent if current_away else None
        if home_possession is not None and away_possession is not None and home_possession + away_possession > 0:
            target = target * 0.8 + (home_possession / (home_possession + away_possession)) * 0.2
    elif statistics_changed and current_home and current_away:
        home_possession = current_home.possession_percent
        away_possession = current_away.possession_percent
        if home_possession is None or away_possession is None or home_possession + away_possession <= 0:
            return None
        target = home_possession / (home_possession + away_possession)
        basis = "statistics"
    else:
        return None

    tracked_target = target if tracked_home else 1 - target
    smoothed = tracked_target if previous_weight is None else previous_weight * 0.6 + tracked_target * 0.4
    tracked_weight = min(0.88, max(0.12, smoothed))
    return FootballMatchFlowPoint(
        minute=minute,
        tracked_team=round(tracked_weight, 3),
        opponent=round(1 - tracked_weight, 3),
        basis=basis,
        observed_at=observed_at,
    )


class FootballAnalytics:
    """Owns bounded, one-fixture in-memory ratings, stats history and Match Flow."""

    def __init__(self, settings: FootballSettings) -> None:
        self._settings = settings
        self._match_id: str | None = None
        self._phase: MatchPhase | None = None
        self._lineups: FootballLineups | None = None
        self._statistics: FootballStatistics | None = None
        self._players: list[FootballPlayerStatistics] = []
        self._last_stats_at: float | None = None
        self._last_players_at: float | None = None
        self._statistics_history: list[FootballStatisticsSnapshot] = []
        self._rating_samples: dict[str, list[FootballRatingSample]] = {}
        self._rating_players: dict[str, FootballPlayer] = {}
        self._ratings: dict[str, float] = {}
        self._rating_deltas: dict[str, tuple[float, float]] = {}
        self._flow: list[FootballMatchFlowPoint] = []
        self._flow_statistics: FootballStatistics | None = None
        self._flow_event_ids: set[str] = set()

    def _reset(self, snapshot: ProviderFootballSnapshot) -> None:
        self._match_id = snapshot.match.id if snapshot.match else None
        self._phase = snapshot.match.status if snapshot.match else None
        self._lineups = None
        self._statistics = None
        self._players = []
        self._last_stats_at = None
        self._last_players_at = None
        self._statistics_history = []
        self._rating_samples = {}
        self._rating_players = {}
        self._ratings = {}
        self._rating_deltas = {}
        self._flow = []
        self._flow_statistics = None
        self._flow_event_ids = {event.id for event in snapshot.events}

    def _quota_multiplier(self, snapshot: ProviderFootballSnapshot, *, players: bool) -> float:
        quota = snapshot.quota
        if quota and quota.critical:
            return 10.0 if players else 5.0
        if quota and quota.low:
            return 3.0 if players else 2.0
        return 1.0

    @staticmethod
    def _minute(snapshot: ProviderFootballSnapshot) -> int | None:
        return snapshot.match.clock.minute if snapshot.match and snapshot.match.clock else None

    def _accept_statistics(self, snapshot: ProviderFootballSnapshot, tick: float, force: bool) -> bool:
        if snapshot.statistics is None:
            return False
        interval = self._settings.poll_team_stats_seconds * self._quota_multiplier(snapshot, players=False)
        if not force and self._last_stats_at is not None and tick - self._last_stats_at < interval:
            return False
        self._last_stats_at = tick
        changed = snapshot.statistics != self._statistics
        self._statistics = snapshot.statistics
        if changed:
            self._statistics_history.append(FootballStatisticsSnapshot(
                minute=self._minute(snapshot),
                home=snapshot.statistics.home,
                away=snapshot.statistics.away,
                observed_at=snapshot.observed_at,
            ))
            self._statistics_history = self._statistics_history[-self._settings.max_history_samples:]
        return changed

    def _accept_players(self, snapshot: ProviderFootballSnapshot, tick: float, force: bool) -> list[RatingChange]:
        if not snapshot.player_statistics:
            return []
        interval = self._settings.poll_player_stats_seconds * self._quota_multiplier(snapshot, players=True)
        if not force and self._last_players_at is not None and tick - self._last_players_at < interval:
            return []
        self._last_players_at = tick
        changes: list[RatingChange] = []
        next_deltas: dict[str, tuple[float, float]] = {}
        watched = {value.casefold() for value in self._settings.players.watched}
        for statistic in snapshot.player_statistics:
            player = statistic.player
            key = player.id or player.name.casefold()
            rating = statistic.rating
            if rating is None:
                continue
            previous = self._ratings.get(key)
            self._rating_players[key] = player
            if previous is None or rating != previous:
                samples = self._rating_samples.setdefault(key, [])
                samples.append(FootballRatingSample(
                    minute=self._minute(snapshot), rating=rating, observed_at=snapshot.observed_at,
                ))
                self._rating_samples[key] = samples[-self._settings.max_history_samples:]
            if previous is not None and rating != previous:
                next_deltas[key] = (previous, rating)
                delta = rating - previous
                if (
                    statistic.for_tracked_team
                    and ((player.id or "").casefold() in watched or player.name.casefold() in watched)
                    and abs(delta) >= self._settings.players.rating_change_threshold
                ):
                    changes.append(RatingChange(player, previous, rating, delta))
            self._ratings[key] = rating
        self._rating_deltas = next_deltas
        self._players = snapshot.player_statistics
        return changes

    def _lineup_player(self, selector: str) -> FootballLineupPlayer | None:
        if not self._lineups:
            return None
        for lineup in (self._lineups.home, self._lineups.away):
            if lineup is None or lineup.team.id != self._settings.tracked_id:
                continue
            for player in lineup.players:
                if player.id == selector or player.name.casefold() == selector.casefold():
                    return player
        return None

    def _watched_states(self, context: MatchdayContext) -> list[WatchedPlayerState]:
        states: list[WatchedPlayerState] = []
        substituted_ids = {
            event.player.id or event.player.name.casefold()
            for event in context.events
            if event.type == FootballEventType.SUBSTITUTION and event.for_tracked_team and event.player
        }
        for selector in self._settings.players.watched:
            statistic = next((item for item in self._players if item.for_tracked_team and (
                item.player.id == selector or item.player.name.casefold() == selector.casefold()
            )), None)
            lineup_player = self._lineup_player(selector)
            player = statistic.player if statistic else lineup_player or FootballPlayer(id=selector, name=selector)
            player_key = player.id or player.name.casefold()
            if context.phase in {MatchPhase.POST_MATCH, MatchPhase.FINISHED}:
                status = WatchedPlayerStatus.FINISHED if statistic and (statistic.minutes or 0) > 0 else WatchedPlayerStatus.BENCH if lineup_player else WatchedPlayerStatus.UNAVAILABLE
            elif player_key in substituted_ids or player.name.casefold() in substituted_ids:
                status = WatchedPlayerStatus.SUBSTITUTED
            elif context.phase == MatchPhase.PRE_MATCH:
                status = WatchedPlayerStatus.STARTING if lineup_player and lineup_player.starter else WatchedPlayerStatus.BENCH if lineup_player else WatchedPlayerStatus.UNAVAILABLE
            elif statistic and (statistic.minutes or 0) > 0:
                status = WatchedPlayerStatus.PLAYING
            elif lineup_player and lineup_player.starter:
                status = WatchedPlayerStatus.PLAYING
            elif lineup_player:
                status = WatchedPlayerStatus.BENCH
            else:
                status = WatchedPlayerStatus.UNAVAILABLE
            previous_and_current = self._rating_deltas.get(player_key)
            states.append(WatchedPlayerState(
                player=player,
                status=status,
                rating=statistic.rating if statistic else None,
                previous_rating=previous_and_current[0] if previous_and_current else None,
                rating_delta=round(previous_and_current[1] - previous_and_current[0], 2) if previous_and_current else None,
                statistics=statistic,
            ))
        return states

    def _update_flow(self, snapshot: ProviderFootballSnapshot, statistics_changed: bool) -> None:
        new_events = [event for event in snapshot.events if event.id not in self._flow_event_ids]
        self._flow_event_ids.update(event.id for event in snapshot.events)
        if not statistics_changed and not new_events:
            return
        context_match = snapshot.match
        if context_match is None:
            return
        point = calculate_match_flow(
            self._flow_statistics,
            self._statistics,
            new_events,
            tracked_home=context_match.home.id == self._settings.tracked_id,
            previous_weight=self._flow[-1].tracked_team if self._flow else None,
            minute=self._minute(snapshot) or max((event.minute or 0 for event in new_events), default=None),
            observed_at=snapshot.observed_at,
        )
        if statistics_changed:
            self._flow_statistics = self._statistics
        if point is not None:
            self._flow.append(point)
            self._flow = self._flow[-self._settings.max_history_samples:]

    def enrich(
        self,
        snapshot: ProviderFootballSnapshot,
        context: MatchdayContext,
        tick: float,
    ) -> tuple[MatchdayContext, list[RatingChange]]:
        if snapshot.match is None:
            return context, []
        if self._match_id != snapshot.match.id:
            self._reset(snapshot)
        phase_changed = self._phase != context.phase
        self._phase = context.phase
        if self._lineups is None and snapshot.lineups is not None:
            self._lineups = snapshot.lineups
        statistics_changed = self._accept_statistics(snapshot, tick, phase_changed)
        rating_changes = self._accept_players(snapshot, tick, phase_changed)
        self._update_flow(snapshot, statistics_changed)

        rated = [item for item in self._players if item.rating is not None]
        tracked = sorted((item for item in rated if item.for_tracked_team), key=lambda item: item.rating or 0, reverse=True)[:3]
        opponent = sorted((item for item in rated if not item.for_tracked_team), key=lambda item: item.rating or 0, reverse=True)[:3]
        enriched = context.model_copy(update={
            "lineups": self._lineups,
            "statistics": self._statistics,
            "statistics_history": list(self._statistics_history),
            "player_statistics": list(self._players),
            "top_tracked_players": tracked,
            "top_opponent_players": opponent,
            "rating_history": [
                FootballPlayerRatingHistory(player=self._rating_players[key], samples=list(samples))
                for key, samples in self._rating_samples.items()
                if any(selector.casefold() in {key.casefold(), self._rating_players[key].name.casefold()} for selector in self._settings.players.watched)
            ],
            "match_flow": list(self._flow),
        })
        enriched = enriched.model_copy(update={
            "watched_players": self._watched_states(enriched),
            "result": result_for_tracked_team(enriched),
        })
        return enriched, rating_changes
