import asyncio
from datetime import datetime, timezone
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from olympus_core.display.static import install_display_routes
from olympus_core.healthcheck import HealthWatchdog, main as healthcheck_main
from olympus_core.persistence.backup import create_backup, prune_backups
from olympus_core.persistence.database import Database
from olympus_core.main import app, health
from olympus_core.release import release_info


class ReleaseInfoTests(unittest.TestCase):
    def test_core_reports_v1_and_reads_packaged_revision(self) -> None:
        self.assertEqual(app.version, "1.0.1")
        self.assertEqual(asyncio.run(health())["version"], "1.0.1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (root / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": "b" * 40,
                "source_tree": "clean",
                "version": "1.0.0",
            }), encoding="ascii")
            release = release_info(root)
        self.assertEqual(release.version, "1.0.0")
        self.assertEqual(release.revision, "b" * 40)
        self.assertEqual(release.source_tree, "clean")

    def test_invalid_or_mismatched_metadata_never_claims_a_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("1.0.0\n", encoding="ascii")
            (root / "RELEASE-METADATA.json").write_text(json.dumps({
                "revision": "short",
                "source_tree": "clean",
                "version": "0.14.1",
            }), encoding="ascii")
            release = release_info(root)
        self.assertEqual(release.version, "1.0.0")
        self.assertEqual(release.revision, "unknown")
        self.assertEqual(release.source_tree, "development")


class ProductionDisplayTests(unittest.TestCase):
    def test_built_display_and_spa_are_served_without_consuming_api_or_websocket(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            display = Path(directory)
            (display / "assets").mkdir()
            (display / "index.html").write_text("<main>Olympus</main>", encoding="utf-8")
            (display / "assets" / "app.js").write_text("window.olympus = true", encoding="utf-8")
            app = FastAPI()

            @app.get("/api/value")
            async def api_value() -> dict[str, bool]:
                return {"api": True}

            @app.websocket("/ws/display")
            async def display_socket(websocket: WebSocket) -> None:
                await websocket.accept()
                await websocket.send_text("connected")
                await websocket.close()

            install_display_routes(app, display)
            client = TestClient(app)
            self.assertIn("Olympus", client.get("/").text)
            self.assertIn("Olympus", client.get("/settings/ambient").text)
            self.assertEqual(client.get("/assets/app.js").text, "window.olympus = true")
            self.assertEqual(client.get("/api/value").json(), {"api": True})
            self.assertEqual(client.get("/api/unknown").status_code, 404)
            self.assertEqual(client.get("/ws/unknown").status_code, 404)
            with client.websocket_connect("/ws/display") as websocket:
                self.assertEqual(websocket.receive_text(), "connected")

    def test_missing_display_build_reports_service_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = FastAPI()
            install_display_routes(app, Path(directory) / "missing")
            response = TestClient(app).get("/")
            self.assertEqual(response.status_code, 503)
            self.assertIn("not installed", response.json()["detail"])


class BackupTests(unittest.TestCase):
    def test_online_backup_is_integral_and_preserves_database_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "state" / "core.db")
            database.initialize()
            with database.connect() as connection:
                connection.execute(
                    "INSERT INTO enrollment_tokens(token_hash, created_at, expires_at) VALUES (?, ?, ?)",
                    ("backup-test", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
                )
                connection.commit()
            created = create_backup(
                database.path,
                root / "backups",
                now=datetime(2026, 8, 23, 8, 9, 10, tzinfo=timezone.utc),
            )
            self.assertEqual(created.name, "core-20260823-080910.db")
            if os.name != "nt":
                self.assertEqual(created.stat().st_mode & 0o777, 0o600)
            self.assertFalse(Path(f"{created}.tmp-wal").exists())
            self.assertFalse(Path(f"{created}.tmp-shm").exists())
            with closing(sqlite3.connect(created)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM enrollment_tokens WHERE token_hash = 'backup-test'"
                    ).fetchone()[0],
                    1,
                )

    def test_backup_retention_removes_only_expired_matching_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "core-20260701-000000.db"
            recent = root / "core-20260822-000000.db"
            unrelated = root / "notes.txt"
            for path in (old, recent, unrelated):
                path.write_text("test", encoding="utf-8")
            now = datetime(2026, 8, 23, tzinfo=timezone.utc)
            os.utime(old, (now.timestamp() - 20 * 86_400,) * 2)
            os.utime(recent, (now.timestamp() - 86_400,) * 2)
            removed = prune_backups(root, 14, now=now)
            self.assertEqual(removed, [old.resolve()])
            self.assertTrue(recent.exists())
            self.assertTrue(unrelated.exists())

    def test_missing_source_fails_without_partial_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                create_backup(root / "missing.db", root / "backups")
            self.assertFalse((root / "backups").exists())


class HealthWatchdogTests(unittest.TestCase):
    def test_failures_are_thresholded_and_recovery_resets_counter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "health-failures"
            restart = Mock()
            watchdog = HealthWatchdog(state, 3, restart)
            self.assertEqual(watchdog.record(False), (1, False))
            self.assertEqual(watchdog.record(False), (2, False))
            restart.assert_not_called()
            self.assertEqual(watchdog.record(True), (0, False))
            self.assertEqual(state.read_text(encoding="ascii"), "0\n")
            self.assertEqual(watchdog.record(False), (1, False))
            self.assertEqual(watchdog.record(False), (2, False))
            self.assertEqual(watchdog.record(False), (3, True))
            restart.assert_called_once_with()
            self.assertEqual(state.read_text(encoding="ascii"), "0\n")

    def test_invalid_or_stale_counter_is_treated_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "health-failures"
            state.write_text("broken", encoding="ascii")
            self.assertEqual(HealthWatchdog(state, 3, Mock()).record(False), (1, False))

    def test_deliberately_stopped_core_is_never_restarted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "health-failures"
            state.write_text("2\n", encoding="ascii")
            with (
                patch("olympus_core.healthcheck.core_service_active", return_value=False),
                patch("olympus_core.healthcheck.restart_core") as restart,
            ):
                self.assertEqual(healthcheck_main([
                    "--url", "http://127.0.0.1:9/health",
                    "--state", str(state),
                    "--threshold", "3",
                ]), 0)
            restart.assert_not_called()
            self.assertEqual(state.read_text(encoding="ascii"), "0\n")


if __name__ == "__main__":
    unittest.main()
