from dataclasses import dataclass

from olympus_core.models.agent import RegisteredAgent
from olympus_core.models.media import MediaState
from olympus_core.models.telemetry import ActivityMode


@dataclass(frozen=True, slots=True)
class ModeResolution:
    mode: ActivityMode
    active_device: str | None = None


class ModeResolver:
    """Applies the small, explicit Olympus scene priority list."""

    def resolve(
        self,
        agents: list[RegisteredAgent],
        media: MediaState | None,
    ) -> ModeResolution:
        development_agent = next(
            (
                agent
                for agent in agents
                if agent.online
                and agent.activity is not None
                and agent.activity.mode == ActivityMode.DEVELOPMENT
            ),
            None,
        )
        if development_agent is not None:
            return ModeResolution(
                ActivityMode.DEVELOPMENT, development_agent.agent_id
            )

        if (
            media is not None
            and media.available
            and media.is_playing
            and media.track is not None
        ):
            return ModeResolution(ActivityMode.MEDIA)

        return ModeResolution(ActivityMode.IDLE)
