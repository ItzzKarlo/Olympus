import difflib
import hashlib
import json
from pathlib import Path
import re
import secrets
from threading import RLock
from datetime import datetime, timezone
import tomllib
import fcntl
from contextlib import contextmanager

from olympus_core.config import parse_core_config
from olympus_core.monitoring.config import parse_monitoring_config
from .auth import ControlError
from .redact import redact, SENSITIVE
from .storage import atomic_write, read_private

FIELDS = {
    "media.local_stale_seconds": (int, float), "media.cloud_stale_seconds": (int, float),
    "football.live_scores_confirmed": bool,
    "news.presentation.global_cooldown_seconds": (int, float),
    "news.presentation.minimum_dwell_seconds": (int, float),
    "night.enabled": bool, "night.weekday_start": str, "night.weekend_start": str, "night.end": str,
    "weather.enabled": bool, "weather.poll_minutes": (int, float),
    "calendar.enabled": bool, "calendar.poll_minutes": (int, float),
    "football.enabled": bool, "football.provider": str, "football.team_id": str, "football.poll_live_seconds": (int, float),
    "news.enabled": bool, "news.poll_minutes": (int, float), "news.presentation.important_threshold": (int, float),
    "news.presentation.major_threshold": (int, float), "network.enabled": bool, "network.poll_seconds": (int, float),
    "network.dns_hostname": str, "service_monitoring.poll_seconds": (int, float),
}


def checksum(text):
    return hashlib.sha256(text.encode()).hexdigest()


def has_secrets(data):
    if isinstance(data, dict):
        return any((SENSITIVE.search(k) and isinstance(v, str) and v and not k.endswith("_env")) or has_secrets(v) for k, v in data.items())
    if isinstance(data, list):
        return any(has_secrets(v) for v in data)
    return False


def safe_text(text):
    # A raw editor cannot safely round-trip arbitrary multiline TOML secrets.
    # Lock such files rather than dropping/redelivering their values.
    try:
        if has_secrets(tomllib.loads(text)):
            return "# Inline credentials detected. Move credentials to secrets.env using local administration before editing in Control.\n", False
    except tomllib.TOMLDecodeError:
        return "# Invalid TOML. Repair locally; raw content withheld to avoid secret disclosure.\n", False
    cleaned = redact(text)
    return cleaned, cleaned == text


class ConfigEditor:
    def __init__(self, path: Path, history: Path):
        # Resolve only the trusted deployment symlink once, never an API-supplied path.
        self.path, self.history, self.lock = path.resolve(), history, RLock()
        self.restart_required = False

    @contextmanager
    def transaction(self):
        with self.lock:
            self.history.mkdir(mode=0o700, parents=True, exist_ok=True)
            lockfile = self.history / ".lock"
            import os
            fd = os.open(lockfile, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                os.close(fd)

    def load(self):
        text = read_private(self.path)
        shown, editable = safe_text(text)
        data = tomllib.loads(text) if editable else {}
        fields = {}
        for key in FIELDS:
            item = data
            for segment in key.split("."):
                item = item.get(segment) if isinstance(item, dict) else None
            fields[key] = item
        return dict(text=shown, checksum=checksum(text), editable=editable, fields=fields, restart_required=self.restart_required)

    def validate(self, text):
        if len(text.encode()) > 262144:
            raise ControlError("config_size", "Config exceeds 256 KiB")
        try:
            data = tomllib.loads(text)
            if has_secrets(data) or redact(text) != text:
                raise ValueError("Keep credentials in secrets.env, outside the Control editor")
            settings = parse_core_config(data)
            parse_monitoring_config(data)
            if not settings.security.require_agent_auth:
                raise ValueError("Agent authentication must remain enabled")
            for key, kind in FIELDS.items():
                value = data
                for segment in key.split("."):
                    value = value.get(segment) if isinstance(value, dict) else None
                if value is not None and (not isinstance(value, kind) or (kind != bool and isinstance(value, bool))):
                    raise ValueError(f"Incorrect type for {key}")
                if value is not None and key.endswith(("_seconds", "_minutes")) and value <= 0:
                    raise ValueError(f"{key} must be positive")
                if value is not None and key.endswith("_threshold") and not 0 <= value <= 1:
                    raise ValueError(f"{key} must be between 0 and 1")
            if settings.calendar.enabled and not settings.calendar.configured:
                raise ValueError("Calendar credentials/provider are incomplete; configure credentials locally")
            if settings.football.enabled and not settings.football.configured:
                raise ValueError("Football credentials/provider are incomplete; configure credentials locally")
            if settings.weather.enabled and not settings.weather.configured:
                raise ValueError("Weather coordinates are incomplete")
            if settings.news.enabled and not settings.news.configured:
                raise ValueError("News requires usable feeds or a fixture")
        except (ValueError, TypeError, KeyError) as error:
            raise ControlError("invalid_config", redact(str(error)))
        return data

    def patch(self, text, changes):
        if not isinstance(changes, dict) or not set(changes) <= FIELDS.keys():
            raise ControlError("invalid_fields", "Unknown structured config field")
        tomllib.loads(text)
        for key, value in changes.items():
            section, leaf = key.rsplit(".", 1)
            lines = text.splitlines(keepends=True)
            header = re.compile(r"^\s*\[" + re.escape(section) + r"\]\s*(?:#.*)?$")
            start = next((i + 1 for i, line in enumerate(lines) if header.match(line.strip())), None)
            assignment = f"{leaf} = {json.dumps(value)}\n"
            if start is None:
                text += f"\n[{section}]\n{assignment}"
                continue
            end = next((i for i in range(start, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
            index = next((i for i in range(start, end) if re.match(r"^\s*" + re.escape(leaf) + r"\s*=", lines[i])), end)
            if index < end:
                lines[index] = assignment
            else:
                lines.insert(index, assignment)
            text = "".join(lines)
        self.validate(text)
        return text

    def preview(self, text, expected):
        old = read_private(self.path)
        if checksum(old) != expected:
            raise ControlError("conflict", "Config changed since load. Reload before applying.", 409)
        if not safe_text(old)[1]:
            raise ControlError("locked_config", "Existing config needs local credential/syntax cleanup", 409)
        self.validate(text)
        return {"text": text, "diff": "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), fromfile="current", tofile="proposed")), "checksum": expected}

    def apply(self, text, expected):
        with self.transaction():
            self.preview(text, expected)
            old = read_private(self.path)
            name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4) + ".toml"
            atomic_write(self.history / name, old)
            # Check again after backup; cooperating writers also take the lock.
            if checksum(read_private(self.path)) != expected:
                raise ControlError("conflict", "Config changed while saving", 409)
            atomic_write(self.path, text)
            self.restart_required = True
            return {"backup": name, "checksum": checksum(text), "restart_required": True}

    def list_history(self):
        if not self.history.exists():
            return []
        return [{"name": p.name, "size": p.stat().st_size, "timestamp": p.stat().st_mtime, "checksum": checksum(read_private(p))} for p in sorted(self.history.glob("*.toml"), reverse=True)[:100] if not p.is_symlink() and p.is_file()]

    def historical(self, name):
        if not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{8}\.toml", name):
            raise ControlError("history_name", "Invalid history entry")
        return read_private(self.history / name)
