from datetime import datetime, timezone
from uuid import uuid4

from olympus_core.models.agent import AgentHello, RegisteredAgent
from olympus_core.models.telemetry import AgentTelemetry


class AgentRegistry:
    """In-memory record of agents and their most recent observations."""

    def __init__(self) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._connection_ids: dict[str, str] = {}

    def register(self, hello: AgentHello) -> tuple[RegisteredAgent, str]:
        now = datetime.now(timezone.utc)
        connection_id = uuid4().hex
        existing = self._agents.get(hello.agent_id)

        agent = RegisteredAgent(
            agent_id=hello.agent_id,
            hostname=hello.hostname,
            platform=hello.platform,
            platform_version=hello.platform_version,
            agent_version=hello.agent_version,
            online=True,
            connected_at=now,
            last_seen=now,
            system=existing.system if existing else None,
            storage=existing.storage if existing else None,
            network=existing.network if existing else None,
            temperatures=existing.temperatures if existing else None,
            gpu=existing.gpu if existing else None,
            activity=existing.activity if existing else None,
        )
        self._agents[hello.agent_id] = agent
        self._connection_ids[hello.agent_id] = connection_id
        return agent, connection_id

    def update(
        self,
        agent_id: str,
        telemetry: AgentTelemetry,
        connection_id: str | None = None,
    ) -> RegisteredAgent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        if connection_id is not None and self._connection_ids.get(agent_id) != connection_id:
            return agent

        agent.system = telemetry.system
        agent.storage = telemetry.storage
        agent.network = telemetry.network
        agent.temperatures = telemetry.temperatures
        agent.gpu = telemetry.gpu
        agent.activity = telemetry.activity
        agent.last_seen = datetime.now(timezone.utc)
        return agent

    def disconnect(self, agent_id: str, connection_id: str | None = None) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        if connection_id is not None and self._connection_ids.get(agent_id) != connection_id:
            return

        agent.online = False
        agent.last_seen = datetime.now(timezone.utc)
        self._connection_ids.pop(agent_id, None)

    def get(self, agent_id: str) -> RegisteredAgent | None:
        return self._agents.get(agent_id)

    def get_all(self) -> list[RegisteredAgent]:
        return list(self._agents.values())
