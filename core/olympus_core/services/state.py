from datetime import datetime, timezone

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.state import DisplayState, MachineState, OlympusState
from olympus_core.services.media import MediaStateStore
from olympus_core.services.mode_resolver import ModeResolver


class StateService:
    """Interprets agent observations into the state consumed by Olympus outputs."""

    def __init__(
        self,
        registry: AgentRegistry,
        media: MediaStateStore | None = None,
        resolver: ModeResolver | None = None,
    ) -> None:
        self._registry = registry
        self._media = media or MediaStateStore()
        self._resolver = resolver or ModeResolver()

    def current(self) -> OlympusState:
        agents = self._registry.get_all()
        media = self._media.get()
        resolution = self._resolver.resolve(agents, media)

        return OlympusState(
            mode=resolution.mode,
            active_device=resolution.active_device,
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
        )

    def display_state(self) -> DisplayState:
        state = self.current()
        return DisplayState(
            **state.model_dump(),
            generated_at=datetime.now(timezone.utc),
        )
