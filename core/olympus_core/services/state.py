from datetime import datetime, timezone

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.state import DisplayState, MachineState, OlympusState
from olympus_core.services.media import MediaStateStore
from olympus_core.services.events import EventService
from olympus_core.services.gaming import GamingSessionService
from olympus_core.services.mode_resolver import ModeResolver
from olympus_core.services.monitoring_store import MonitoringStore
from olympus_core.services.ambient import WeatherStateStore


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
        timezone: str = "UTC",
        weather: WeatherStateStore | None = None,
    ) -> None:
        self._registry = registry
        self._media = media or MediaStateStore()
        self._resolver = resolver or ModeResolver()
        self._monitoring = monitoring or MonitoringStore()
        self._events = events or EventService()
        self._gaming = gaming or GamingSessionService()
        self._timezone = timezone
        self._weather = weather or WeatherStateStore()

    def current(self) -> OlympusState:
        agents = self._registry.get_all()
        media = self._media.get()
        resolution = self._resolver.resolve(agents, media)
        gaming = self._gaming.update(resolution, agents)

        return OlympusState(
            mode=resolution.mode,
            active_device=resolution.active_device,
            timezone=self._timezone,
            weather=self._weather.get(),
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
            generated_at=datetime.now(timezone.utc),
        )
