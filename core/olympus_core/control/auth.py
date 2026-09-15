import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from threading import RLock

from fastapi import Request
from .storage import atomic_write, read_private

COOKIE = "olympus_control"
SESSION_SECONDS = 8 * 3600


class ControlError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def password_record(password: str) -> dict:
    if not 12 <= len(password) <= 1024:
        raise ValueError("Use a password between 12 and 1024 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return {"salt": salt.hex(), "password_hash": digest.hex(), "generation": secrets.token_hex(16)}


class Auth:
    def __init__(self, credentials: Path, runtime: Path, clock=time.time):
        self.credentials, self.sessions_path, self.clock = credentials, runtime / "sessions.json", clock
        self.attempts: dict[str, list[float]] = {}
        self.lock = RLock()

    def _credentials(self):
        try:
            if self.credentials.stat().st_mode & 0o007:
                raise ValueError("Credentials are world accessible")
            record = json.loads(read_private(self.credentials, 4096))
            if len(bytes.fromhex(record["salt"])) != 16 or len(bytes.fromhex(record["password_hash"])) != 64:
                raise ValueError("Invalid credentials")
            return record
        except (OSError, ValueError, KeyError, TypeError):
            raise ControlError("not_configured", "Control is locked. Run the local control-password setup command.", 503)

    def _sessions(self) -> dict:
        try:
            data = json.loads(read_private(self.sessions_path))
            return {k: v for k, v in data.items() if isinstance(v, dict) and v.get("expires", 0) > self.clock()}
        except (OSError, ValueError, TypeError, AttributeError):
            return {}

    def login(self, password: str, peer: str) -> tuple[str, str]:
        with self.lock:
            now = self.clock()
            self.attempts = {k: [t for t in v if t > now - 300] for k, v in self.attempts.items() if any(t > now - 300 for t in v)}
            times = self.attempts.setdefault(peer, [])
            if len(times) >= 5 or sum(map(len, self.attempts.values())) >= 40:
                raise ControlError("rate_limited", "Too many login attempts. Wait five minutes.", 429)
            times.append(now)
            record = self._credentials()
            actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(record["salt"]), n=16384, r=8, p=1)
            if not hmac.compare_digest(actual.hex(), record["password_hash"]):
                raise ControlError("invalid_login", "Invalid credentials", 401)
            self.attempts.pop(peer, None)
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            sessions = self._sessions()
            if len(sessions) >= 64:
                sessions.pop(next(iter(sessions)))
            sessions[hashlib.sha256(token.encode()).hexdigest()] = {"csrf": csrf, "expires": now + SESSION_SECONDS, "generation": record["generation"]}
            atomic_write(self.sessions_path, json.dumps(sessions))
            return token, csrf

    def session(self, request: Request) -> dict:
        token = request.cookies.get(COOKIE, "")
        with self.lock:
            session = self._sessions().get(hashlib.sha256(token.encode()).hexdigest())
            if not session or session.get("generation") != self._credentials()["generation"]:
                raise ControlError("unauthorized", "Login required", 401)
            return session

    def require(self, request: Request) -> dict:
        session = self.session(request)
        if request.method not in {"GET", "HEAD"}:
            self.origin(request)
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
                raise ControlError("csrf", "Missing or invalid CSRF token", 403)
        return session

    @staticmethod
    def origin(request: Request):
        # Login also requires a same-origin browser POST. Never trust forwarded headers.
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if request.headers.get("origin") != expected or request.headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
            raise ControlError("origin", "Same-origin request required", 403)

    def logout(self, request: Request):
        with self.lock:
            sessions = self._sessions()
            sessions.pop(hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest(), None)
            atomic_write(self.sessions_path, json.dumps(sessions))
