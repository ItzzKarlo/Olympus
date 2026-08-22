from pathlib import Path
import asyncio
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.websockets import WebSocketDisconnect

from olympus_core.agents.registry import AgentRegistry
from olympus_core.config import SecuritySettings
from olympus_core.persistence.database import Database
from olympus_core.persistence.devices import DeviceRepository, encode_public_key
from olympus_core.persistence.enrollment import EnrollmentRepository
from olympus_core.security import auth_payload, decode_base64url, encode_base64url
from olympus_core.websocket.agents import handle_agent_socket


def public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def hello(agent_id: str, key: Ed25519PrivateKey, token: str | None = None) -> dict[str, str]:
    value = {
        "type": "hello",
        "agent_id": agent_id,
        "hostname": "Test Device",
        "platform": "linux",
        "platform_version": "1",
        "agent_version": "0.12.0",
        "public_key": encode_public_key(public_bytes(key)),
    }
    if token:
        value["enrollment_token"] = token
    return value


class FakeWebSocket:
    def __init__(self, messages: list[object], signer: Ed25519PrivateKey | None = None, agent_id: str = "agent") -> None:
        self.messages = list(messages)
        self.signer = signer
        self.agent_id = agent_id
        self.sent: list[dict[str, object]] = []
        self.close_code: int | None = None
        self.close_reason: str | None = None

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict[str, object]) -> None:
        self.sent.append(message)

    async def receive_json(self) -> object:
        if self.messages:
            return self.messages.pop(0)
        if self.signer and self.sent and self.sent[-1].get("type") == "auth_challenge":
            challenge = decode_base64url(str(self.sent[-1]["challenge"]))
            signature = self.signer.sign(auth_payload(self.agent_id, challenge))
            self.signer = None
            return {"type": "auth_response", "signature": encode_base64url(signature)}
        raise WebSocketDisconnect()

    async def close(self, code: int, reason: str) -> None:
        self.close_code = code
        self.close_reason = reason


class AgentAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "core.db")
        self.database.initialize()
        self.devices = DeviceRepository(self.database)
        self.enrollment = EnrollmentRepository(self.database)
        self.security = SecuritySettings(
            auth_timeout_seconds=1,
            revocation_refresh_seconds=1,
            last_seen_write_seconds=5,
        )
        self.registry = AgentRegistry()

    async def asyncTearDown(self) -> None:
        self.temporary.cleanup()

    async def run_socket(self, socket: FakeWebSocket) -> None:
        async def publish() -> None:
            pass
        await handle_agent_socket(
            socket, self.registry, publish,
            security=self.security,
            devices=self.devices,
            enrollment=self.enrollment,
        )

    async def enroll(self, agent_id: str, key: Ed25519PrivateKey) -> None:
        token = self.enrollment.create()
        socket = FakeWebSocket([hello(agent_id, key, token.token)])
        await self.run_socket(socket)
        self.assertEqual(socket.sent[-1]["type"], "welcome")

    async def test_enrollment_then_signed_reconnect_survives_database_reopen(self) -> None:
        key = Ed25519PrivateKey.generate()
        await self.enroll("agent", key)
        reopened = Database(self.database.path)
        reopened.initialize()
        self.devices = DeviceRepository(reopened)
        self.enrollment = EnrollmentRepository(reopened)
        socket = FakeWebSocket([hello("agent", key)], signer=key)
        await self.run_socket(socket)
        self.assertEqual([item["type"] for item in socket.sent], ["auth_challenge", "welcome"])

    async def test_wrong_key_for_known_agent_is_rejected_before_registry(self) -> None:
        await self.enroll("claimed", Ed25519PrivateKey.generate())
        self.registry = AgentRegistry()
        attacker = Ed25519PrivateKey.generate()
        socket = FakeWebSocket([hello("claimed", attacker)], signer=attacker, agent_id="claimed")
        await self.run_socket(socket)
        self.assertEqual(socket.close_reason, "Authentication failed")
        self.assertIsNone(self.registry.get("claimed"))

    async def test_pre_auth_telemetry_is_rejected(self) -> None:
        key = Ed25519PrivateKey.generate()
        await self.enroll("agent", key)
        self.registry = AgentRegistry()
        socket = FakeWebSocket([
            hello("agent", key),
            {"type": "telemetry", "system": {}, "activity": {"mode": "idle"}},
        ])
        await self.run_socket(socket)
        self.assertEqual(socket.close_reason, "Authentication failed")
        self.assertIsNone(self.registry.get("agent"))

    async def test_replayed_signature_fails_on_new_challenge(self) -> None:
        key = Ed25519PrivateKey.generate()
        await self.enroll("agent", key)
        old_challenge = b"old-challenge".ljust(32, b"x")
        old_signature = key.sign(auth_payload("agent", old_challenge))
        socket = FakeWebSocket([
            hello("agent", key),
            {"type": "auth_response", "signature": encode_base64url(old_signature)},
        ])
        await self.run_socket(socket)
        self.assertEqual(socket.close_reason, "Authentication failed")

    async def test_revoked_device_is_rejected_without_new_enrollment(self) -> None:
        key = Ed25519PrivateKey.generate()
        await self.enroll("agent", key)
        self.devices.revoke("agent")
        self.registry = AgentRegistry()
        socket = FakeWebSocket([hello("agent", key)])
        await self.run_socket(socket)
        self.assertEqual(socket.sent[0]["type"], "enrollment_required")
        self.assertIsNone(self.registry.get("agent"))

    async def test_authentication_disabled_preserves_explicit_development_flow(self) -> None:
        self.security = SecuritySettings(require_agent_auth=False)
        socket = FakeWebSocket([{
            "type": "hello",
            "agent_id": "legacy",
            "hostname": "Legacy",
            "platform": "linux",
            "platform_version": "1",
            "agent_version": "0.11.0",
        }])
        await self.run_socket(socket)
        self.assertEqual(socket.sent[0]["type"], "welcome")
        self.assertIsNotNone(self.registry.get("legacy"))

    async def test_active_revocation_closes_connection_within_refresh(self) -> None:
        key = Ed25519PrivateKey.generate()
        await self.enroll("agent", key)
        self.registry = AgentRegistry()
        self.security = SecuritySettings(
            auth_timeout_seconds=1,
            revocation_refresh_seconds=0.02,
            last_seen_write_seconds=5,
        )
        socket = FakeWebSocket([hello("agent", key)], signer=key)
        original_receive = socket.receive_json

        async def receive() -> object:
            if socket.signer is None and socket.sent and socket.sent[-1].get("type") == "welcome":
                await asyncio.sleep(60)
            return await original_receive()

        socket.receive_json = receive  # type: ignore[method-assign]
        task = asyncio.create_task(self.run_socket(socket))
        while not socket.sent or socket.sent[-1].get("type") != "welcome":
            await asyncio.sleep(0)
        self.devices.revoke("agent")
        await asyncio.wait_for(task, 1)
        self.assertEqual(socket.close_reason, "Device trust revoked")


if __name__ == "__main__":
    unittest.main()
