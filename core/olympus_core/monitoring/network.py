import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol

import httpx

from olympus_core.models.monitoring import (
    EventSeverity,
    NetworkState,
    NetworkTargetState,
    ProbeState,
    ProbeStatus,
)
from olympus_core.monitoring.config import NetworkConfig
from olympus_core.monitoring.probes import ProbeResult, dns_probe, http_probe, tcp_probe
from olympus_core.monitoring.transitions import StatusTransition, TransitionTracker
from olympus_core.services.events import EventService
from olympus_core.services.monitoring_store import MonitoringStore


class NetworkProbeSet(Protocol):
    async def probe_all(self, config: NetworkConfig) -> dict[str, ProbeResult]: ...


class DefaultNetworkProbeSet:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def probe_all(self, config: NetworkConfig) -> dict[str, ProbeResult]:
        names = ["gateway", "internet", "dns", "https"] + [
            f"target:{target.id}" for target in config.targets
        ]
        checks = [
            tcp_probe(
                config.gateway,
                config.gateway_port,
                config.timeout_seconds,
                refused_is_reachable=True,
            ),
            tcp_probe(config.internet_host, config.internet_port, config.timeout_seconds),
            dns_probe(config.dns_hostname, config.timeout_seconds),
            http_probe(self._client, config.https_url, config.timeout_seconds + 1),
            *[
                tcp_probe(target.host, target.port, config.timeout_seconds)
                for target in config.targets
            ],
        ]
        return dict(zip(names, await asyncio.gather(*checks), strict=True))


class NetworkCollector:
    def __init__(
        self,
        config: NetworkConfig,
        store: MonitoringStore,
        events: EventService,
        probes: NetworkProbeSet,
        on_update: Callable[[], Awaitable[None]],
    ) -> None:
        self._config = config
        self._store = store
        self._events = events
        self._probes = probes
        self._on_update = on_update
        names = ["gateway", "internet", "dns", "https"] + [
            f"target:{target.id}" for target in config.targets
        ]
        self._trackers = {
            name: TransitionTracker(
                config.failure_threshold, config.recovery_threshold
            )
            for name in names
        }

    async def poll_once(self) -> NetworkState:
        observed_at = datetime.now(timezone.utc)
        results = await self._probes.probe_all(self._config)
        transitions: dict[str, StatusTransition] = {}
        states: dict[str, ProbeState] = {}
        for name, tracker in self._trackers.items():
            result = results.get(name, ProbeResult(False))
            transition = tracker.record(result.success)
            if transition is not None:
                transitions[name] = transition
            states[name] = ProbeState(
                status=tracker.status,
                latency_ms=result.latency_ms if result.success else None,
                last_checked=observed_at,
            )

        targets = {
            target.id: NetworkTargetState(
                id=target.id,
                name=target.name,
                **states[f"target:{target.id}"].model_dump(),
            )
            for target in self._config.targets
        }
        state = NetworkState(
            gateway=states["gateway"],
            dns=states["dns"],
            internet=states["internet"],
            https=states["https"],
            targets=targets,
        )
        self._store.network = state
        for name, transition in transitions.items():
            await self._handle_transition(name, transition, state)
        await self._on_update()
        return state

    async def _handle_transition(
        self,
        name: str,
        transition: StatusTransition,
        state: NetworkState,
    ) -> None:
        if transition.current == ProbeStatus.UP:
            if transition.previous == ProbeStatus.DOWN:
                title = self._title(name, recovered=True)
                await self._events.resolve_incident(
                    f"network:{name}",
                    event_type=self._event_type(name, restored=True),
                    title=title,
                    message=f"{title} and monitoring is stable again.",
                    source="network",
                    payload=self._diagnostics(state, name),
                )
            return

        if transition.current != ProbeStatus.DOWN:
            return
        target_config = next(
            (item for item in self._config.targets if name == f"target:{item.id}"),
            None,
        )
        if target_config is not None and not target_config.alert:
            return
        title = self._title(name, recovered=False)
        severity = EventSeverity.WARNING
        if (
            name == "gateway"
            and state.internet.status == ProbeStatus.DOWN
        ) or (
            name == "internet"
            and state.https.status == ProbeStatus.DOWN
        ):
            severity = EventSeverity.CRITICAL
        message = self._failure_message(name, state)
        await self._events.raise_incident(
            f"network:{name}",
            event_type=self._event_type(name, restored=False),
            severity=severity,
            title=title,
            message=message,
            source="network",
            payload=self._diagnostics(state, name),
        )

    def _title(self, name: str, recovered: bool) -> str:
        action = "reachable again" if recovered else "unreachable"
        if name.startswith("target:"):
            target_id = name.split(":", 1)[1]
            target = next(item for item in self._config.targets if item.id == target_id)
            return f"{target.name} {action}"
        labels = {
            "gateway": "Gateway",
            "internet": "Internet connection",
            "dns": "DNS resolution",
            "https": "External HTTPS",
        }
        if recovered:
            return f"{labels[name]} restored"
        return f"{labels[name]} unavailable"

    def _event_type(self, name: str, restored: bool) -> str:
        suffix = "restored" if restored else "down"
        return (
            f"network.target.{suffix}"
            if name.startswith("target:")
            else f"network.{name}.{suffix}"
        )

    def _failure_message(self, name: str, state: NetworkState) -> str:
        if name.startswith("target:"):
            if state.gateway.status == ProbeStatus.UP and state.internet.status == ProbeStatus.UP:
                return "LAN and Internet checks are healthy; this may be a remote-node or Meshnet issue."
            return "The configured remote target did not answer its reachability probe."
        if name == "gateway" and (
            state.internet.status == ProbeStatus.UP
            or state.https.status == ProbeStatus.UP
        ):
            return "The configured gateway endpoint did not answer, but external checks are healthy; the probe port may be blocked."
        if name == "internet" and state.https.status == ProbeStatus.UP:
            return "The external IP probe failed, but HTTPS still works; Internet connectivity is only partially degraded."
        messages = {
            "gateway": "The local gateway did not answer, so LAN routing may be unavailable.",
            "internet": "The external IP reachability check failed.",
            "dns": "The configured hostname could not be resolved.",
            "https": "External HTTPS failed while other network evidence is tracked separately.",
        }
        return messages[name]

    def _diagnostics(self, state: NetworkState, failed_probe: str) -> dict[str, object]:
        return {
            "failed_probe": failed_probe,
            "gateway": state.gateway.model_dump(mode="json"),
            "dns": state.dns.model_dump(mode="json"),
            "internet": state.internet.model_dump(mode="json"),
            "https": state.https.model_dump(mode="json"),
        }

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.poll_once()
            except Exception:
                # Individual probe failures are normalized; this protects the loop
                # from an unexpected collector-level parsing/configuration error.
                await self._on_update()
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._config.poll_seconds)
            except TimeoutError:
                pass
