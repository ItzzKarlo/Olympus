import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


AUTH_CONTEXT = b"olympus-agent-auth-v1"


def decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Invalid base64url value") from error


def encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def auth_payload(agent_id: str, challenge: bytes) -> bytes:
    return AUTH_CONTEXT + b"\0" + agent_id.encode("utf-8") + b"\0" + challenge


def verify_agent_signature(
    public_key: bytes,
    agent_id: str,
    challenge: bytes,
    signature: bytes,
) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, auth_payload(agent_id, challenge)
        )
    except (InvalidSignature, ValueError):
        return False
    return True
