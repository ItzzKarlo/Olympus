from dataclasses import dataclass

from olympus_core.models.agent import RegisteredAgent
from olympus_core.models.media import MediaState
from olympus_core.models.telemetry import ActivityMode
from olympus_core.models.football import MatchdayContext, MatchPhase
from olympus_core.models.news import NewsImportanceLevel, NewsState


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
        night_active: bool = False,
        matchday: MatchdayContext | None = None,
        news: NewsState | None = None,
    ) -> ModeResolution:
        if matchday is not None and matchday.active and matchday.phase in {
            MatchPhase.LIVE,
            MatchPhase.HALF_TIME,
            MatchPhase.SUSPENDED,
        }:
            return ModeResolution(ActivityMode.MATCHDAY)

        presentation = news.presentation if news is not None else None
        if (
            presentation is not None
            and news.active_story is not None
            and presentation.level == NewsImportanceLevel.MAJOR
        ):
            return ModeResolution(ActivityMode.NEWS)

        gaming_agents = [
            agent
            for agent in agents
            if agent.online
            and agent.activity is not None
            and agent.activity.mode == ActivityMode.GAMING
            and agent.activity.game is not None
        ]
        if gaming_agents:
            active = max(
                gaming_agents,
                key=lambda agent: (agent.last_seen, agent.agent_id),
            )
            return ModeResolution(ActivityMode.GAMING, active.agent_id)

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

        if matchday is not None and matchday.active and matchday.phase in {
            MatchPhase.PRE_MATCH,
            MatchPhase.POST_MATCH,
        }:
            return ModeResolution(ActivityMode.MATCHDAY)

        if (
            presentation is not None
            and news is not None
            and news.active_story is not None
            and presentation.level == NewsImportanceLevel.IMPORTANT
        ):
            return ModeResolution(ActivityMode.NEWS)

        if (
            media is not None
            and media.available
            and media.is_playing
            and media.track is not None
        ):
            return ModeResolution(ActivityMode.MEDIA)

        return ModeResolution(ActivityMode.NIGHT if night_active else ActivityMode.IDLE)
