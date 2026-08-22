from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.state import MachineState, OlympusState
from olympus_core.models.telemetry import ActivityMode


class StateService:
    """Interprets agent observations into the state consumed by Olympus outputs."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def current(self) -> OlympusState:
        agents = self._registry.get_all()
        active_device = next(
            (
                agent.agent_id
                for agent in agents
                if agent.online
                and agent.activity is not None
                and agent.activity.mode == ActivityMode.DEVELOPMENT
            ),
            None,
        )

        return OlympusState(
            mode=(
                ActivityMode.DEVELOPMENT
                if active_device is not None
                else ActivityMode.IDLE
            ),
            active_device=active_device,
            machines={
                agent.agent_id: MachineState(
                    hostname=agent.hostname,
                    online=agent.online,
                    system=agent.system,
                    activity=agent.activity,
                )
                for agent in agents
            },
        )
