from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, WebSocket

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import SpotifySettings, load_core_config
from olympus_core.display.hub import DisplayHub
from olympus_core.integrations.spotify import SpotifyApi, SpotifyCollector
from olympus_core.integrations.weather import OpenMeteoApi, WeatherCollector
from olympus_core.integrations.calendar import CalendarCollector, GoogleCalendarApi
from olympus_core.monitoring.config import load_monitoring_config
from olympus_core.monitoring.runtime import MonitoringRuntime
from olympus_core.models.agent import RegisteredAgent
from olympus_core.models.media import MediaState
from olympus_core.models.gameplay import GameplayEvent
from olympus_core.models.weather import WeatherState
from olympus_core.models.calendar import CalendarSnapshot
from olympus_core.models.state import OlympusState
from olympus_core.services.media import MediaStateStore
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore
from olympus_core.services.state import StateService
from olympus_core.services.gameplay import GameplayEventService
from olympus_core.services.ambient import CalendarStateStore, WeatherStateStore
from olympus_core.websocket.agents import handle_agent_socket
from olympus_core.websocket.display import handle_display_socket


logger = logging.getLogger(__name__)
registry = AgentRegistry()
core_settings = load_core_config()
media_store = MediaStateStore()
weather_store = WeatherStateStore()
calendar_store = CalendarStateStore(core_settings.timezone)
monitoring_store = MonitoringStore()
event_service = EventService()
state_service = StateService(
    registry,
    media_store,
    monitoring=monitoring_store,
    events=event_service,
    timezone=core_settings.timezone,
    weather=weather_store,
    calendar=calendar_store,
)
display_hub = DisplayHub()
gameplay_service = GameplayEventService()


async def publish_display_state() -> None:
    await display_hub.broadcast(state_service.display_state())


async def update_media_state(media: MediaState) -> None:
    media_store.update(media)
    await publish_display_state()


async def update_weather_state(weather: WeatherState) -> None:
    weather_store.update(weather)
    await publish_display_state()


async def update_calendar_state(calendar: CalendarSnapshot) -> None:
    calendar_store.update(calendar)
    await publish_display_state()


async def publish_ambient_time_progression() -> None:
    while True:
        await asyncio.sleep(60)
        if calendar_store.has_state:
            await publish_display_state()


async def publish_gameplay_event(event: GameplayEvent) -> None:
    await display_hub.broadcast_event(event)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    monitoring = MonitoringRuntime(
        load_monitoring_config(),
        monitoring_store,
        event_service,
        publish_display_state,
    )
    monitoring.start()
    settings = SpotifySettings.from_environment()
    collector: SpotifyCollector | None = None
    collector_task: asyncio.Task[None] | None = None
    if settings.enabled and settings.has_credentials:
        collector = SpotifyCollector(
            settings,
            SpotifyApi(settings),
            update_media_state,
        )
        collector_task = asyncio.create_task(
            collector.run(), name="spotify-collector"
        )
    elif settings.enabled:
        logger.warning(
            "Spotify collector disabled because credentials are incomplete"
        )
    else:
        logger.info("Spotify collector disabled")

    weather_collector: WeatherCollector | None = None
    weather_task: asyncio.Task[None] | None = None
    if core_settings.weather.configured:
        weather_collector = WeatherCollector(
            core_settings.weather,
            OpenMeteoApi(core_settings.weather),
            update_weather_state,
        )
        weather_task = asyncio.create_task(
            weather_collector.run(), name="weather-collector"
        )
    elif core_settings.weather.enabled:
        logger.warning("Weather collector disabled because coordinates are invalid or missing")
    else:
        logger.info("Weather collector disabled")

    calendar_collector: CalendarCollector | None = None
    calendar_task: asyncio.Task[None] | None = None
    ambient_tick_task: asyncio.Task[None] | None = None
    if core_settings.calendar.configured:
        calendar_collector = CalendarCollector(
            core_settings.calendar,
            GoogleCalendarApi(core_settings.calendar),
            update_calendar_state,
        )
        calendar_task = asyncio.create_task(
            calendar_collector.run(), name="calendar-collector"
        )
        ambient_tick_task = asyncio.create_task(
            publish_ambient_time_progression(), name="ambient-minute-tick"
        )
    elif core_settings.calendar.enabled:
        logger.warning("Calendar collector disabled because provider or credentials are incomplete")
    else:
        logger.info("Calendar collector disabled")

    try:
        yield
    finally:
        if collector is not None and collector_task is not None:
            collector.stop()
            await collector_task
        if weather_collector is not None and weather_task is not None:
            weather_collector.stop()
            await weather_task
        if calendar_collector is not None and calendar_task is not None:
            calendar_collector.stop()
            await calendar_task
        if ambient_tick_task is not None:
            ambient_tick_task.cancel()
            await asyncio.gather(ambient_tick_task, return_exceptions=True)
        await monitoring.stop()


app = FastAPI(
    title="Olympus Core",
    description="Core service for the Olympus home display system.",
    version="0.7.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "olympus-core",
        "version": "0.7.0",
    }


@app.get("/api/agents", response_model=list[RegisteredAgent])
async def agents() -> list[RegisteredAgent]:
    return registry.get_all()


@app.get("/api/state", response_model=OlympusState)
async def state() -> OlympusState:
    return state_service.current()


@app.websocket("/ws/agents")
async def agent_socket(websocket: WebSocket) -> None:
    await handle_agent_socket(
        websocket,
        registry,
        publish_display_state,
        publish_gameplay_event,
        gameplay_service,
    )


@app.websocket("/ws/display")
async def display_socket(websocket: WebSocket) -> None:
    await handle_display_socket(websocket, display_hub, state_service)
