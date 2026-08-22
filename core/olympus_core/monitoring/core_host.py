import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import platform
import socket
import time

import psutil

from olympus_core.models.monitoring import CoreHostState
from olympus_core.models.telemetry import StorageTelemetry, SystemTelemetry
from olympus_core.services.monitoring_store import MonitoringStore


class CoreHostCollector:
    def __init__(
        self,
        store: MonitoringStore,
        poll_seconds: float,
        on_update: Callable[[], Awaitable[None]],
    ) -> None:
        self._store = store
        self._poll_seconds = poll_seconds
        self._on_update = on_update

    def collect_once(self) -> CoreHostState:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        state = CoreHostState(
            hostname=socket.gethostname(),
            platform=platform.system().lower(),
            observed_at=datetime.now(timezone.utc),
            system=SystemTelemetry(
                cpu_percent=psutil.cpu_percent(interval=None),
                ram_percent=memory.percent,
                ram_used_bytes=memory.used,
                ram_total_bytes=memory.total,
                uptime_seconds=max(0, time.time() - psutil.boot_time()),
            ),
            storage=StorageTelemetry(
                root_used_percent=disk.percent,
                root_free_bytes=disk.free,
                root_total_bytes=disk.total,
            ),
        )
        self._store.core_host = state
        return state

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self.collect_once()
            await self._on_update()
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._poll_seconds)
            except TimeoutError:
                pass
