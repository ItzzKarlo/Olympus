import unittest

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.media import MediaState, MediaTrack
from olympus_core.models.telemetry import ActivityMode
from olympus_core.services.media import MediaStateStore
from olympus_core.services.state import StateService
from tests.test_registry import hello, telemetry


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

    def test_no_agents_and_no_spotify_is_idle(self) -> None:
        self.assertEqual(self.state.current().mode, ActivityMode.IDLE)

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


if __name__ == "__main__":
    unittest.main()
