from collections.abc import Sequence
from datetime import datetime, timezone
import sqlite3


MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, (
        """CREATE TABLE trusted_devices (
            agent_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            public_key TEXT NOT NULL,
            public_key_fingerprint TEXT NOT NULL,
            enrolled_at TEXT NOT NULL,
            last_authenticated_at TEXT,
            last_seen_at TEXT,
            revoked_at TEXT
        )""",
        "CREATE UNIQUE INDEX idx_trusted_devices_fingerprint ON trusted_devices(public_key_fingerprint)",
        """CREATE TABLE enrollment_tokens (
            id INTEGER PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            label TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT
        )""",
        "CREATE INDEX idx_enrollment_tokens_expiry ON enrollment_tokens(expires_at) WHERE used_at IS NULL",
        """CREATE TABLE incidents (
            id TEXT PRIMARY KEY,
            incident_key TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            recovered_at TEXT,
            duration_seconds REAL,
            resolution TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )""",
        "CREATE UNIQUE INDEX idx_incidents_active_key ON incidents(incident_key) WHERE recovered_at IS NULL",
        "CREATE INDEX idx_incidents_started_at ON incidents(started_at)",
        """CREATE TABLE news_presentation_memory (
            fingerprint TEXT PRIMARY KEY,
            highest_level TEXT NOT NULL,
            last_presented_at TEXT NOT NULL
        )""",
        "CREATE INDEX idx_news_memory_presented_at ON news_presentation_memory(last_presented_at)",
    )),
)


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[tuple[int, Sequence[str]]] = MIGRATIONS,
) -> int:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        applied = {int(row[0]) for row in rows}
        known = {version for version, _ in migrations}
        unknown = applied - known
        if unknown:
            raise RuntimeError(f"Database schema is newer than this Core: {sorted(unknown)}")
        for version, statements in migrations:
            if version in applied:
                continue
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return max(known, default=0)
