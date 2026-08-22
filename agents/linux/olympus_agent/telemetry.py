import time
from typing import Any

import psutil

from olympus_agent.activity import detect_development_activity
from olympus_agent.game_profiles import LINUX_GAME_PROFILES
from olympus_agent_common.games import ProcessInfo, detect_running_game
from olympus_agent_common.telemetry import build_telemetry, optional_section


PREFERRED_CPU_SENSORS = ("coretemp", "k10temp", "cpu_thermal", "acpitz")


def normalize_cpu_temperature(readings: dict[str, list[Any]]) -> float | None:
    for sensor_name in PREFERRED_CPU_SENSORS:
        temperatures = [
            float(entry.current)
            for entry in readings.get(sensor_name, [])
            if getattr(entry, "current", None) is not None
        ]
        if temperatures:
            return max(temperatures)
    return None


def collect_telemetry() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    network = psutil.net_io_counters()
    try:
        sensor_readings = psutil.sensors_temperatures(fahrenheit=False)
    except (AttributeError, OSError):
        sensor_readings = {}
    temperatures = optional_section(
        cpu_celsius=normalize_cpu_temperature(sensor_readings),
        gpu_celsius=None,
    )
    raw_processes: list[Any] = []
    game_processes: list[ProcessInfo] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        raw_processes.append(process)
        try:
            info = process.info
            if info.get("name") and isinstance(info.get("pid"), int):
                game_processes.append(
                    ProcessInfo(
                        info["pid"],
                        info["name"],
                        tuple(info.get("cmdline") or ()),
                    )
                )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    activity = detect_running_game(game_processes, LINUX_GAME_PROFILES)
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
        temperatures=temperatures,
        activity=activity.as_dict(),
    )
