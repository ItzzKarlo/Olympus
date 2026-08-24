from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx

from olympus_core.config import FootballSettings, parse_core_config
from olympus_core.integrations.football import (
    ApiFootballProvider,
    FixtureFootballProvider,
    FootballDataProvider,
    create_football_provider,
)
from olympus_core.integrations.football.base import FootballProviderError, FootballRateLimitError
from olympus_core.integrations.football.collector import FootballCollector, MatchdayPolicy
from olympus_core.integrations.football.football_data import (
    normalize_football_data_events,
    normalize_football_data_match,
)
from olympus_core.models.football import FootballEventType, MatchPhase


NOW = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)
SETTINGS = FootballSettings(
    enabled=True,
    provider="football-data",
    team_id="5",
    timezone="Europe/Berlin",
    football_data_api_key="football-data-test-key",
)


def raw_match(
    status: str = "TIMED",
    *,
    kickoff: datetime | None = None,
    bayern_home: bool = True,
    score: tuple[int | None, int | None] = (None, None),
    include_optional: bool = False,
) -> dict[str, object]:
    bayern = {
        "id": 5,
        "name": "FC Bayern München",
        "shortName": "Bayern",
        "tla": "FCB",
    }
    opponent = {
        "id": 4,
        "name": "Borussia Dortmund",
        "shortName": "Dortmund",
        "tla": "BVB",
    }
    value: dict[str, object] = {
        "id": 550001,
        "utcDate": (kickoff or (NOW + timedelta(hours=2))).isoformat().replace("+00:00", "Z"),
        "status": status,
        "minute": 63 if status == "IN_PLAY" else 45 if status == "PAUSED" else None,
        "injuryTime": 2 if status == "IN_PLAY" else None,
        "venue": "Allianz Arena" if bayern_home else "Signal Iduna Park",
        "competition": {"id": 2002, "name": "Bundesliga", "code": "BL1"},
        "homeTeam": bayern if bayern_home else opponent,
        "awayTeam": opponent if bayern_home else bayern,
        "score": {
            "winner": None,
            "duration": "REGULAR",
            "fullTime": {"home": score[0], "away": score[1]},
            "halfTime": {"home": None, "away": None},
        },
    }
    if include_optional:
        home = value["homeTeam"]
        away = value["awayTeam"]
        assert isinstance(home, dict) and isinstance(away, dict)
        home.update({
            "formation": "4-2-3-1",
            "lineup": [{"id": 1, "name": "Manuel Neuer", "position": "Goalkeeper", "shirtNumber": 1}],
            "bench": [],
        })
        value.update({
            "goals": [{
                "minute": 17,
                "injuryTime": None,
                "type": "REGULAR",
                "team": bayern,
                "scorer": {"id": 2, "name": "Harry Kane"},
                "assist": {"id": 3, "name": "Jamal Musiala"},
                "score": {"home": 1 if bayern_home else 0, "away": 0 if bayern_home else 1},
            }],
            "bookings": [{
                "minute": 40,
                "team": opponent,
                "player": {"id": 10, "name": "Opponent Defender"},
                "card": "YELLOW",
            }],
            "substitutions": [],
        })
    return value


def provider_for(
    matches: list[object] | None = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[FootballDataProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status_code,
            headers=headers,
            json={"matches": matches if matches is not None else []},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FootballDataProvider(SETTINGS, client, clock=lambda: NOW), requests


class FootballDataNormalizationTests(unittest.TestCase):
    def test_home_away_status_score_clock_and_utc_kickoff(self) -> None:
        home = normalize_football_data_match(raw_match("IN_PLAY", score=(2, 1)), SETTINGS)
        away = normalize_football_data_match(
            raw_match("PAUSED", bayern_home=False, score=(1, 1)), SETTINGS
        )

        self.assertIsNotNone(home)
        self.assertEqual(home.home.id, "bayern")
        self.assertEqual(home.away.id, "football-data:4")
        self.assertEqual(home.status, MatchPhase.LIVE)
        self.assertEqual(home.score.model_dump(), {"home": 2, "away": 1})
        self.assertEqual(home.clock.minute, 63)
        self.assertEqual(home.clock.added_time, 2)
        self.assertEqual(home.kickoff.tzinfo, timezone.utc)
        self.assertEqual(away.away.id, "bayern")
        self.assertEqual(away.status, MatchPhase.HALF_TIME)

    def test_all_statuses_map_without_provider_values_leaking(self) -> None:
        expected = {
            "SCHEDULED": MatchPhase.UPCOMING,
            "TIMED": MatchPhase.UPCOMING,
            "IN_PLAY": MatchPhase.LIVE,
            "EXTRA_TIME": MatchPhase.LIVE,
            "PENALTY_SHOOTOUT": MatchPhase.LIVE,
            "PAUSED": MatchPhase.HALF_TIME,
            "FINISHED": MatchPhase.FINISHED,
            "AWARDED": MatchPhase.FINISHED,
            "SUSPENDED": MatchPhase.SUSPENDED,
            "POSTPONED": MatchPhase.POSTPONED,
            "CANCELLED": MatchPhase.CANCELLED,
            "unexpected": MatchPhase.UNKNOWN,
        }
        for status, phase in expected.items():
            with self.subTest(status=status):
                self.assertEqual(normalize_football_data_match(raw_match(status), SETTINGS).status, phase)

    def test_optional_events_and_lineups_are_honest_when_present_or_absent(self) -> None:
        value = raw_match("IN_PLAY", score=(1, 0), include_optional=True)
        match = normalize_football_data_match(value, SETTINGS)
        events = normalize_football_data_events(value, match, SETTINGS)

        self.assertEqual([event.type for event in events], [
            FootballEventType.GOAL,
            FootballEventType.YELLOW_CARD,
        ])
        self.assertTrue(events[0].for_tracked_team)
        self.assertEqual(events[0].score_after.model_dump(), {"home": 1, "away": 0})
        self.assertEqual(normalize_football_data_events({}, match, SETTINGS), [])


class FootballDataProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_upcoming_match_uses_team_endpoint_auth_and_provider_team_id(self) -> None:
        provider, requests = provider_for([raw_match()])
        snapshot = await provider.fetch()

        self.assertEqual(snapshot.next_match.id, "550001")
        self.assertEqual(snapshot.match.id, "550001")
        self.assertEqual(snapshot.tracked_team.id, "bayern")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/v4/teams/5/matches")
        self.assertEqual(requests[0].headers["X-Auth-Token"], "football-data-test-key")
        self.assertEqual(requests[0].url.params["dateFrom"], "2026-08-27")
        self.assertEqual(requests[0].url.params["dateTo"], "2026-11-27")

    async def test_live_halftime_finished_and_optional_data_normalize(self) -> None:
        cases = [
            ("IN_PLAY", MatchPhase.LIVE, NOW - timedelta(hours=1), (2, 1)),
            ("PAUSED", MatchPhase.HALF_TIME, NOW - timedelta(hours=1), (1, 1)),
            ("FINISHED", MatchPhase.FINISHED, NOW - timedelta(hours=2), (3, 1)),
        ]
        for status, phase, kickoff, score in cases:
            with self.subTest(status=status):
                provider, _ = provider_for([
                    raw_match(status, kickoff=kickoff, score=score, include_optional=True)
                ])
                snapshot = await provider.fetch()
                self.assertEqual(snapshot.match.status, phase)
                self.assertEqual(snapshot.match.score.home, score[0])
                self.assertEqual(len(snapshot.events), 2)
                self.assertIsNotNone(snapshot.lineups)
                self.assertIsNone(snapshot.statistics)
                self.assertEqual(snapshot.player_statistics, [])

    async def test_empty_response_is_valid_and_malformed_data_is_diagnostic(self) -> None:
        empty, _ = provider_for([])
        snapshot = await empty.fetch()
        self.assertIsNone(snapshot.next_match)
        self.assertIsNone(snapshot.match)
        self.assertEqual(snapshot.tracked_team.id, "bayern")

        malformed_payload = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"matches": "not-a-list"})
        ))
        provider = FootballDataProvider(SETTINGS, malformed_payload, clock=lambda: NOW)
        with self.assertRaisesRegex(FootballProviderError, "malformed matches response"):
            await provider.fetch()

        malformed_records, _ = provider_for([{"id": "missing-required-fields"}])
        with self.assertRaisesRegex(FootballProviderError, "malformed match records"):
            await malformed_records.fetch()

    async def test_auth_rate_limit_not_found_and_upstream_errors_are_explicit(self) -> None:
        cases = [
            (401, "rejected credentials"),
            (403, "subscription access"),
            (404, "team_id 5 was not found"),
            (500, "upstream error 500"),
        ]
        for status_code, message in cases:
            with self.subTest(status=status_code):
                provider, _ = provider_for(status_code=status_code)
                with self.assertRaisesRegex(FootballProviderError, message) as caught:
                    await provider.fetch()
                self.assertNotIn("football-data-test-key", str(caught.exception))

        limited, _ = provider_for(
            status_code=429,
            headers={"X-RequestCounter-Reset": "37"},
        )
        with self.assertRaises(FootballRateLimitError) as caught:
            await limited.fetch()
        self.assertEqual(caught.exception.retry_after, 37)

    async def test_quota_headers_and_matchday_modes_use_normalized_state(self) -> None:
        provider, _ = provider_for(
            [raw_match("TIMED", kickoff=NOW + timedelta(minutes=30))],
            headers={"X-RequestsAvailable": "2"},
        )
        snapshot = await provider.fetch()
        state = MatchdayPolicy(SETTINGS).state(snapshot, NOW)

        self.assertEqual(state.matchday.phase, MatchPhase.PRE_MATCH)
        self.assertEqual(snapshot.quota.minute_remaining, 2)
        self.assertTrue(snapshot.quota.low)

    async def test_provider_snapshots_drive_the_existing_matchday_lifecycle(self) -> None:
        cases = [
            ("TIMED", NOW + timedelta(minutes=30), MatchPhase.PRE_MATCH),
            ("IN_PLAY", NOW - timedelta(hours=1), MatchPhase.LIVE),
            ("PAUSED", NOW - timedelta(hours=1), MatchPhase.HALF_TIME),
            ("FINISHED", NOW - timedelta(hours=2), MatchPhase.POST_MATCH),
        ]
        for status, kickoff, expected in cases:
            with self.subTest(status=status):
                provider, _ = provider_for([
                    raw_match(status, kickoff=kickoff, score=(1, 0))
                ])
                snapshot = await provider.fetch()
                state = MatchdayPolicy(SETTINGS).state(snapshot, NOW)
                self.assertEqual(state.matchday.phase, expected)

    async def test_free_tier_provider_clamps_live_polling_to_one_minute(self) -> None:
        provider, _ = provider_for([
            raw_match("IN_PLAY", kickoff=NOW - timedelta(hours=1), score=(1, 0))
        ])
        snapshot = await provider.fetch()
        state = MatchdayPolicy(SETTINGS).state(snapshot, NOW)
        collector = FootballCollector(SETTINGS, provider, lambda value: None, lambda value: None)

        self.assertEqual(SETTINGS.poll_live_seconds, 15)
        self.assertEqual(collector.poll_interval(state, NOW), 60)

        finished_provider, _ = provider_for([
            raw_match("FINISHED", kickoff=NOW - timedelta(hours=2), score=(3, 1))
        ])
        finished_snapshot = await finished_provider.fetch()
        post_match = MatchdayPolicy(SETTINGS).state(finished_snapshot, NOW)
        finished_collector = FootballCollector(
            SETTINGS,
            finished_provider,
            lambda value: None,
            lambda value: None,
        )
        self.assertEqual(finished_collector.poll_interval(post_match, NOW), 300)


class FootballProviderConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_supported_providers_still_instantiate(self) -> None:
        api_provider = create_football_provider(replace(
            SETTINGS,
            provider="api-football",
            team_id="157",
            api_key="api-football-key",
        ))
        football_data_provider = create_football_provider(SETTINGS)
        fixture_provider = create_football_provider(replace(
            SETTINGS,
            provider="fixture",
            fixture_path="/tmp/olympus-football-fixture.json",
        ))
        self.assertIsInstance(api_provider, ApiFootballProvider)
        self.assertIsInstance(football_data_provider, FootballDataProvider)
        self.assertIsInstance(fixture_provider, FixtureFootballProvider)
        await api_provider.aclose()
        await football_data_provider.aclose()

    def test_config_accepts_dedicated_key_and_preserves_existing_providers(self) -> None:
        with patch.dict("os.environ", {"OLYMPUS_FOOTBALL_DATA_API_KEY": "fd-key"}, clear=True):
            football_data = parse_core_config({
                "football": {"enabled": True, "provider": "football-data", "team_id": "5"},
            }).football
        self.assertTrue(football_data.configured)
        self.assertEqual(football_data.football_data_api_key, "fd-key")
        self.assertIsNone(football_data.api_key)

        with patch.dict("os.environ", {"OLYMPUS_FOOTBALL_API_KEY": "af-key"}, clear=True):
            api_football = parse_core_config({
                "football": {"enabled": True, "provider": "api-football", "team_id": "157"},
            }).football
        self.assertTrue(api_football.configured)

        with patch.dict("os.environ", {"OLYMPUS_FOOTBALL_FIXTURE_PATH": "/tmp/fixture.json"}, clear=True):
            fixture = parse_core_config({
                "football": {"enabled": True, "provider": "fixture", "team_id": "157"},
            }).football
        self.assertTrue(fixture.configured)

    def test_missing_provider_key_and_unknown_provider_fail_clearly(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = parse_core_config({
                "football": {"enabled": True, "provider": "football-data", "team_id": "5"},
            }).football
        self.assertFalse(settings.configured)
        self.assertEqual(
            settings.configuration_issue,
            "football-data requires OLYMPUS_FOOTBALL_DATA_API_KEY",
        )

        with self.assertRaisesRegex(ValueError, "Unsupported football provider"):
            parse_core_config({"football": {"provider": "made-up"}})

    def test_api_football_optional_season_is_validated_and_sent(self) -> None:
        with patch.dict("os.environ", {"OLYMPUS_FOOTBALL_API_KEY": "af-key"}, clear=True):
            settings = parse_core_config({
                "football": {
                    "enabled": True,
                    "provider": "api-football",
                    "team_id": "157",
                    "season": 2025,
                },
            }).football
        self.assertEqual(settings.season, 2025)
        with self.assertRaisesRegex(ValueError, "four-digit starting year"):
            parse_core_config({"football": {"season": "2025"}})


if __name__ == "__main__":
    unittest.main()
