from datetime import datetime, timedelta, timezone
from contextlib import closing
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote


def create_backup(
    database_path: Path,
    destination: Path,
    *,
    now: datetime | None = None,
) -> Path:
    source_path = database_path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Olympus database does not exist: {source_path}")
    destination = destination.expanduser().resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        destination.chmod(0o700)
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    target = destination / observed_at.strftime("core-%Y%m%d-%H%M%S.db")
    suffix = 1
    while target.exists():
        target = destination / (
            observed_at.strftime("core-%Y%m%d-%H%M%S") + f"-{suffix}.db"
        )
        suffix += 1
    temporary = target.with_suffix(".db.tmp")
    temporary_sidecars = (
        Path(f"{temporary}-wal"),
        Path(f"{temporary}-shm"),
    )
    source_uri = f"file:{quote(source_path.as_posix())}?mode=ro"
    try:
        with closing(sqlite3.connect(source_uri, uri=True, timeout=10)) as source:
            with closing(sqlite3.connect(temporary)) as backup:
                source.backup(backup)
                integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise sqlite3.DatabaseError(
                        f"SQLite backup integrity check failed: {integrity}"
                    )
                backup.execute("PRAGMA journal_mode = DELETE")
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        for sidecar in temporary_sidecars:
            sidecar.unlink(missing_ok=True)
        raise
    for sidecar in temporary_sidecars:
        sidecar.unlink(missing_ok=True)
    return target


def prune_backups(
    destination: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> list[Path]:
    if retention_days < 1:
        raise ValueError("Backup retention must be at least one day")
    directory = destination.expanduser().resolve()
    if not directory.exists():
        return []
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = observed_at - timedelta(days=retention_days)
    removed: list[Path] = []
    for path in directory.glob("core-*.db"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if path.is_file() and not path.is_symlink() and modified < cutoff:
            path.unlink()
            removed.append(path)
    return removed
