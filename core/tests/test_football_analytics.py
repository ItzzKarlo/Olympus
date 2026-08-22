from datetime import datetime, timezone
import unittest

from olympus_core.config import FootballPlayerSettings, FootballSettings
from olympus_core.integrations.football.analytics import calculate_match_flow, result_for_tracked_team
from olympus_core.integrations.football.collector import FootballCollector, MatchdayPolicy
from olympus_core.integrations.football.normalization import (
    normalize_events,
    normalize_fixture,
    normalize_lineups,
    normalize_player_statistics,
)
from olympus_core.models.football import (
    FootballEventType,
    FootballMatchEvent,
    FootballQuotaState,
    FootballResult,
    FootballStatistics,
    FootballTeamStatistics,
    MatchPhase,
    ProviderFootballSnapshot,
    WatchedPlayerStatus,
)


NOW = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)
SETTINGS = FootballSettings(
    enabled=True,
    api_key="test",
    players=FootballPlayerSettings(watched=("1", "2", "999"), rating_change_threshold=0.25),
    poll_team_stats_seconds=1,
    poll_player_stats_seconds=1,
)


def fixture(status: str = "2H", home: int | None = 2, away: int | None = 1, minute: int = 63) -> dict[str, object]:
    return {
        "fixture": {
            "id": 44,
            "date": "2026-08-29T18:30:00+02:00",
            "venue": {"name": "Allianz Arena"},
            "status": {"short": status, "elapsed": minute, "extra": None},
        },
        "league": {"id": 78, "name": "Bundesliga"},
        "teams": {
            "home": {"id": 157, "name": "Bayern Munich", "code": "BAY"},
            "away": {"id": 165, "name": "Opponent", "code": "OPP"},
        },
        "goals": {"home": home, "away": away},
    }


def player_block(rating: object = "8.4", minutes: int = 72, substitute: bool = False) -> list[dict[str, object]]:
    return [{
        "team": {"id": 157, "name": "Bayern Munich"},
        "players": [{
            "player": {"id": 1, "name": "Harry Kane"},
            "statistics": [{
                "games": {"minutes": minutes, "number": 9, "position": "F", "rating": rating, "substitute": substitute},
                "shots": {"total": 5, "on": 4},
                "goals": {"total": 2, "assists": 1},
                "passes": {"total": 31, "key": 3, "accuracy": "84%"},
                "tackles": {"total": 1, "interceptions": 2, "blocks": 0},
                "duels": {"total": 8, "won": 5},
                "dribbles": {"attempts": 2, "success": 1},
                "fouls": {"committed": 1, "drawn": 2},
                "cards": {"yellow": 0, "red": 0},
                "penalty": {"won": 1, "commited": 0, "scored": 1, "missed": 0, "saved": 0},
            }],
        }],
    }]


def snapshot(rating: object = "8.4", *, status: str = "2H", events: list[dict[str, object]] | None = None) -> ProviderFootballSnapshot:
    raw = fixture(status)
    match = normalize_fixture(raw, SETTINGS)
    return ProviderFootballSnapshot(
        tracked_team=match.home,
        match=match,
        events=normalize_events(events or [], match, SETTINGS),
        lineups=normalize_lineups([{
            "team": {"id": 157, "name": "Bayern Munich"},
            "formation": "4-2-3-1",
            "startXI": [{"player": {"id": 1, "name": "Harry Kane", "number": 9, "pos": "F"}}],
            "substitutes": [{"player": {"id": 2, "name": "Bench Player", "number": 22, "pos": "M"}}],
        }], match, SETTINGS),
        statistics=FootballStatistics(
            home=FootballTeamStatistics(possession_percent=62, shots=10, shots_on_target=5, corners=4),
            away=FootballTeamStatistics(possession_percent=38, shots=4, shots_on_target=1, corners=2),
        ),
        player_statistics=normalize_player_statistics(player_block(rating), match, SETTINGS),
        observed_at=NOW,
    )


class DummyProvider:
    def __init__(self, values: list[ProviderFootballSnapshot]) -> None:
        self.values = values

    async def fetch(self) -> ProviderFootballSnapshot:
        return self.values.pop(0)

    async def aclose(self) -> None:
        pass


class PlayerNormalizationTests(unittest.TestCase):
    def test_normalizes_complete_player_performance_without_provider_shapes_leaking(self) -> None:
        match = normalize_fixture(fixture(), SETTINGS)
        player = normalize_player_statistics(player_block(), match, SETTINGS)[0]

        self.assertEqual(player.player.name, "Harry Kane")
        self.assertEqual(player.player.number, 9)
        self.assertEqual(player.minutes, 72)
        self.assertEqual(player.rating, 8.4)
        self.assertTrue(player.starter)
        self.assertEqual((player.goals, player.assists), (2, 1))
        self.assertEqual((player.shots.total, player.shots.on_target), (5, 4))
        self.assertEqual((player.passes.total, player.passes.key, player.passes.accuracy_percent), (31, 3, 84))
        self.assertEqual((player.defending.tackles, player.defending.interceptions), (1, 2))
        self.assertEqual((player.duels.total, player.duels.won), (8, 5))
        self.assertEqual((player.dribbles.attempted, player.dribbles.successful), (2, 1))
        self.assertEqual((player.cards.yellow, player.cards.red), (0, 0))
        self.assertEqual(player.penalties.scored, 1)

    def test_missing_and_malformed_rating_remain_unavailable(self) -> None:
        match = normalize_fixture(fixture(), SETTINGS)
        malformed = normalize_player_statistics(player_block("excellent"), match, SETTINGS)[0]
        missing = normalize_player_statistics(player_block(None), match, SETTINGS)[0]
        self.assertIsNone(malformed.rating)
        self.assertIsNone(missing.rating)


class WatchedAndRatingTests(unittest.IsolatedAsyncioTestCase):
    async def test_watched_starting_bench_absent_and_substituted_states(self) -> None:
        prematch_snapshot = snapshot(status="NS")
        prematch_snapshot.match.kickoff = NOW
        prematch_snapshot.next_match = prematch_snapshot.match
        collector = FootballCollector(SETTINGS, DummyProvider([prematch_snapshot]), lambda state: None, lambda event: None)
        state = await collector.poll_once(monotonic_now=0, now=NOW)
        statuses = {item.player.id: item.status for item in state.matchday.watched_players}
        self.assertEqual(statuses, {"1": WatchedPlayerStatus.STARTING, "2": WatchedPlayerStatus.BENCH, "999": WatchedPlayerStatus.UNAVAILABLE})

        substitution = [{
            "time": {"elapsed": 67, "extra": None},
            "team": {"id": 157, "name": "Bayern Munich"},
            "player": {"id": 1, "name": "Harry Kane"},
            "assist": {"id": 2, "name": "Bench Player"},
            "type": "subst",
            "detail": "Substitution 1",
        }]
        live = snapshot(events=substitution)
        collector = FootballCollector(SETTINGS, DummyProvider([live]), lambda state: None, lambda event: None)
        state = await collector.poll_once(monotonic_now=0, now=NOW)
        self.assertEqual(state.matchday.watched_players[0].status, WatchedPlayerStatus.SUBSTITUTED)

    async def test_rating_history_threshold_dedup_and_restart_baseline(self) -> None:
        values = [snapshot(value) for value in ("7.1", "7.2", "7.5", "7.5", "8.0")]
        events = []
        collector = FootballCollector(SETTINGS, DummyProvider(values), lambda state: None, events.append)
        states = [await collector.poll_once(monotonic_now=index * 60, now=NOW) for index in range(5)]

        rating_events = [event for event in events if event.type == "football.player.rating_changed"]
        self.assertEqual([event.payload["delta"] for event in rating_events], [0.3, 0.5])
        self.assertEqual([sample.rating for sample in states[-1].matchday.rating_history[0].samples], [7.1, 7.2, 7.5, 8.0])

        restart_events = []
        restarted = FootballCollector(SETTINGS, DummyProvider([snapshot("8.0")]), lambda state: None, restart_events.append)
        state = await restarted.poll_once(monotonic_now=0, now=NOW)
        self.assertEqual(state.matchday.watched_players[0].rating, 8.0)
        self.assertFalse(any(event.type == "football.player.rating_changed" for event in restart_events))


class MatchFlowAndResultTests(unittest.TestCase):
    def point(self, previous: FootballStatistics | None, current: FootballStatistics | None, events=(), prior=None):
        return calculate_match_flow(
            previous, current, list(events), tracked_home=True, previous_weight=prior,
            minute=30, observed_at=NOW,
        )

    def test_flow_distinguishes_pressure_neutral_smoothing_and_bounds(self) -> None:
        zero = FootballStatistics(home=FootballTeamStatistics(shots=0, shots_on_target=0, corners=0), away=FootballTeamStatistics(shots=0, shots_on_target=0, corners=0))
        bayern = FootballStatistics(home=FootballTeamStatistics(shots=5, shots_on_target=3, corners=2), away=FootballTeamStatistics(shots=1, shots_on_target=0, corners=0))
        opponent = FootballStatistics(home=FootballTeamStatistics(shots=5, shots_on_target=3, corners=2), away=FootballTeamStatistics(shots=7, shots_on_target=4, corners=3))
        neutral = FootballStatistics(home=FootballTeamStatistics(shots=2, shots_on_target=1, corners=1), away=FootballTeamStatistics(shots=2, shots_on_target=1, corners=1))

        self.assertGreater(self.point(zero, bayern).tracked_team, 0.5)
        pressured = self.point(bayern, opponent, prior=0.8)
        self.assertLess(pressured.tracked_team, 0.8)
        self.assertGreaterEqual(pressured.tracked_team, 0.12)
        self.assertLessEqual(pressured.tracked_team, 0.88)
        self.assertEqual(self.point(zero, neutral).tracked_team, 0.5)

    def test_events_only_fallback_and_no_data_omission(self) -> None:
        goal = FootballMatchEvent(
            id="goal", type=FootballEventType.GOAL, minute=17,
            team=normalize_fixture(fixture(), SETTINGS).home, for_tracked_team=True,
        )
        self.assertGreater(self.point(None, None, [goal]).tracked_team, 0.5)
        self.assertIsNone(self.point(None, None))

    def test_result_is_relative_to_tracked_team_and_missing_score_is_unknown(self) -> None:
        for scores, expected in [((2, 1), FootballResult.WIN), ((1, 1), FootballResult.DRAW), ((0, 1), FootballResult.LOSS), ((None, 1), FootballResult.UNKNOWN)]:
            raw = fixture("FT", *scores)
            snap = ProviderFootballSnapshot(tracked_team=normalize_fixture(raw, SETTINGS).home, match=normalize_fixture(raw, SETTINGS), observed_at=NOW)
            context = MatchdayPolicy(SETTINGS).state(snap, NOW).matchday
            with self.subTest(scores=scores):
                self.assertEqual(result_for_tracked_team(context), expected)

    def test_quota_pressure_stretches_fast_polling_deterministically(self) -> None:
        snap = snapshot()
        context = MatchdayPolicy(SETTINGS).state(snap, NOW).matchday
        collector = FootballCollector(SETTINGS, DummyProvider([]), lambda state: None, lambda event: None)
        normal = MatchdayPolicy(SETTINGS).state(snap, NOW)
        low = normal.model_copy(update={"quota": FootballQuotaState(daily_remaining=20, low=True, observed_at=NOW)})
        critical = normal.model_copy(update={"quota": FootballQuotaState(daily_remaining=4, low=True, critical=True, observed_at=NOW)})
        self.assertEqual(collector.poll_interval(normal), 15)
        self.assertEqual(collector.poll_interval(low), 30)
        self.assertEqual(collector.poll_interval(critical), 60)


if __name__ == "__main__":
    unittest.main()
