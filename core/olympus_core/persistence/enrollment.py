from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from olympus_core.persistence.database import Database
from olympus_core.persistence.devices import (
    TrustedDevice,
    _device,
    encode_public_key,
    public_key_fingerprint,
)


class EnrollmentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EnrollmentToken:
    token: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class EnrollmentRepository:
    def __init__(self, database: Database, default_ttl_minutes: int = 10) -> None:
        self._database = database
        self._default_ttl_minutes = default_ttl_minutes

    def create(
        self,
        ttl_minutes: int | None = None,
        label: str | None = None,
        now: datetime | None = None,
    ) -> EnrollmentToken:
        created_at = now or datetime.now(timezone.utc)
        ttl = ttl_minutes or self._default_ttl_minutes
        if ttl <= 0:
            raise ValueError("Enrollment token TTL must be greater than zero")
        expires_at = created_at + timedelta(minutes=ttl)
        token = f"OLYMPUS-{secrets.token_urlsafe(32)}"
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO enrollment_tokens(token_hash, label, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (_hash_token(token), label, created_at.isoformat(), expires_at.isoformat()),
            )
            connection.commit()
        return EnrollmentToken(token, expires_at)

    def enroll(
        self,
        *,
        token: str,
        agent_id: str,
        display_name: str,
        platform: str,
        public_key: bytes,
        now: datetime | None = None,
    ) -> TrustedDevice:
        if len(public_key) != 32:
            raise EnrollmentError("Invalid device public key")
        observed_at = now or datetime.now(timezone.utc)
        encoded_key = encode_public_key(public_key)
        fingerprint = public_key_fingerprint(public_key)
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                token_row = connection.execute(
                    "SELECT id, expires_at, used_at FROM enrollment_tokens WHERE token_hash = ?",
                    (_hash_token(token),),
                ).fetchone()
                if token_row is None:
                    raise EnrollmentError("Enrollment token is invalid")
                if token_row["used_at"] is not None:
                    raise EnrollmentError("Enrollment token has already been used")
                if datetime.fromisoformat(token_row["expires_at"]) <= observed_at:
                    raise EnrollmentError("Enrollment token has expired")

                existing = connection.execute(
                    "SELECT * FROM trusted_devices WHERE agent_id = ?", (agent_id,)
                ).fetchone()
                if existing is not None and existing["revoked_at"] is None:
                    raise EnrollmentError("Agent ID is already bound to a trusted key")
                if existing is None:
                    connection.execute(
                        "INSERT INTO trusted_devices(" 
                        "agent_id, display_name, platform, public_key, public_key_fingerprint, "
                        "enrolled_at, last_authenticated_at, last_seen_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            agent_id, display_name, platform, encoded_key, fingerprint,
                            observed_at.isoformat(), observed_at.isoformat(), observed_at.isoformat(),
                        ),
                    )
                else:
                    connection.execute(
                        "UPDATE trusted_devices SET display_name = ?, platform = ?, public_key = ?, "
                        "public_key_fingerprint = ?, enrolled_at = ?, last_authenticated_at = ?, "
                        "last_seen_at = ?, revoked_at = NULL WHERE agent_id = ?",
                        (
                            display_name, platform, encoded_key, fingerprint,
                            observed_at.isoformat(), observed_at.isoformat(),
                            observed_at.isoformat(), agent_id,
                        ),
                    )
                connection.execute(
                    "UPDATE enrollment_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
                    (observed_at.isoformat(), token_row["id"]),
                )
                row = connection.execute(
                    "SELECT * FROM trusted_devices WHERE agent_id = ?", (agent_id,)
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return _device(row)
