from datetime import datetime, timezone as datetime_timezone
from collections.abc import Callable

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.state import DisplayState, MachineState, OlympusState
from olympus_core.services.media import MediaStateStore
from olympus_core.services.events import EventService
from olympus_core.services.gaming import GamingSessionService
from olympus_core.services.mode_resolver import ModeResolver
from olympus_core.services.monitoring_store import MonitoringStore
from olympus_core.services.ambient import CalendarStateStore, WeatherStateStore
from olympus_core.services.time_policy import TimePolicyService
from olympus_core.services.football import FootballStateStore
from olympus_core.config import NightSettings


class StateService:
    """Interprets agent observations into the state consumed by Olympus outputs."""

    def __init__(
        self,
        registry: AgentRegistry,
        media: MediaStateStore | None = None,
        resolver: ModeResolver | None = None,
        monitoring: MonitoringStore | None = None,
        events: EventService | None = None,
        gaming: GamingSessionService | None = None,
        timezone: str = "Europe/Berlin",
        weather: WeatherStateStore | None = None,
        calendar: CalendarStateStore | None = None,
        time_policy: TimePolicyService | None = None,
        clock: Callable[[], datetime] | None = None,
        football: FootballStateStore | None = None,
    ) -> None:
        self._registry = registry
        self._media = media or MediaStateStore()
        self._resolver = resolver or ModeResolver()
        self._monitoring = monitoring or MonitoringStore()
        self._events = events or EventService()
        self._gaming = gaming or GamingSessionService()
        self._timezone = timezone
        self._weather = weather or WeatherStateStore()
        self._calendar = calendar or CalendarStateStore(timezone)
        self._time_policy = time_policy or TimePolicyService(NightSettings(enabled=False), timezone)
        self._clock = clock or (lambda: datetime.now(datetime_timezone.utc))
        self._football = football or FootballStateStore()

    def current(self) -> OlympusState:
        agents = self._registry.get_all()
        now = self._clock()
        media = self._media.get()
        time_policy = self._time_policy.evaluate(now)
        football = self._football.get()
        resolution = self._resolver.resolve(
            agents,
            media,
            time_policy.is_night,
            football.matchday if football else None,
        )
        gaming = self._gaming.update(resolution, agents)

        return OlympusState(
            mode=resolution.mode,
            active_device=resolution.active_device,
            timezone=self._timezone,
            weather=self._weather.get(),
            calendar=self._calendar.get(now),
            time_policy=time_policy,
            football=football,
            machines={
                agent.agent_id: MachineState(
                    agent_id=agent.agent_id,
                    hostname=agent.hostname,
                    platform=agent.platform,
                    platform_version=agent.platform_version,
                    online=agent.online,
                    last_seen=agent.last_seen,
                    system=agent.system,
                    storage=agent.storage,
                    network=agent.network,
                    temperatures=agent.temperatures,
                    gpu=agent.gpu,
                    activity=agent.activity,
                )
                for agent in agents
            },
            media=media,
            core_host=self._monitoring.core_host,
            network=self._monitoring.network,
            services=dict(self._monitoring.services),
            alerts=self._events.active_alerts(),
            recoveries=self._events.recoveries(),
            gaming=gaming,
        )

    def display_state(self) -> DisplayState:
        state = self.current()
        return DisplayState(
            **state.model_dump(),
            generated_at=datetime.now(datetime_timezone.utc),
        )
