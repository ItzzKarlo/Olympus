from pathlib import Path
import time
from typing import Any

import psutil

from olympus_agent.activity import detect_development_activity
from olympus_agent.gpu import collect_nvidia_gpu
from olympus_agent_common.telemetry import build_telemetry


def collect_telemetry() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    root = Path.home().anchor or "C:\\"
    disk = psutil.disk_usage(root)
    network = psutil.net_io_counters()
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
        activity=detect_development_activity().as_dict(),
    )
