from pathlib import Path
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
