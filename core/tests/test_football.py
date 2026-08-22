from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx

from olympus_core.config import FootballSettings, parse_core_config
from olympus_core.integrations.football.api_football import ApiFootballProvider
from olympus_core.integrations.football.base import FootballProviderError, FootballRateLimitError
from olympus_core.integrations.football.collector import FootballCollector, MatchdayPolicy
from olympus_core.integrations.football.normalization import (
    normalize_events,
    normalize_fixture,
    normalize_lineups,
    normalize_statistics,
)
from olympus_core.models.football import FootballEventType, MatchPhase, ProviderFootballSnapshot


SETTINGS = FootballSettings(
    enabled=True,
    timezone="Europe/Berlin",
    api_key="test-key",
)


def raw_fixture(status: str = "NS", kickoff: str = "2026-08-29T18:30:00+02:00", **extra: object) -> dict[str, object]:
    return {
        "fixture": {
            "id": 9001,
            "date": kickoff,
            "venue": {"name": "Allianz Arena"},
            "status": {"short": status, "elapsed": 63 if status == "2H" else None, "extra": 2 if status == "2H" else None},
        },
        "league": {"id": 78, "name": "Bundesliga"},
        "teams": {
            "home": {"id": 157, "name": "Bayern Munich", "code": "BAY"},
            "away": {"id": 165, "name": "Borussia Dortmund", "code": "BVB"},
        },
        "goals": {"home": 2 if status != "NS" else None, "away": 0 if status != "NS" else None},
        **extra,
    }


def raw_events(include_card: bool = True) -> list[dict[str, object]]:
    values = [
        {
            "time": {"elapsed": 17, "extra": None},
            "team": {"id": 157, "name": "Bayern Munich"},
            "player": {"id": 1, "name": "Harry Kane"},
            "assist": {"id": 2, "name": "Jamal Musiala"},
            "type": "Goal",
            "detail": "Normal Goal",
        },
        {
            "time": {"elapsed": 40, "extra": 1},
            "team": {"id": 165, "name": "Borussia Dortmund"},
            "player": {"id": 3, "name": "Opponent"},
            "assist": {"id": None, "name": None},
            "type": "Goal",
            "detail": "Missed Penalty",
        },
    ]
    if include_card:
        values.append({
            "time": {"elapsed": 58, "extra": None},
            "team": {"id": 165, "name": "Borussia Dortmund"},
            "player": {"id": 4, "name": "Defender"},
            "assist": {"id": None, "name": None},
            "type": "Card",
            "detail": "Yellow Card",
        })
    return values


class FootballNormalizationTests(unittest.TestCase):
    def test_fixture_status_score_competition_venue_and_clock(self) -> None:
        match = normalize_fixture(raw_fixture("2H"), SETTINGS)

        self.assertEqual(match.status, MatchPhase.LIVE)
        self.assertEqual(match.home.id, "bayern")
        self.assertEqual(match.away.id, "api-football:165")
        self.assertEqual(match.competition.name, "Bundesliga")
        self.assertEqual(match.venue.name, "Allianz Arena")
        self.assertEqual(match.clock.minute, 63)
        self.assertEqual(match.clock.added_time, 2)
        self.assertEqual(match.score.model_dump(), {"home": 2, "away": 0})

    def test_provider_statuses_are_normalized(self) -> None:
        expected = {
            "NS": MatchPhase.UPCOMING,
            "HT": MatchPhase.HALF_TIME,
            "FT": MatchPhase.FINISHED,
            "PST": MatchPhase.POSTPONED,
            "CANC": MatchPhase.CANCELLED,
            "SUSP": MatchPhase.SUSPENDED,
            "mystery": MatchPhase.UNKNOWN,
        }
        for status, phase in expected.items():
            with self.subTest(status=status):
                self.assertEqual(normalize_fixture(raw_fixture(status), SETTINGS).status, phase)

    def test_events_are_owned_deterministic_and_mark_the_tracked_team(self) -> None:
        match = normalize_fixture(raw_fixture("2H"), SETTINGS)
        first = normalize_events(raw_events(), match, SETTINGS)
        second = normalize_events(raw_events(), match, SETTINGS)

        self.assertEqual([item.id for item in first], [item.id for item in second])
        self.assertEqual(first[0].type, FootballEventType.GOAL)
        self.assertTrue(first[0].for_tracked_team)
        self.assertEqual(first[0].assist.name, "Jamal Musiala")
        self.assertEqual(first[1].type, FootballEventType.MISSED_PENALTY)
        self.assertFalse(first[1].for_tracked_team)
        self.assertEqual(first[2].type, FootballEventType.YELLOW_CARD)

    def test_lineups_and_statistics_allow_missing_values(self) -> None:
        match = normalize_fixture(raw_fixture("2H"), SETTINGS)
        lineups = normalize_lineups([
            {
                "team": {"id": 157, "name": "Bayern Munich"},
                "formation": "4-2-3-1",
                "startXI": [{"player": {"id": 1, "name": "Manuel Neuer", "number": 1, "pos": "G"}}],
                "substitutes": [{"player": {"id": 2, "name": "Sub", "number": 22, "pos": "M"}}],
            },
        ], match, SETTINGS)
        statistics = normalize_statistics([
            {
                "team": {"id": 157, "name": "Bayern Munich"},
                "statistics": [
                    {"type": "Ball Possession", "value": "61%"},
                    {"type": "Total Shots", "value": 14},
                    {"type": "Shots on Goal", "value": 7},
                    {"type": "Fouls", "value": None},
                ],
            },
        ], match, SETTINGS)

        self.assertEqual(lineups.home.formation, "4-2-3-1")
        self.assertTrue(lineups.home.players[0].starter)
        self.assertFalse(lineups.home.players[1].starter)
        self.assertEqual(statistics.home.possession_percent, 61)
        self.assertEqual(statistics.home.shots_on_target, 7)
        self.assertIsNone(statistics.home.fouls)
        self.assertIsNone(normalize_lineups([], match, SETTINGS))
        self.assertIsNone(normalize_statistics([], match, SETTINGS))


class ApiFootballProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_live_fixture_on_initial_fetch(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            payload = raw_fixture("2H", events=raw_events(), lineups=[], statistics=[])
            return httpx.Response(200, json={"errors": {}, "response": [payload]})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = ApiFootballProvider(
            SETTINGS,
            client,
            clock=lambda: datetime(2026, 8, 29, 19, 45, tzinfo=timezone.utc),
            monotonic_clock=lambda: 10,
        )
        state = await provider.fetch()

        self.assertEqual(state.match.status, MatchPhase.LIVE)
        self.assertEqual(len(state.events), 3)
        self.assertEqual(len(calls), 2)
        self.assertIn("team=157", calls[0])
        self.assertIn("id=9001", calls[1])

    async def test_rate_limit_and_malformed_responses_are_explicit(self) -> None:
        limited = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"Retry-After": "42"}),
        ))
        provider = ApiFootballProvider(SETTINGS, limited)
        with self.assertRaises(FootballRateLimitError) as caught:
            await provider.fetch()
        self.assertEqual(caught.exception.retry_after, 42)

        malformed = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"errors": {}, "response": "bad"}),
        ))
        provider = ApiFootballProvider(SETTINGS, malformed)
        with self.assertRaises(FootballProviderError):
            await provider.fetch()


class DummyProvider:
    def __init__(self, responses: list[ProviderFootballSnapshot | Exception]) -> None:
        self.responses = responses

    async def fetch(self) -> ProviderFootballSnapshot:
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def aclose(self) -> None:
        pass


def snapshot(status: str, observed_at: datetime, include_card: bool = False) -> ProviderFootballSnapshot:
    match = normalize_fixture(raw_fixture(status), SETTINGS)
    return ProviderFootballSnapshot(
        tracked_team=match.home,
        next_match=match if match.status == MatchPhase.UPCOMING else None,
        match=match,
        events=normalize_events(raw_events(include_card), match, SETTINGS),
        observed_at=observed_at,
    )


class FootballCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_live_sync_baselines_history_then_emits_only_new_events(self) -> None:
        now = datetime(2026, 8, 29, 19, 45, tzinfo=timezone.utc)
        updates = []
        events = []
        provider = DummyProvider([
            snapshot("2H", now, include_card=False),
            snapshot("2H", now + timedelta(seconds=15), include_card=True),
            snapshot("2H", now + timedelta(seconds=30), include_card=True),
        ])
        collector = FootballCollector(SETTINGS, provider, updates.append, events.append)

        await collector.poll_once(monotonic_now=0, now=now)
        await collector.poll_once(monotonic_now=15, now=now + timedelta(seconds=15))
        await collector.poll_once(monotonic_now=30, now=now + timedelta(seconds=30))

        self.assertEqual([event.type for event in events], ["football.yellow_card"])
        self.assertEqual(updates[-1].matchday.match.score.home, 2)

    async def test_failure_retains_live_context_marks_stale_and_recovers(self) -> None:
        now = datetime(2026, 8, 29, 19, 45, tzinfo=timezone.utc)
        updates = []
        provider = DummyProvider([
            snapshot("2H", now),
            TimeoutError("offline"),
            TimeoutError("offline"),
            snapshot("2H", now + timedelta(seconds=90)),
        ])
        collector = FootballCollector(SETTINGS, provider, updates.append, lambda event: None)

        good = await collector.poll_once(monotonic_now=0, now=now)
        retained = await collector.poll_once(monotonic_now=30, now=now + timedelta(seconds=30))
        stale = await collector.poll_once(monotonic_now=70, now=now + timedelta(seconds=70))
        recovered = await collector.poll_once(monotonic_now=90, now=now + timedelta(seconds=90))

        self.assertFalse(good.stale)
        self.assertFalse(retained.stale)
        self.assertTrue(stale.stale)
        self.assertTrue(stale.matchday.active)
        self.assertFalse(recovered.stale)

    def test_matchday_thresholds_post_window_and_adaptive_intervals(self) -> None:
        kickoff = datetime(2026, 8, 29, 16, 30, tzinfo=timezone.utc)
        policy = MatchdayPolicy(SETTINGS)
        upcoming = snapshot("NS", kickoff - timedelta(hours=2))
        upcoming.match.kickoff = kickoff
        upcoming.next_match.kickoff = kickoff

        early = policy.state(upcoming, kickoff - timedelta(minutes=61))
        prematch = policy.state(upcoming, kickoff - timedelta(minutes=60))
        finished_snapshot = snapshot("FT", kickoff + timedelta(hours=2))
        finished = policy.state(finished_snapshot, kickoff + timedelta(hours=2))
        expired = policy.state(finished_snapshot, kickoff + timedelta(hours=2, minutes=20))

        self.assertIsNone(early.matchday)
        self.assertEqual(prematch.matchday.phase, MatchPhase.PRE_MATCH)
        self.assertEqual(finished.matchday.phase, MatchPhase.POST_MATCH)
        self.assertIsNone(expired.matchday)


class FootballConfigTests(unittest.TestCase):
    def test_disabled_defaults_and_environment_secret(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            disabled = parse_core_config({}).football
        self.assertFalse(disabled.enabled)
        self.assertFalse(disabled.configured)
        self.assertEqual(disabled.team_id, "157")

        with patch.dict("os.environ", {"OLYMPUS_FOOTBALL_API_KEY": "secret"}, clear=True):
            configured = parse_core_config({
                "olympus": {"timezone": "Europe/Berlin"},
                "football": {
                    "enabled": True,
                    "team_id": "157",
                    "poll_live_seconds": 20,
                    "live_stale_seconds": 45,
                    "unavailable_seconds": 600,
                    "matchday": {"pre_match_minutes": 75, "post_match_minutes": 25},
                },
            }).football
        self.assertTrue(configured.configured)
        self.assertEqual(configured.timezone, "Europe/Berlin")
        self.assertEqual(configured.poll_live_seconds, 20)
        self.assertEqual(configured.live_stale_seconds, 45)
        self.assertEqual(configured.unavailable_seconds, 600)
        self.assertEqual(configured.matchday.pre_match_minutes, 75)


if __name__ == "__main__":
    unittest.main()
