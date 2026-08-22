import asyncio
from dataclasses import dataclass
import socket
import time

import httpx


@dataclass(frozen=True, slots=True)
class ProbeResult:
    success: bool
    latency_ms: float | None = None
    host: str | None = None
    source: str | None = None


async def tcp_probe(
    host: str,
    port: int,
    timeout: float,
    *,
    refused_is_reachable: bool = False,
) -> ProbeResult:
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        del reader
        writer.close()
        await writer.wait_closed()
    except ConnectionRefusedError:
        if not refused_is_reachable:
            return ProbeResult(False)
    except (TimeoutError, OSError):
        return ProbeResult(False)
    return ProbeResult(True, (time.perf_counter() - started) * 1000)


async def dns_probe(hostname: str, timeout: float) -> ProbeResult:
    started = time.perf_counter()
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM),
            timeout=timeout,
        )
    except (TimeoutError, OSError, socket.gaierror):
        return ProbeResult(False)
    return ProbeResult(True, (time.perf_counter() - started) * 1000)


async def http_probe(
    client: httpx.AsyncClient,
    url: str,
    timeout: float,
) -> ProbeResult:
    started = time.perf_counter()
    try:
        response = await client.get(url, timeout=timeout)
    except httpx.HTTPError:
        return ProbeResult(False)
    return ProbeResult(
        response.status_code < 400,
        (time.perf_counter() - started) * 1000,
    )
