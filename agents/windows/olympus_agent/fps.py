from collections import deque
import csv
import os
from pathlib import Path
import time

from olympus_agent_common.activity import normalize_process_name


class PresentMonCsvFpsProvider:
    """Reads optional external PresentMon CSV output without touching game processes."""

    def __init__(self, path: Path, stale_seconds: float = 6.0) -> None:
        self._path = path
        self._stale_seconds = stale_seconds

    def latest_fps(self, process_name: str) -> float | None:
        try:
            if time.time() - self._path.stat().st_mtime > self._stale_seconds:
                return None
            with self._path.open(encoding="utf-8-sig", newline="") as file:
                header = file.readline()
                rows = deque(file, maxlen=180)
        except OSError:
            return None
        if not header or not rows:
            return None
        target = normalize_process_name(process_name)
        frame_times: list[float] = []
        for row in csv.DictReader([header, *rows]):
            application = row.get("Application") or ""
            if normalize_process_name(application) != target:
                continue
            raw = row.get("FrameTime") or row.get("MsBetweenPresents")
            try:
                frame_time = float(raw or 0)
            except ValueError:
                continue
            if 1 <= frame_time <= 1000:
                frame_times.append(frame_time)
        if not frame_times:
            return None
        average = sum(frame_times[-60:]) / len(frame_times[-60:])
        return round(1000 / average, 1)


def fps_provider_from_environment() -> PresentMonCsvFpsProvider | None:
    value = os.getenv("OLYMPUS_PRESENTMON_CSV")
    return PresentMonCsvFpsProvider(Path(value).expanduser()) if value else None
