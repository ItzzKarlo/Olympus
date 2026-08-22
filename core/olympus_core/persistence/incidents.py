from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

from olympus_core.models.monitoring import ActiveAlert, EventSeverity
from olympus_core.persistence.database import Database


logger = logging.getLogger(__name__)
MAX_METADATA_BYTES = 8_192


def _metadata(value: dict[str, Any]) -> str:
    try:
        serialized = json.dumps(value, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "{}"
    if len(serialized.encode("utf-8")) > MAX_METADATA_BYTES:
        return '{"summary":"metadata omitted because it exceeded the persistence limit"}'
    return serialized


@dataclass(frozen=True, slots=True)
class DurableIncident:
    alert: ActiveAlert
    recovered_at: datetime | None = None
    duration_seconds: float | None = None
    resolution: str | None = None


class IncidentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def active(self) -> list[ActiveAlert]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM incidents WHERE recovered_at IS NULL ORDER BY started_at"
            ).fetchall()
        return [ActiveAlert(
            id=row["id"],
            incident_key=row["incident_key"],
            type=row["event_type"],
            severity=EventSeverity(row["severity"]),
            title=row["title"],
            message=row["message"],
            source=row["source"],
            started_at=datetime.fromisoformat(row["started_at"]),
            payload=json.loads(row["metadata_json"]),
        ) for row in rows]

    def open(self, alert: ActiveAlert) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO incidents(" 
                "id, incident_key, event_type, severity, title, message, source, started_at, metadata_json" 
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    alert.id, alert.incident_key, alert.type, alert.severity.value,
                    alert.title, alert.message, alert.source, alert.started_at.isoformat(),
                    _metadata(alert.payload),
                ),
            )
            connection.commit()

    def resolve(
        self,
        incident_key: str,
        recovered_at: datetime,
        duration_seconds: float,
        metadata: dict[str, Any],
        resolution: str = "recovered",
    ) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute(
                "UPDATE incidents SET recovered_at = ?, duration_seconds = ?, "
                "resolution = ?, metadata_json = ? "
                "WHERE incident_key = ? AND recovered_at IS NULL",
                (
                    recovered_at.isoformat(), duration_seconds, resolution,
                    _metadata(metadata), incident_key,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def resolve_orphans(self, active_keys: set[str], when: datetime | None = None) -> int:
        observed_at = when or datetime.now(timezone.utc)
        resolved = 0
        for alert in self.active():
            if alert.incident_key in active_keys:
                continue
            duration = max(0.0, (observed_at - alert.started_at).total_seconds())
            resolved += int(self.resolve(
                alert.incident_key,
                observed_at,
                duration,
                alert.payload,
                "monitor_removed",
            ))
        return resolved

    def cleanup(self, retention_days: int, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM incidents WHERE recovered_at IS NOT NULL AND recovered_at < ?",
                (cutoff.isoformat(),),
            )
            connection.commit()
        return cursor.rowcount
