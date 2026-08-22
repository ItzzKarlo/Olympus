from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

import psutil


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


@dataclass(frozen=True)
class ActivityObservation:
    mode: str
    application: str | None = None
    process_name: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _normalized_process_name(name: str) -> str:
    normalized = name.casefold().strip()
    if normalized.endswith(".exe"):
        normalized = normalized[:-4]
    return normalized


def detect_development_activity(
    processes: Iterable[Any] | None = None,
) -> ActivityObservation:
    running_processes = (
        processes if processes is not None else psutil.process_iter(["name"])
    )
    try:
        for process in running_processes:
            try:
                process_name = process.info.get("name")
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            if not process_name:
                continue

            application = IDE_PROCESSES.get(_normalized_process_name(process_name))
            if application is not None:
                return ActivityObservation(
                    mode="development",
                    application=application,
                    process_name=process_name,
                )
    except PermissionError:
        return ActivityObservation(mode="unknown")

    return ActivityObservation(mode="idle")
