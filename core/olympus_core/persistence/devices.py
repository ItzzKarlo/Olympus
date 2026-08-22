from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
from hashlib import sha256

from olympus_core.persistence.database import Database


def public_key_fingerprint(public_key: bytes) -> str:
    digest = sha256(public_key).hexdigest().upper()
    return "SHA256:" + ":".join(digest[index:index + 4] for index in range(0, len(digest), 4))


def encode_public_key(public_key: bytes) -> str:
    return base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class TrustedDevice:
    agent_id: str
    display_name: str
    platform: str
    public_key: str
    public_key_fingerprint: str
    enrolled_at: datetime
    last_authenticated_at: datetime | None
    last_seen_at: datetime | None
    revoked_at: datetime | None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _device(row: object) -> TrustedDevice:
    return TrustedDevice(
        agent_id=row["agent_id"],  # type: ignore[index]
        display_name=row["display_name"],  # type: ignore[index]
        platform=row["platform"],  # type: ignore[index]
        public_key=row["public_key"],  # type: ignore[index]
        public_key_fingerprint=row["public_key_fingerprint"],  # type: ignore[index]
        enrolled_at=_time(row["enrolled_at"]),  # type: ignore[index,arg-type]
        last_authenticated_at=_time(row["last_authenticated_at"]),  # type: ignore[index]
        last_seen_at=_time(row["last_seen_at"]),  # type: ignore[index]
        revoked_at=_time(row["revoked_at"]),  # type: ignore[index]
    )  # type: ignore[arg-type]


class DeviceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, agent_id: str) -> TrustedDevice | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM trusted_devices WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return _device(row) if row is not None else None

    def list(self) -> list[TrustedDevice]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM trusted_devices ORDER BY display_name, agent_id"
            ).fetchall()
        return [_device(row) for row in rows]

    def record_authenticated(self, agent_id: str, when: datetime | None = None) -> None:
        observed_at = (when or datetime.now(timezone.utc)).isoformat()
        with self._database.connect() as connection:
            cursor = connection.execute(
                "UPDATE trusted_devices SET last_authenticated_at = ?, last_seen_at = ? "
                "WHERE agent_id = ? AND revoked_at IS NULL",
                (observed_at, observed_at, agent_id),
            )
            connection.commit()
        if cursor.rowcount != 1:
            raise PermissionError("Device is not trusted")

    def touch_last_seen(
        self,
        agent_id: str,
        minimum_interval_seconds: float,
        when: datetime | None = None,
        *,
        force: bool = False,
    ) -> bool:
        observed = when or datetime.now(timezone.utc)
        cutoff = observed - timedelta(seconds=minimum_interval_seconds)
        with self._database.connect() as connection:
            if force:
                cursor = connection.execute(
                    "UPDATE trusted_devices SET last_seen_at = ? "
                    "WHERE agent_id = ? AND revoked_at IS NULL",
                    (observed.isoformat(), agent_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE trusted_devices SET last_seen_at = ? "
                    "WHERE agent_id = ? AND revoked_at IS NULL "
                    "AND (last_seen_at IS NULL OR last_seen_at <= ?)",
                    (observed.isoformat(), agent_id, cutoff.isoformat()),
                )
            connection.commit()
        return cursor.rowcount == 1

    def revoke(self, agent_id: str, when: datetime | None = None) -> bool:
        revoked_at = (when or datetime.now(timezone.utc)).isoformat()
        with self._database.connect() as connection:
            cursor = connection.execute(
                "UPDATE trusted_devices SET revoked_at = ? "
                "WHERE agent_id = ? AND revoked_at IS NULL",
                (revoked_at, agent_id),
            )
            connection.commit()
        return cursor.rowcount == 1
