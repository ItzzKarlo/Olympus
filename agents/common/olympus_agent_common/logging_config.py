from logging.handlers import RotatingFileHandler
import logging
import os
from pathlib import Path
import re


TOKEN_PATTERN = re.compile(r"OLYMPUS-[A-Za-z0-9_-]{16,}")


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        token = os.environ.get("OLYMPUS_ENROLLMENT_TOKEN")
        if token:
            message = message.replace(token, "[REDACTED]")
        record.msg = TOKEN_PATTERN.sub("[REDACTED]", message)
        record.args = ()
        return True


def configure_logging(background: bool, log_dir: Path) -> Path | None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    secret_filter = SecretRedactionFilter()
    log_path: Path | None = None
    if background:
        log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        log_path = log_dir / "agent.log"
        handler: logging.Handler = RotatingFileHandler(
            log_path,
            maxBytes=3 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        try:
            log_path.chmod(0o600)
        except OSError:
            pass
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(secret_filter)
    root.addHandler(handler)
    return log_path
