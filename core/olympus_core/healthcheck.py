import argparse
import json
from pathlib import Path
import subprocess
from typing import Callable
from urllib.request import urlopen

from olympus_core.config import load_core_config


Restart = Callable[[], None]


class HealthWatchdog:
    def __init__(self, state_path: Path, threshold: int, restart: Restart) -> None:
        if threshold < 2:
            raise ValueError("Health failure threshold must be at least two")
        self.state_path = state_path
        self.threshold = threshold
        self.restart = restart

    def _read_failures(self) -> int:
        try:
            return max(0, int(self.state_path.read_text(encoding="ascii").strip()))
        except (FileNotFoundError, OSError, ValueError):
            return 0

    def _write_failures(self, failures: int) -> None:
        self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(f"{failures}\n", encoding="ascii")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.state_path)

    def record(self, healthy: bool) -> tuple[int, bool]:
        if healthy:
            self._write_failures(0)
            return 0, False
        failures = self._read_failures() + 1
        self._write_failures(failures)
        if failures < self.threshold:
            return failures, False
        self.restart()
        self._write_failures(0)
        return failures, True


def core_is_healthy(url: str, timeout: float) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return False
            value = json.loads(response.read())
            return value.get("status") == "ok" and value.get("persistence") == "healthy"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def restart_core() -> None:
    subprocess.run(
        ["systemctl", "restart", "olympus-core.service"],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Thresholded local Olympus Core watchdog")
    parser.add_argument("--url")
    parser.add_argument("--state", type=Path, default=Path("/run/olympus/health-failures"))
    parser.add_argument("--threshold", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args(argv)
    try:
        url = args.url or f"http://127.0.0.1:{load_core_config().server.port}/health"
        watchdog = HealthWatchdog(args.state, args.threshold, restart_core)
        failures, restarted = watchdog.record(core_is_healthy(url, args.timeout))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Olympus healthcheck failed: {error}")
        return 1
    if restarted:
        print(f"Olympus Core restarted after {failures} consecutive health failures.")
    elif failures:
        print(f"Olympus Core health failure {failures}/{args.threshold}; no restart yet.")
    else:
        print("Olympus Core healthy; failure counter reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
