import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from olympus_agent_common.config import AgentConfig
from olympus_agent_common.integrations import LocalIntegrationServer
from olympus_agent_common.minecraft import normalize_minecraft_state
from olympus_agent_common.runtime import run_connection


HELLO = {
    "protocol": 1,
    "type": "hello",
    "integration": {
        "id": "minecraft-fabric",
        "name": "Minecraft Fabric",
        "version": "0.1.0",
    },
}

MINECRAFT_STATE = {
    "connection": {
        "type": "multiplayer",
        "server_name": "Hermes SMP",
        "server_address": "minecraft.local",
    },
    "world": {"dimension": "overworld", "biome": "plains"},
    "player": {
        "position": {"x": -1432.4, "y": 71, "z": 825.8},
        "health": 18,
        "max_health": 20,
        "food": 14,
        "max_food": 20,
        "armor": 16,
        "experience": {"level": 38, "progress": 0.42},
        "game_mode": "survival",
    },
}


async def send(writer: asyncio.StreamWriter, message: object) -> None:
    writer.write(json.dumps(message).encode() + b"\n")
    await writer.drain()


class LocalIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.now = [100.0]
        self.server = LocalIntegrationServer(
            port=0,
            stale_seconds=5,
            clock=lambda: self.now[0],
        )
        await self.server.start()

    async def asyncTearDown(self) -> None:
        await self.server.stop()

    async def connect(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_connection("127.0.0.1", self.server.bound_port)

    async def test_binds_only_to_ipv4_loopback_and_accepts_hello(self) -> None:
        self.assertEqual(self.server._server.sockets[0].getsockname()[0], "127.0.0.1")
        reader, writer = await self.connect()
        await send(writer, HELLO)
        welcome = json.loads(await reader.readline())
        self.assertEqual(welcome, {"protocol": 1, "type": "welcome"})
        self.assertTrue(self.server.snapshot()["minecraft"]["connected"])
        writer.close()
        await writer.wait_closed()

    async def test_receives_normalized_state_and_event(self) -> None:
        reader, writer = await self.connect()
        await send(writer, HELLO)
        await reader.readline()
        await send(writer, {
            "protocol": 1,
            "type": "state",
            "integration": "minecraft",
            "payload": MINECRAFT_STATE,
        })
        state = await asyncio.wait_for(self.server.next_upstream(), 1)
        self.assertEqual(state["type"], "integration_state")
        self.assertEqual(state["payload"]["world"]["biome"], "plains")

        await send(writer, {
            "protocol": 1,
            "type": "event",
            "integration": "minecraft",
            "event": "player.damage_taken",
            "payload": {"amount": 3, "health_after": 15, "max_health": 20},
        })
        event = await asyncio.wait_for(self.server.next_upstream(), 1)
        self.assertEqual(event["event"], "minecraft.player.damage_taken")
        self.assertEqual(event["payload"]["amount"], 3)
        writer.close()
        await writer.wait_closed()

    async def test_disconnect_expires_state_without_stopping_server(self) -> None:
        reader, writer = await self.connect()
        await send(writer, HELLO)
        await reader.readline()
        await send(writer, {
            "protocol": 1,
            "type": "state",
            "integration": "minecraft",
            "payload": MINECRAFT_STATE,
        })
        await self.server.next_upstream()
        writer.close()
        await writer.wait_closed()
        for _ in range(10):
            if not self.server.snapshot()["minecraft"]["connected"]:
                break
            await asyncio.sleep(0.01)
        self.assertFalse(self.server.snapshot()["minecraft"]["connected"])
        self.assertTrue(self.server.snapshot()["minecraft"]["available"])
        self.now[0] = 106
        self.assertFalse(self.server.snapshot()["minecraft"]["available"])
        self.assertIsNone(self.server.snapshot()["minecraft"]["payload"])

    async def test_malformed_client_isolated_from_next_connection(self) -> None:
        reader, writer = await self.connect()
        writer.write(b"not json\n")
        await writer.drain()
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        writer.close()
        await writer.wait_closed()

    async def test_agent_core_connection_survives_local_integration_disconnect(self) -> None:
        class FakeCoreSocket:
            def __init__(self) -> None:
                self.sent: list[dict[str, object]] = []

            async def __aenter__(self) -> "FakeCoreSocket":
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

            async def send(self, raw_message: str) -> None:
                self.sent.append(json.loads(raw_message))

            async def recv(self) -> str:
                return json.dumps({"type": "welcome", "agent_id": "test-agent"})

        core_socket = FakeCoreSocket()
        config = AgentConfig(
            core_ws_url="ws://core.invalid/ws/agents",
            telemetry_interval=0.01,
            reconnect_delay=0.01,
            identity_path=Path("/tmp/unused-olympus-test-identity"),
        )

        def collect() -> dict[str, object]:
            return {
                "type": "telemetry",
                "system": {
                    "cpu_percent": 1,
                    "ram_percent": 2,
                    "ram_used_bytes": 2,
                    "ram_total_bytes": 100,
                },
                "activity": {
                    "mode": "gaming",
                    "application": "Minecraft",
                    "process_name": "javaw.exe",
                    "game": {"id": "minecraft", "name": "Minecraft"},
                },
            }

        with patch("olympus_agent_common.runtime.connect", return_value=core_socket):
            task = asyncio.create_task(run_connection(
                config,
                "test-agent",
                "windows",
                "11",
                "0.6.0",
                collect,
                self.server,
            ))
            for _ in range(20):
                if core_socket.sent:
                    break
                await asyncio.sleep(0.01)

            reader, writer = await self.connect()
            await send(writer, HELLO)
            await reader.readline()
            await send(writer, {
                "protocol": 1,
                "type": "state",
                "integration": "minecraft",
                "payload": MINECRAFT_STATE,
            })
            writer.close()
            await writer.wait_closed()
            for _ in range(20):
                if not self.server.snapshot()["minecraft"]["connected"]:
                    break
                await asyncio.sleep(0.01)

            sent_after_disconnect = len(core_socket.sent)
            await asyncio.sleep(0.04)
            self.assertFalse(task.done())
            self.assertGreater(len(core_socket.sent), sent_after_disconnect)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        reader, writer = await self.connect()
        await send(writer, HELLO)
        self.assertEqual(json.loads(await reader.readline())["type"], "welcome")
        writer.close()
        await writer.wait_closed()


class MinecraftNormalizationTests(unittest.TestCase):
    def test_normalizes_multiplayer_state_and_modded_identifiers(self) -> None:
        payload = {**MINECRAFT_STATE,
            "world": {"dimension": "mod:moon", "biome": "mod:crystal_fields"}}
        state = normalize_minecraft_state(payload)
        self.assertEqual(state["connection"]["server_name"], "Hermes SMP")
        self.assertEqual(state["world"]["dimension"], "mod:moon")
        self.assertEqual(state["player"]["position"]["x"], -1432.4)

    def test_singleplayer_and_optional_fields(self) -> None:
        state = normalize_minecraft_state({
            "connection": {"type": "singleplayer", "world_name": "Home World"},
            "world": {"dimension": "overworld"},
            "player": {"position": {"x": 1, "y": 2, "z": 3}},
        })
        self.assertEqual(state["connection"]["world_name"], "Home World")
        self.assertIsNone(state["player"]["health"])
        self.assertEqual(state["player"]["game_mode"], "unknown")


if __name__ == "__main__":
    unittest.main()
