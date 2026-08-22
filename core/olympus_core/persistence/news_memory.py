from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from olympus_core.persistence.database import Database


@dataclass(frozen=True, slots=True)
class NewsPresentationMemory:
    fingerprint: str
    highest_level: str
    last_presented_at: datetime


class NewsMemoryRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def load(self, retention_days: int, now: datetime | None = None) -> dict[str, NewsPresentationMemory]:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM news_presentation_memory WHERE last_presented_at >= ?",
                (cutoff.isoformat(),),
            ).fetchall()
        return {
            row["fingerprint"]: NewsPresentationMemory(
                row["fingerprint"],
                row["highest_level"],
                datetime.fromisoformat(row["last_presented_at"]),
            )
            for row in rows
        }

    def record(self, fingerprint: str, level: str, presented_at: datetime) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO news_presentation_memory(fingerprint, highest_level, last_presented_at) "
                "VALUES (?, ?, ?) ON CONFLICT(fingerprint) DO UPDATE SET "
                "highest_level = excluded.highest_level, last_presented_at = excluded.last_presented_at",
                (fingerprint, level, presented_at.isoformat()),
            )
            connection.commit()

    def cleanup(self, retention_days: int, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
        with self._database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM news_presentation_memory WHERE last_presented_at < ?",
                (cutoff.isoformat(),),
            )
            connection.commit()
        return cursor.rowcount
