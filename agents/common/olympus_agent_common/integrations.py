import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Callable
from uuid import uuid4

from olympus_agent_common.minecraft import (
    normalize_minecraft_event,
    normalize_minecraft_state,
)


LOGGER = logging.getLogger("olympus-agent.integrations")
PROTOCOL_VERSION = 1
LOOPBACK_HOST = "127.0.0.1"
MAX_MESSAGE_BYTES = 65_536
StateNormalizer = Callable[[Any], dict[str, Any]]
EventNormalizer = Callable[[Any, Any], tuple[str, dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class IntegrationAdapter:
    state: StateNormalizer
    event: EventNormalizer


ADAPTERS = {
    "minecraft": IntegrationAdapter(
        state=normalize_minecraft_state,
        event=normalize_minecraft_event,
    )
}
OBSERVER_DEFAULTS = {"minecraft-fabric": "minecraft"}


@dataclass(slots=True)
class IntegrationRecord:
    integration: str
    observer_id: str
    observer_name: str
    observer_version: str
    connection_token: str
    connected: bool
    last_seen_monotonic: float
    last_seen: str
    payload: dict[str, Any] | None = None


class LocalIntegrationServer:
    """Small newline-JSON observer endpoint bound exclusively to loopback."""

    def __init__(
        self,
        port: int = 38_765,
        stale_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.port = port
        self.stale_seconds = stale_seconds
        self._clock = clock
        self._server: asyncio.Server | None = None
        self._records: dict[str, IntegrationRecord] = {}
        self._upstream: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=128)

    @property
    def bound_port(self) -> int | None:
        if self._server is None or not self._server.sockets:
            return None
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client,
            LOOPBACK_HOST,
            self.port,
            limit=MAX_MESSAGE_BYTES,
        )
        LOGGER.info("Local integrations listening on %s:%s", LOOPBACK_HOST, self.bound_port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    def snapshot(self) -> dict[str, dict[str, Any]]:
        now = self._clock()
        result: dict[str, dict[str, Any]] = {}
        for integration, record in self._records.items():
            available = record.payload is not None and now - record.last_seen_monotonic <= self.stale_seconds
            result[integration] = {
                "available": available,
                "connected": record.connected,
                "last_seen": record.last_seen,
                "observer": {
                    "id": record.observer_id,
                    "name": record.observer_name,
                    "version": record.observer_version,
                },
                "payload": record.payload if available else None,
            }
        return result

    async def next_upstream(self) -> dict[str, Any]:
        return await self._upstream.get()

    def _queue(self, message: dict[str, Any]) -> None:
        if self._upstream.full():
            try:
                self._upstream.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._upstream.put_nowait(message)

    @staticmethod
    def _parse_line(line: bytes) -> dict[str, Any]:
        if not line or len(line) > MAX_MESSAGE_BYTES:
            raise ValueError("integration message is empty or too large")
        value = json.loads(line)
        if not isinstance(value, dict) or value.get("protocol") != PROTOCOL_VERSION:
            raise ValueError("unsupported integration envelope")
        return value

    @staticmethod
    def _parse_hello(message: dict[str, Any]) -> tuple[str, str, str]:
        if message.get("type") != "hello" or not isinstance(message.get("integration"), dict):
            raise ValueError("valid integration hello required")
        integration = message["integration"]
        values = tuple(integration.get(key) for key in ("id", "name", "version"))
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("integration identity is incomplete")
        return tuple(str(value).strip()[:128] for value in values)  # type: ignore[return-value]

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        integration_ids: set[str] = set()
        token = uuid4().hex
        try:
            hello = self._parse_line(await reader.readline())
            observer_id, observer_name, observer_version = self._parse_hello(hello)
            default_integration = OBSERVER_DEFAULTS.get(observer_id)
            if default_integration is not None:
                observed_at = datetime.now(timezone.utc).isoformat()
                self._records[default_integration] = IntegrationRecord(
                    integration=default_integration,
                    observer_id=observer_id,
                    observer_name=observer_name,
                    observer_version=observer_version,
                    connection_token=token,
                    connected=True,
                    last_seen_monotonic=self._clock(),
                    last_seen=observed_at,
                )
                integration_ids.add(default_integration)
            writer.write(json.dumps({"protocol": 1, "type": "welcome"}).encode() + b"\n")
            await writer.drain()

            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                message = self._parse_line(line)
                message_type = message.get("type")
                integration = message.get("integration")
                if not isinstance(integration, str) or integration not in ADAPTERS:
                    raise ValueError("unsupported integration")
                adapter = ADAPTERS[integration]
                observed_at = datetime.now(timezone.utc).isoformat()
                record = self._records.get(integration)
                if record is None or record.connection_token != token:
                    record = IntegrationRecord(
                        integration=integration,
                        observer_id=observer_id,
                        observer_name=observer_name,
                        observer_version=observer_version,
                        connection_token=token,
                        connected=True,
                        last_seen_monotonic=self._clock(),
                        last_seen=observed_at,
                    )
                    self._records[integration] = record
                integration_ids.add(integration)
                record.connected = True
                record.last_seen_monotonic = self._clock()
                record.last_seen = observed_at

                if message_type == "state":
                    payload = adapter.state(message.get("payload"))
                    changed = payload != record.payload
                    record.payload = payload
                    if changed:
                        self._queue({
                            "type": "integration_state",
                            "integration": integration,
                            "available": True,
                            "observer": {
                                "id": observer_id,
                                "name": observer_name,
                                "version": observer_version,
                            },
                            "observed_at": observed_at,
                            "payload": payload,
                        })
                elif message_type == "clear":
                    record.payload = None
                    self._queue({
                        "type": "integration_state",
                        "integration": integration,
                        "available": False,
                        "observer": {
                            "id": observer_id,
                            "name": observer_name,
                            "version": observer_version,
                        },
                        "observed_at": observed_at,
                        "payload": None,
                    })
                elif message_type == "event":
                    event, payload = adapter.event(message.get("event"), message.get("payload", {}))
                    self._queue({
                        "type": "integration_event",
                        "integration": integration,
                        "event": event,
                        "observed_at": observed_at,
                        "payload": payload,
                    })
                else:
                    raise ValueError("unsupported integration message type")
        except (ValueError, json.JSONDecodeError, asyncio.LimitOverrunError) as error:
            LOGGER.warning("Rejected local integration message: %s", error)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            for integration in integration_ids:
                record = self._records.get(integration)
                if record is not None and record.connection_token == token:
                    record.connected = False
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
