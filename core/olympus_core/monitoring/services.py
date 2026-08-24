import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol
import logging
import time

import httpx

from olympus_core.models.monitoring import EventSeverity, ProbeStatus, ServiceState
from olympus_core.monitoring.config import MonitoringConfig, ServiceConfig
from olympus_core.monitoring.probes import ProbeResult, http_probe, tcp_probe
from olympus_core.monitoring.transitions import TransitionTracker
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore


logger = logging.getLogger(__name__)


class ServiceProbe(Protocol):
    async def probe(self, service: ServiceConfig, timeout: float) -> ProbeResult: ...


class DefaultServiceProbe:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def probe(self, service: ServiceConfig, timeout: float) -> ProbeResult:
        if service.type in {"http", "https"} and service.url:
            return await http_probe(self._client, service.url, timeout)
        if service.type == "tcp" and service.host and service.port:
            return await tcp_probe(service.host, service.port, timeout)
        return ProbeResult(False)


class ServiceCollector:
    def __init__(
        self,
        config: MonitoringConfig,
        store: MonitoringStore,
        events: EventService,
        probe: ServiceProbe,
        on_update: Callable[[], Awaitable[None]],
    ) -> None:
        self._config = config
        self._store = store
        self._events = events
        self._probe = probe
        self._on_update = on_update
        self._last_error_log_at = 0.0
        self._trackers = {
            service.id: TransitionTracker(
                config.service_failure_threshold,
                config.service_recovery_threshold,
            )
            for service in config.services
        }

    async def poll_once(self) -> dict[str, ServiceState]:
        observed_at = datetime.now(timezone.utc)
        results = await asyncio.gather(
            *[
                self._probe.probe(service, self._config.service_timeout_seconds)
                for service in self._config.services
            ]
        )
        for service, result in zip(self._config.services, results, strict=True):
            tracker = self._trackers[service.id]
            transition = tracker.record(result.success)
            previous = self._store.services.get(service.id)
            last_changed = (
                observed_at
                if transition is not None
                else previous.last_changed if previous else None
            )
            self._store.services[service.id] = ServiceState(
                id=service.id,
                name=service.name,
                status=tracker.status,
                latency_ms=result.latency_ms if result.success else None,
                last_checked=observed_at,
                last_changed=last_changed,
            )
            if transition is None:
                continue
            if transition.current == ProbeStatus.DOWN:
                severity = (
                    EventSeverity.CRITICAL
                    if service.severity == "critical"
                    else EventSeverity.WARNING
                )
                await self._events.raise_incident(
                    f"service:{service.id}",
                    event_type="service.down",
                    severity=severity,
                    title=f"{service.name} is down",
                    message="Repeated health checks failed for this configured service.",
                    source=service.id,
                    payload={"service_id": service.id, "service_name": service.name},
                )
            elif transition.current == ProbeStatus.UP:
                await self._events.resolve_incident(
                    f"service:{service.id}",
                    event_type="service.restored",
                    title=f"{service.name} restored",
                    message="The service is responding consistently again.",
                    source=service.id,
                    payload={"service_id": service.id, "service_name": service.name},
                )
        await self._on_update()
        return dict(self._store.services)

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.poll_once()
            except Exception as error:
                if time.monotonic() - self._last_error_log_at >= 60:
                    logger.warning("Service collector temporarily unavailable: %s", error)
                    self._last_error_log_at = time.monotonic()
                await self._on_update()
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=self._config.service_poll_seconds
                )
            except TimeoutError:
                pass
