from fastapi import FastAPI, WebSocket

from olympus_core.agents.registry import AgentRegistry
from olympus_core.models.agent import RegisteredAgent
from olympus_core.models.state import OlympusState
from olympus_core.services.state import StateService
from olympus_core.websocket.agents import handle_agent_socket


app = FastAPI(
    title="Olympus Core",
    description="Core service for the Olympus home display system.",
    version="0.1.0",
)
registry = AgentRegistry()
state_service = StateService(registry)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "olympus-core",
        "version": "0.1.0",
    }


@app.get("/api/agents", response_model=list[RegisteredAgent])
async def agents() -> list[RegisteredAgent]:
    return registry.get_all()


@app.get("/api/state", response_model=OlympusState)
async def state() -> OlympusState:
    return state_service.current()


@app.websocket("/ws/agents")
async def agent_socket(websocket: WebSocket) -> None:
    await handle_agent_socket(websocket, registry)
