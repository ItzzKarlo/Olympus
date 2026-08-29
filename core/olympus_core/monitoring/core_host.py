import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import platform
import re
import shutil
import socket
import subprocess
import time
import logging

import psutil

from olympus_core.models.monitoring import CoreHostState
from olympus_core.models.telemetry import StorageTelemetry, SystemTelemetry
from olympus_core.services.monitoring_store import MonitoringStore


logger = logging.getLogger(__name__)


def _cpu_temperature() -> float | None:
    try:
        values = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for name in ("cpu_thermal", "coretemp", "k10temp"):
        entries = values.get(name, [])
        if entries:
            return float(entries[0].current)
    return None


def _pi_power_flags() -> tuple[bool | None, bool | None]:
    command = shutil.which("vcgencmd")
    if command is None:
        return None, None
    try:
        output = subprocess.run(
            [command, "get_throttled"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        ).stdout.strip()
        match = re.fullmatch(r"throttled=0x([0-9a-fA-F]+)", output)
        if match is None:
            return None, None
        flags = int(match.group(1), 16)
        return bool(flags & ((1 << 2) | (1 << 18))), bool(flags & ((1 << 0) | (1 << 16)))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None


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
        self._last_power_check = 0.0
        self._power_flags: tuple[bool | None, bool | None] = (None, None)

    def _cached_power_flags(self) -> tuple[bool | None, bool | None]:
        now = time.monotonic()
        if now - self._last_power_check >= 60:
            self._power_flags = _pi_power_flags()
            self._last_power_check = now
        return self._power_flags

    def collect_once(self) -> CoreHostState:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")
        try:
            load_1m, load_5m, _ = psutil.getloadavg()
        except (AttributeError, OSError):
            load_1m = load_5m = None
        throttled, undervoltage = self._cached_power_flags()
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
            load_average_1m=load_1m,
            load_average_5m=load_5m,
            swap_percent=swap.percent,
            cpu_temperature_celsius=_cpu_temperature(),
            throttled=throttled,
            undervoltage=undervoltage,
        )
        self._store.core_host = state
        return state

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                self.collect_once()
                await self._on_update()
            except Exception as error:
                logger.warning("Core host telemetry temporarily unavailable: %s", error)
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._poll_seconds)
            except TimeoutError:
                pass
