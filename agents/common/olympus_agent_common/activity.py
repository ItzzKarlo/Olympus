from collections.abc import Iterable, Mapping
from typing import Any

from olympus_agent_common.protocol import ActivityObservation


def normalize_process_name(name: str) -> str:
    normalized = name.casefold().strip()
    return normalized[:-4] if normalized.endswith(".exe") else normalized


def detect_mapped_activity(
    processes: Iterable[Any],
    process_map: Mapping[str, str],
) -> ActivityObservation:
    for process in processes:
        try:
            process_name = process.info.get("name")
        except Exception:
            continue
        if not process_name:
            continue
        application = process_map.get(normalize_process_name(process_name))
        if application is not None:
            return ActivityObservation(
                mode="development",
                application=application,
                process_name=process_name,
            )
    return ActivityObservation(mode="idle")
