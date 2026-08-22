import asyncio
from collections.abc import Awaitable, Callable
import logging

import httpx

from olympus_core.monitoring.config import MonitoringConfig
from olympus_core.monitoring.core_host import CoreHostCollector
from olympus_core.monitoring.network import DefaultNetworkProbeSet, NetworkCollector
from olympus_core.monitoring.services import DefaultServiceProbe, ServiceCollector
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore


logger = logging.getLogger(__name__)


class MonitoringRuntime:
    def __init__(
        self,
        config: MonitoringConfig,
        store: MonitoringStore,
        events: EventService,
        on_update: Callable[[], Awaitable[None]],
    ) -> None:
        self._config = config
        self._stop = asyncio.Event()
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Olympus-Core/0.4"},
        )
        self._collectors: list[object] = [
            CoreHostCollector(store, config.core_host_poll_seconds, on_update)
        ]
        if config.network.enabled:
            self._collectors.append(
                NetworkCollector(
                    config.network,
                    store,
                    events,
                    DefaultNetworkProbeSet(self._client),
                    on_update,
                )
            )
        if config.services:
            self._collectors.append(
                ServiceCollector(
                    config,
                    store,
                    events,
                    DefaultServiceProbe(self._client),
                    on_update,
                )
            )
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(
                collector.run(self._stop),
                name=f"monitoring-{collector.__class__.__name__.lower()}",
            )
            for collector in self._collectors
        ]
        logger.info("System monitoring started with %d collectors", len(self._tasks))

    async def stop(self) -> None:
        self._stop.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._client.aclose()
