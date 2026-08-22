from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from olympus_core.persistence.database import Database
from olympus_core.persistence.devices import DeviceRepository
from olympus_core.persistence.enrollment import EnrollmentError, EnrollmentRepository, _hash_token
from olympus_core.persistence.migrations import apply_migrations


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "state" / "core.db"
        self.database = Database(self.path)
        self.database.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_empty_database_migrates_and_latest_is_noop(self) -> None:
        self.database.initialize()
        with self.database.connect() as connection:
            version = connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(version, 1)
        self.assertEqual(mode, "wal")
        self.assertEqual(foreign_keys, 1)

    def test_failed_migration_rolls_back(self) -> None:
        connection = sqlite3.connect(":memory:")
        with self.assertRaises(sqlite3.OperationalError):
            apply_migrations(connection, ((1, (
                "CREATE TABLE temporary_value(id INTEGER)",
                "THIS IS NOT SQL",
            )),))
        table = connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'temporary_value'"
        ).fetchone()
        self.assertIsNone(table)

    def test_enrollment_is_hashed_atomic_single_use_and_restart_safe(self) -> None:
        enrollment = EnrollmentRepository(self.database)
        created = enrollment.create(now=datetime.now(timezone.utc))
        with self.database.connect() as connection:
            row = connection.execute("SELECT token_hash FROM enrollment_tokens").fetchone()
            dump = " ".join(str(value) for value in row)
        self.assertNotIn(created.token, dump)
        self.assertEqual(row["token_hash"], _hash_token(created.token))

        enrolled = enrollment.enroll(
            token=created.token,
            agent_id="linux-test",
            display_name="Hermes",
            platform="linux",
            public_key=b"a" * 32,
        )
        self.assertEqual(enrolled.agent_id, "linux-test")
        with self.assertRaises(EnrollmentError):
            enrollment.enroll(
                token=created.token,
                agent_id="other",
                display_name="Other",
                platform="linux",
                public_key=b"b" * 32,
            )

        reopened = Database(self.path)
        reopened.initialize()
        self.assertEqual(DeviceRepository(reopened).get("linux-test").public_key, enrolled.public_key)

    def test_expired_and_unknown_tokens_are_rejected(self) -> None:
        now = datetime.now(timezone.utc)
        enrollment = EnrollmentRepository(self.database)
        expired = enrollment.create(ttl_minutes=1, now=now - timedelta(minutes=2))
        for token in (expired.token, "OLYMPUS-unknown-token-with-sufficient-length"):
            with self.subTest(token=token[:12]):
                with self.assertRaises(EnrollmentError):
                    enrollment.enroll(
                        token=token,
                        agent_id="test",
                        display_name="Test",
                        platform="linux",
                        public_key=b"c" * 32,
                        now=now,
                    )

    def test_revoked_device_can_only_be_reenrolled_with_a_new_token(self) -> None:
        enrollment = EnrollmentRepository(self.database)
        first = enrollment.create()
        enrollment.enroll(
            token=first.token,
            agent_id="device",
            display_name="Device",
            platform="linux",
            public_key=b"d" * 32,
        )
        devices = DeviceRepository(self.database)
        self.assertTrue(devices.revoke("device"))
        second = enrollment.create()
        replaced = enrollment.enroll(
            token=second.token,
            agent_id="device",
            display_name="Device",
            platform="linux",
            public_key=b"e" * 32,
        )
        self.assertFalse(replaced.revoked)
        self.assertNotEqual(replaced.public_key, first.token)


if __name__ == "__main__":
    unittest.main()
