import asyncio
from dataclasses import dataclass
import ipaddress
import platform
import re
import subprocess
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResolvedGateway:
    host: str
    source: str


def _valid_ipv4(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    return str(address) if address.version == 4 and not address.is_unspecified else None


def parse_linux_default_route(content: str) -> str | None:
    for line in content.splitlines()[1:]:
        columns = line.split()
        if len(columns) < 4 or columns[1] != "00000000":
            continue
        try:
            flags = int(columns[3], 16)
            raw = bytes.fromhex(columns[2])
        except (ValueError, IndexError):
            continue
        if flags & 0x2 and len(raw) == 4:
            return _valid_ipv4(".".join(str(part) for part in reversed(raw)))
    return None


def parse_macos_default_route(content: str) -> str | None:
    match = re.search(r"^\s*gateway:\s+(\S+)", content, re.MULTILINE)
    return _valid_ipv4(match.group(1)) if match else None


def parse_windows_default_route(content: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    for line in content.splitlines():
        columns = line.split()
        if len(columns) < 5 or columns[0] != "0.0.0.0" or columns[1] != "0.0.0.0":
            continue
        gateway = _valid_ipv4(columns[2])
        try:
            metric = int(columns[-1])
        except ValueError:
            continue
        if gateway:
            candidates.append((metric, gateway))
    return min(candidates)[1] if candidates else None


def detect_default_gateway_sync(system_name: str | None = None) -> str | None:
    current = (system_name or platform.system()).lower()
    try:
        if current == "linux":
            return parse_linux_default_route(
                Path("/proc/net/route").read_text(encoding="utf-8")
            )
        if current == "darwin":
            result = subprocess.run(
                ["/sbin/route", "-n", "get", "default"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            return parse_macos_default_route(result.stdout)
        if current == "windows":
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            return parse_windows_default_route(result.stdout)
    except (OSError, subprocess.SubprocessError):
        return None
    return None


async def resolve_gateway(configured: str) -> ResolvedGateway | None:
    if configured.casefold() != "auto":
        host = _valid_ipv4(configured)
        return ResolvedGateway(host, "configured") if host else None
    host = await asyncio.to_thread(detect_default_gateway_sync)
    return ResolvedGateway(host, "auto") if host else None
