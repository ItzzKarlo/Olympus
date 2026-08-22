from pathlib import Path
import hashlib
import shutil
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class DeviceKey:
    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key

    @property
    def public_bytes(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.public_bytes).hexdigest().upper()
        return "SHA256:" + ":".join(
            digest[index:index + 4] for index in range(0, len(digest), 4)
        )


def _copy_verified(source: Path, destination: Path, mode: int) -> bool:
    if destination.exists() or not source.exists():
        return False
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".migration")
    shutil.copyfile(source, temporary)
    if temporary.read_bytes() != source.read_bytes():
        temporary.unlink(missing_ok=True)
        raise OSError(f"Could not verify migrated Agent state: {destination.name}")
    try:
        temporary.chmod(mode)
    except OSError:
        pass
    temporary.replace(destination)
    return True


def migrate_legacy_identity(
    identity_path: Path,
    key_path: Path,
    legacy_identity_path: Path | None,
    legacy_key_path: Path | None,
) -> tuple[bool, bool]:
    identity_migrated = bool(legacy_identity_path) and _copy_verified(
        legacy_identity_path, identity_path, 0o600
    )
    key_migrated = bool(legacy_key_path) and _copy_verified(
        legacy_key_path, key_path, 0o600
    )
    return identity_migrated, key_migrated


def read_agent_id(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    return value or None


def read_device_fingerprint(path: Path) -> str | None:
    if not path.exists():
        return None
    return load_or_create_device_key(path).fingerprint


def load_or_create_agent_id(path: Path, prefix: str) -> str:
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""

    if existing:
        return existing

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    agent_id = f"{prefix}-{uuid4().hex}"
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(f"{agent_id}\n", encoding="utf-8")
    try:
        temporary_path.chmod(0o600)
    except OSError:
        # Windows ACLs, rather than POSIX modes, protect the user profile path.
        pass
    temporary_path.replace(path)
    return agent_id


def load_or_create_device_key(path: Path) -> DeviceKey:
    try:
        private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("Agent key is not an Ed25519 private key")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return DeviceKey(private_key)
    except FileNotFoundError:
        pass

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    serialized = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_bytes(serialized)
    try:
        temporary_path.chmod(0o600)
    except OSError:
        pass
    temporary_path.replace(path)
    return DeviceKey(private_key)
