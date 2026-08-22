from pathlib import Path
import time
from typing import Any
from dataclasses import replace

import psutil

from olympus_agent.activity import detect_development_activity
from olympus_agent.foreground import get_foreground_process_id
from olympus_agent.fps import fps_provider_from_environment
from olympus_agent.game_profiles import WINDOWS_GAME_PROFILES
from olympus_agent.gpu import collect_nvidia_gpu
from olympus_agent_common.games import ForegroundGameDetector, ProcessInfo
from olympus_agent_common.telemetry import build_telemetry


GAME_DETECTOR = ForegroundGameDetector(WINDOWS_GAME_PROFILES, 15.0)
FPS_PROVIDER = fps_provider_from_environment()


def configure_game_detection(grace_seconds: float) -> None:
    global GAME_DETECTOR
    GAME_DETECTOR = ForegroundGameDetector(WINDOWS_GAME_PROFILES, grace_seconds)


def _process_snapshots() -> tuple[list[Any], list[ProcessInfo]]:
    raw_processes: list[Any] = []
    game_processes: list[ProcessInfo] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        raw_processes.append(process)
        try:
            info = process.info
            name = info.get("name")
            pid = info.get("pid")
            if name and isinstance(pid, int):
                game_processes.append(
                    ProcessInfo(pid, name, tuple(info.get("cmdline") or ()))
                )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return raw_processes, game_processes


def collect_telemetry() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    root = Path.home().anchor or "C:\\"
    disk = psutil.disk_usage(root)
    network = psutil.net_io_counters()
    raw_processes, game_processes = _process_snapshots()
    activity = GAME_DETECTOR.detect(game_processes, get_foreground_process_id())
    if activity is not None and FPS_PROVIDER is not None and activity.process_name:
        activity = replace(
            activity,
            fps=FPS_PROVIDER.latest_fps(activity.process_name),
        )
    if activity is None:
        activity = detect_development_activity(raw_processes)
    return build_telemetry(
        system={
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": memory.percent,
            "ram_used_bytes": memory.used,
            "ram_total_bytes": memory.total,
            "uptime_seconds": max(0, time.time() - psutil.boot_time()),
        },
        storage={
            "root_used_percent": disk.percent,
            "root_free_bytes": disk.free,
            "root_total_bytes": disk.total,
        },
        network={
            "bytes_sent": network.bytes_sent,
            "bytes_received": network.bytes_recv,
        },
        gpu=collect_nvidia_gpu(),
        activity=activity.as_dict(),
    )
