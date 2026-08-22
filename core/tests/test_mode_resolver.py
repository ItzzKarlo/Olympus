import unittest
from datetime import datetime, timezone

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import NightSettings
from olympus_core.models.media import MediaState, MediaTrack
from olympus_core.models.football import (
    FootballCompetition,
    FootballMatch,
    FootballScore,
    FootballTeam,
    MatchdayContext,
    MatchPhase,
)
from olympus_core.models.telemetry import ActivityMode
from olympus_core.models.news import (
    NewsCluster, NewsImportance, NewsImportanceLevel, NewsPresentation, NewsState, NewsTopic,
)
from olympus_core.services.media import MediaStateStore
from olympus_core.services.state import StateService
from olympus_core.services.time_policy import TimePolicyService
from tests.test_registry import gaming_telemetry, hello, telemetry


def playback(is_playing: bool = True) -> MediaState:
    return MediaState(
        is_playing=is_playing,
        progress_ms=12_000,
        track=MediaTrack(title="Olympus", duration_ms=180_000),
    )


def matchday(phase: MatchPhase) -> MatchdayContext:
    bayern = FootballTeam(id="bayern", name="FC Bayern München", short_name="Bayern", code="FCB")
    opponent = FootballTeam(id="opponent", name="Opponent", short_name="Opponent")
    return MatchdayContext(
        active=True,
        phase=phase,
        tracked_team=bayern,
        match=FootballMatch(
            id="fixture",
            competition=FootballCompetition(id="bundesliga", name="Bundesliga"),
            kickoff=datetime(2026, 8, 29, 18, 30, tzinfo=timezone.utc),
            home=bayern,
            away=opponent,
            status=phase,
            score=FootballScore(home=0, away=0),
        ),
        observed_at=datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc),
    )


def news(level: NewsImportanceLevel) -> NewsState:
    now = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)
    story = NewsCluster(
        id="story", headline="A developing story", language="en", topic=NewsTopic.WORLD,
        articles=[], sources=[], first_seen_at=now, latest_seen_at=now,
        importance=NewsImportance(score=0.9, level=level),
    )
    return NewsState(
        active_story=story,
        presentation=NewsPresentation(
            story_id=story.id, level=level, started_at=now, ends_at=now.replace(hour=19),
        ),
    )


class ModeResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.media = MediaStateStore()
        self.state = StateService(self.registry, self.media)

    def night_state(self) -> StateService:
        return StateService(
            self.registry,
            self.media,
            timezone="Europe/Zagreb",
            time_policy=TimePolicyService(NightSettings(), "Europe/Zagreb"),
            clock=lambda: datetime(2026, 8, 20, 22, 30, tzinfo=timezone.utc),
        )

    def test_no_agents_and_no_spotify_is_idle(self) -> None:
        self.assertEqual(self.state.current().mode, ActivityMode.IDLE)

    def test_night_is_the_fallback_when_the_room_is_inactive(self) -> None:
        state = self.night_state().current()

        self.assertEqual(state.mode, ActivityMode.NIGHT)
        self.assertTrue(state.time_policy.is_night)

    def test_live_matchday_overrides_gaming_development_and_media(self) -> None:
        self.media.update(playback())
        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())

        resolution = self.state._resolver.resolve(
            self.registry.get_all(), self.media.get(), False, matchday(MatchPhase.LIVE)
        )
        self.assertEqual(resolution.mode, ActivityMode.MATCHDAY)

    def test_live_matchday_protects_against_major_news(self) -> None:
        resolution = self.state._resolver.resolve(
            [], None, False, matchday(MatchPhase.LIVE), news(NewsImportanceLevel.MAJOR)
        )
        self.assertEqual(resolution.mode, ActivityMode.MATCHDAY)

    def test_major_news_overrides_gaming_and_development(self) -> None:
        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())
        resolution = self.state._resolver.resolve(
            self.registry.get_all(), None, False, None, news(NewsImportanceLevel.MAJOR)
        )
        self.assertEqual(resolution.mode, ActivityMode.NEWS)

    def test_important_news_beats_media_and_fallback_but_not_active_work(self) -> None:
        important = news(NewsImportanceLevel.IMPORTANT)
        self.media.update(playback())
        self.assertEqual(self.state._resolver.resolve([], self.media.get(), False, None, important).mode, ActivityMode.NEWS)
        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        self.assertEqual(
            self.state._resolver.resolve(self.registry.get_all(), self.media.get(), False, None, important).mode,
            ActivityMode.DEVELOPMENT,
        )

    def test_pre_match_remains_above_important_news(self) -> None:
        resolution = self.state._resolver.resolve(
            [], None, False, matchday(MatchPhase.PRE_MATCH), news(NewsImportanceLevel.IMPORTANT)
        )
        self.assertEqual(resolution.mode, ActivityMode.MATCHDAY)

    def test_pre_match_yields_to_gaming_and_development_but_beats_media(self) -> None:
        self.media.update(playback())
        prematch = matchday(MatchPhase.PRE_MATCH)
        media_resolution = self.state._resolver.resolve([], self.media.get(), False, prematch)
        self.assertEqual(media_resolution.mode, ActivityMode.MATCHDAY)

        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        development = self.state._resolver.resolve(self.registry.get_all(), self.media.get(), False, prematch)
        self.assertEqual(development.mode, ActivityMode.DEVELOPMENT)

        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())
        gaming = self.state._resolver.resolve(self.registry.get_all(), self.media.get(), False, prematch)
        self.assertEqual(gaming.mode, ActivityMode.GAMING)

    def test_post_match_beats_idle_and_media_then_normal_fallback_resumes(self) -> None:
        self.media.update(playback())
        post = self.state._resolver.resolve([], self.media.get(), True, matchday(MatchPhase.POST_MATCH))
        self.assertEqual(post.mode, ActivityMode.MATCHDAY)
        normal = self.state._resolver.resolve([], self.media.get(), True, None)
        self.assertEqual(normal.mode, ActivityMode.MEDIA)

    def test_media_overrides_night(self) -> None:
        self.media.update(playback())
        self.assertEqual(self.night_state().current().mode, ActivityMode.MEDIA)

    def test_development_overrides_night(self) -> None:
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.assertEqual(self.night_state().current().mode, ActivityMode.DEVELOPMENT)

    def test_gaming_overrides_night(self) -> None:
        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())
        self.assertEqual(self.night_state().current().mode, ActivityMode.GAMING)

    def test_playing_media_selects_media(self) -> None:
        self.media.update(playback())
        self.assertEqual(self.state.current().mode, ActivityMode.MEDIA)

    def test_development_overrides_playing_media(self) -> None:
        self.media.update(playback())
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.assertEqual(self.state.current().mode, ActivityMode.DEVELOPMENT)

    def test_closing_development_returns_to_media(self) -> None:
        self.media.update(playback())
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.registry.update("mac-test", telemetry("idle"))
        self.assertEqual(self.state.current().mode, ActivityMode.MEDIA)

    def test_paused_media_is_idle(self) -> None:
        self.media.update(playback(False))
        self.assertEqual(self.state.current().mode, ActivityMode.IDLE)

    def test_offline_development_agent_does_not_override_media(self) -> None:
        self.media.update(playback())
        self.registry.register(hello())
        self.registry.update("mac-test", telemetry("development"))
        self.registry.disconnect("mac-test")
        self.assertEqual(self.state.current().mode, ActivityMode.MEDIA)

    def test_gaming_overrides_development_and_media(self) -> None:
        self.media.update(playback())
        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())

        state = self.state.current()
        self.assertEqual(state.mode, ActivityMode.GAMING)
        self.assertEqual(state.active_device, "win-test")
        self.assertEqual(state.gaming.game.id, "fortnite")

    def test_game_closes_to_development_then_media_then_idle(self) -> None:
        self.media.update(playback())
        self.registry.register(hello("dev-test"))
        self.registry.update("dev-test", telemetry("development"))
        self.registry.register(hello("win-test"))
        self.registry.update("win-test", gaming_telemetry())
        self.registry.update("win-test", telemetry("idle"))
        self.assertEqual(self.state.current().mode, ActivityMode.DEVELOPMENT)

        self.registry.update("dev-test", telemetry("idle"))
        self.assertEqual(self.state.current().mode, ActivityMode.MEDIA)

        self.media.update(playback(False))
        self.assertEqual(self.state.current().mode, ActivityMode.IDLE)


if __name__ == "__main__":
    unittest.main()
