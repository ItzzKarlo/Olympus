from collections.abc import Mapping
from typing import Any


def optional_section(**values: Any) -> dict[str, Any] | None:
    section = {key: value for key, value in values.items() if value is not None}
    return section or None


def build_telemetry(
    *,
    system: Mapping[str, Any],
    activity: Mapping[str, Any],
    storage: Mapping[str, Any] | None = None,
    network: Mapping[str, Any] | None = None,
    temperatures: Mapping[str, Any] | None = None,
    gpu: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "telemetry",
        "system": dict(system),
        "activity": dict(activity),
    }
    for name, section in (
        ("storage", storage),
        ("network", network),
        ("temperatures", temperatures),
        ("gpu", gpu),
    ):
        if section:
            payload[name] = dict(section)
    return payload
