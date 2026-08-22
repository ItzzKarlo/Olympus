from typing import Any

import psutil

from olympus_agent.activity import detect_development_activity


def collect_telemetry() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    return {
        "type": "telemetry",
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": memory.percent,
            "ram_used_bytes": memory.used,
            "ram_total_bytes": memory.total,
        },
        "activity": detect_development_activity().as_dict(),
    }
