import unittest
from datetime import datetime, timezone

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import NightSettings
from olympus_core.models.media import MediaState, MediaTrack
from olympus_core.models.telemetry import ActivityMode
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
