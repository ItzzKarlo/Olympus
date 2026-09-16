from datetime import datetime, timedelta, timezone
from dataclasses import replace
import unittest
import httpx
from test_football import SETTINGS, raw_fixture, snapshot, DummyProvider
from olympus_core.integrations.football.api_football import ApiFootballProvider
from olympus_core.integrations.football.collector import FootballCollector, MatchdayPolicy
from olympus_core.integrations.football.normalization import normalize_fixture, normalize_event_type
from olympus_core.integrations.football.base import FootballProviderError, FootballRateLimitError
from olympus_core.models.football import FootballScore, FootballEventType

NOW = datetime(2026, 8, 29, 18, tzinfo=timezone.utc)

class FootballReliability(unittest.IsolatedAsyncioTestCase):
    async def test_old_configured_season_rejected_without_network(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: self.fail('obsolete season requested'))) as client:
            provider = ApiFootballProvider(replace(SETTINGS, season=2023), client, clock=lambda: NOW)
            with self.assertRaises(FootballProviderError) as caught:
                await provider.fetch()
            self.assertEqual(caught.exception.code, 'unsupported_season')

    async def test_quota_without_last_good_is_visible_and_respected(self):
        collector = FootballCollector(SETTINGS, DummyProvider([FootballRateLimitError('quota', 1000)]), lambda s: None, lambda e: None)
        state = await collector.poll_once(now=NOW, monotonic_now=0)
        self.assertFalse(state.available)
        self.assertEqual(state.provider_status, 'quota_exhausted')
        self.assertGreaterEqual(collector.poll_interval(state), 1000)

    async def test_recovery_baselines_events_and_expired_context_returns_to_normal(self):
        events = []
        collector = FootballCollector(SETTINGS, DummyProvider([
            snapshot('2H', NOW), TimeoutError(), snapshot('2H', NOW, include_card=True), TimeoutError()
        ]), lambda s: None, events.append)
        await collector.poll_once(now=NOW, monotonic_now=0)
        await collector.poll_once(now=NOW, monotonic_now=70)
        await collector.poll_once(now=NOW, monotonic_now=100)
        self.assertEqual(events, [])
        expired = await collector.poll_once(now=NOW, monotonic_now=1100)
        self.assertIsNone(expired.matchday)
        self.assertFalse(expired.available)

    async def test_score_correction_not_goal_replay(self):
        first = snapshot('2H', NOW)
        corrected = first.model_copy(deep=True)
        corrected.match.score = FootballScore(home=1, away=0)
        corrected.events[0].id = 'corrected-goal-metadata'
        events = []
        collector = FootballCollector(SETTINGS, DummyProvider([first, corrected, corrected]), lambda s: None, events.append)
        for tick in (0,15,30):
            await collector.poll_once(now=NOW, monotonic_now=tick)
        self.assertEqual([e.type for e in events], ['football.score.corrected'])

    def test_wrong_team_and_obsolete_live_record(self):
        raw = raw_fixture()
        raw['teams']['home']['id'] = 123
        self.assertIsNone(normalize_fixture(raw, SETTINGS))
        old = snapshot('2H', NOW)
        old.match.kickoff = NOW - timedelta(days=365)
        self.assertIsNone(MatchdayPolicy(SETTINGS).state(old, NOW).matchday)
        self.assertEqual(normalize_event_type('Goal','Disallowed Goal'), FootballEventType.VAR)
