from collections.abc import Iterable
from typing import Any

import psutil

from olympus_agent_common.activity import detect_mapped_activity
from olympus_agent_common.protocol import ActivityObservation


IDE_PROCESSES = {
    "code": "Visual Studio Code",
    "cursor": "Cursor",
    "idea": "IntelliJ IDEA",
    "idea64": "IntelliJ IDEA",
    "rider": "Rider",
    "pycharm": "PyCharm",
    "webstorm": "WebStorm",
    "clion": "CLion",
    "goland": "GoLand",
    "studio": "Android Studio",
}


def detect_development_activity(
    processes: Iterable[Any] | None = None,
) -> ActivityObservation:
    running = processes if processes is not None else psutil.process_iter(["name"])
    try:
        return detect_mapped_activity(running, IDE_PROCESSES)
    except PermissionError:
        return ActivityObservation(mode="unknown")
