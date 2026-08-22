from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
from typing import Iterator

from olympus_core.persistence.migrations import apply_migrations


class Database:
    """Small SQLite boundary shared safely by Core and the local admin CLI."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.available = False

    def initialize(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            self.path.parent.chmod(0o700)
        with self.connect() as connection:
            apply_migrations(connection)
            connection.execute("PRAGMA optimize")
        if os.name != "nt":
            self.path.chmod(0o600)
        self.available = True

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def close(self) -> None:
        self.available = False
