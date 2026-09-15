"""Fixed systemd operations, no shell and no arbitrary command/unit arguments."""
import json
import subprocess
import time
from threading import RLock
from .auth import ControlError

UNITS = {name: f"olympus-{name}.service" for name in ("core", "kiosk", "healthcheck", "backup")}
UNITS.update({"healthcheck-timer": "olympus-healthcheck.timer", "backup-timer": "olympus-backup.timer"})
LOG_UNITS = {key: value for key, value in UNITS.items() if value.endswith(".service")}
PROPERTIES = "Id,LoadState,ActiveState,SubState,Result,MainPID,NRestarts,ActiveEnterTimestamp,ExecMainStatus"


class Services:
    def __init__(self, run=subprocess.run):
        self.run = run
        self._cache = None
        self._at = 0
        self.lock = RLock()

    def command(self, args):
        try:
            result = self.run(args, capture_output=True, text=True, timeout=15, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
        except (OSError, subprocess.TimeoutExpired):
            raise ControlError("host_unavailable", "Host operation unavailable or timed out", 503)
        if result.returncode:
            # Only fixed commands; keep stderr bounded. Caller redacts before responding.
            raise ControlError("host_action_failed", result.stderr.strip()[:1200] or "Host operation failed", 502)
        return result.stdout

    def validate(self, service, action):
        if service not in UNITS or action not in {"start", "stop", "restart", "reset-failed"} or (action == "reset-failed" and service != "kiosk"):
            raise ControlError("not_allowed", "Service/action is outside the Olympus allowlist", 403)

    def action(self, service, action):
        self.validate(service, action)
        self.command(["/usr/bin/systemctl", "--no-ask-password", "--no-block", action, UNITS[service]])
        self._at = 0
        return {"accepted": True, "unit": UNITS[service], "action": action, "note": "Job submitted; inspect unit state for completion."}

    def states(self):
        with self.lock:
            if self._cache is not None and time.monotonic() - self._at < 5:
                return self._cache
            text = self.command(["/usr/bin/systemctl", "show", "--no-pager", f"--property={PROPERTIES}", *UNITS.values()])
            rows = []
            for block in text.strip().split("\n\n"):
                row = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
                if row.get("Id") in UNITS.values():
                    row["key"] = next(key for key, unit in UNITS.items() if unit == row["Id"])
                    rows.append(row)
            self._cache, self._at = rows, time.monotonic()
            return rows

    def logs(self, unit, count, priority):
        if unit not in LOG_UNITS or count not in {50, 100, 250, 500} or priority not in {"0", "1", "2", "3", "4", "5", "6", "7"}:
            raise ControlError("not_allowed", "Invalid journal selection", 403)
        text = self.command(["/usr/bin/journalctl", "--no-pager", "-q", "-o", "json", "-n", str(count), "-p", priority, "-u", LOG_UNITS[unit]])
        return [{"time": row.get("__REALTIME_TIMESTAMP"), "priority": row.get("PRIORITY", "6"), "message": row.get("MESSAGE", "")} for line in text.splitlines() if (row := json.loads(line))]
