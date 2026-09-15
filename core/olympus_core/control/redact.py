import os
import re

SENSITIVE = re.compile(r"password|secret|token|api[_-]?key|authorization|credential", re.I)


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SENSITIVE.search(k) and not k.endswith(("_minutes", "_seconds", "_env")) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    for key, secret in os.environ.items():
        if SENSITIVE.search(key) and len(secret) >= 4:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"OLYMPUS-[A-Za-z0-9_-]{20,}", "[ENROLLMENT REDACTED]", value)
    value = re.sub(r"(?i)(Bearer\s+)[\w.+=/-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:password|secret|token|api[_-]?key|authorization)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", value)
    value = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", value)
    return value
