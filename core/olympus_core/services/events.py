from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
import inspect
from typing import Any
from uuid import uuid4

from olympus_core.models.monitoring import (
    ActiveAlert,
    EventSeverity,
    OlympusEvent,
    RecoveryNotice,
)


EventListener = Callable[[OlympusEvent], Awaitable[None] | None]


class EventService:
    """Small in-memory incident/event service for alert overlays."""

    def __init__(self, recovery_seconds: float = 6.0) -> None:
        self._active: dict[str, ActiveAlert] = {}
        self._recoveries: list[RecoveryNotice] = []
        self._listeners: list[EventListener] = []
        self._recovery_seconds = recovery_seconds

    def subscribe(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    async def _emit(self, event: OlympusEvent) -> None:
        for listener in self._listeners:
            result = listener(event)
            if inspect.isawaitable(result):
                await result

    async def raise_incident(
        self,
        incident_key: str,
        *,
        event_type: str,
        severity: EventSeverity,
        title: str,
        message: str,
        source: str,
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> ActiveAlert:
        existing = self._active.get(incident_key)
        if existing is not None:
            return existing
        observed_at = timestamp or datetime.now(timezone.utc)
        alert = ActiveAlert(
            id=uuid4().hex,
            incident_key=incident_key,
            type=event_type,
            severity=severity,
            title=title,
            message=message,
            source=source,
            started_at=observed_at,
            payload=payload or {},
        )
        self._active[incident_key] = alert
        await self._emit(
            OlympusEvent(
                id=uuid4().hex,
                type=event_type,
                severity=severity,
                timestamp=observed_at,
                title=title,
                message=message,
                source=source,
                payload=payload or {},
            )
        )
        return alert

    async def resolve_incident(
        self,
        incident_key: str,
        *,
        event_type: str,
        title: str,
        message: str,
        source: str,
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> RecoveryNotice | None:
        alert = self._active.pop(incident_key, None)
        if alert is None:
            return None
        recovered_at = timestamp or datetime.now(timezone.utc)
        downtime = max(0.0, (recovered_at - alert.started_at).total_seconds())
        recovery = RecoveryNotice(
            id=uuid4().hex,
            incident_key=incident_key,
            type=event_type,
            title=title,
            message=message,
            source=source,
            recovered_at=recovered_at,
            downtime_seconds=downtime,
            expires_at=recovered_at + timedelta(seconds=self._recovery_seconds),
            payload=payload or alert.payload,
        )
        self._recoveries.append(recovery)
        await self._emit(
            OlympusEvent(
                id=uuid4().hex,
                type=event_type,
                severity=EventSeverity.INFO,
                timestamp=recovered_at,
                title=title,
                message=message,
                source=source,
                payload={
                    **(payload or alert.payload),
                    "downtime_seconds": downtime,
                },
            )
        )
        return recovery

    def active_alerts(self) -> list[ActiveAlert]:
        return sorted(
            self._active.values(),
            key=lambda alert: (
                {EventSeverity.CRITICAL: 0, EventSeverity.WARNING: 1, EventSeverity.INFO: 2}[alert.severity],
                alert.started_at,
            ),
        )

    def recoveries(self, now: datetime | None = None) -> list[RecoveryNotice]:
        current = now or datetime.now(timezone.utc)
        self._recoveries = [item for item in self._recoveries if item.expires_at > current]
        return list(self._recoveries)
