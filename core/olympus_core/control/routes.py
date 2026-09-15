import asyncio
from dataclasses import asdict
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import Field

from olympus_core.persistence.backup import create_backup, prune_backups
from olympus_core.release import release_info, release_root, VERSION_PATTERN
from .auth import Auth, COOKIE, ControlError, SESSION_SECONDS
from .config_api import ConfigEditor
from .overrides import OverrideRequest, OverrideStore, StrictModel
from .redact import redact
from .services import Services
from .storage import atomic_write, read_private

logger = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def ok(data=None, status=200):
    return JSONResponse({"ok": True, "data": data}, status_code=status)


class Login(StrictModel):
    password: str = Field(min_length=1, max_length=1024)


class ConfigInput(StrictModel):
    text: str = Field(max_length=262144)
    checksum: str = Field(min_length=64, max_length=64)
    confirm: bool = False


class StructuredInput(ConfigInput):
    changes: dict


class Confirm(StrictModel):
    confirm: bool


class Enrollment(StrictModel):
    label: str = Field(default="Control enrollment", max_length=120)
    ttl_minutes: int = Field(default=10, ge=1, le=60)


class Restore(StrictModel):
    name: str = Field(max_length=80)
    checksum: str = Field(min_length=64, max_length=64)
    confirm: bool = False


class Control:
    def __init__(self, settings, state_service, display_hub, devices, enrollment, publish,
                 runtime=None, credentials=None, config=None, history=None, services=None):
        self.settings, self.state_service, self.hub = settings, state_service, display_hub
        self.devices, self.enrollment, self.publish = devices, enrollment, publish
        self.runtime = runtime or Path(os.getenv("OLYMPUS_CONTROL_RUNTIME", "/run/olympus-control"))
        self.auth = Auth(credentials or Path(os.getenv("OLYMPUS_CONTROL_CREDENTIALS", "/etc/olympus/control.json")), self.runtime)
        self.overrides = OverrideStore(self.runtime / "control-overrides.json")
        self.config = ConfigEditor(config or Path(os.getenv("OLYMPUS_CONFIG", "config.toml")), history or settings.backup.resolved_directory / "config")
        self.services = services or Services()
        self.started = time.monotonic()
        self.action_lock = asyncio.Lock()
        self.backup_lock = asyncio.Lock()
        state_service.control_overrides = self.overrides

    async def watch(self):
        """Expiry and emergency unlink propagate over the normal Display transport."""
        previous = None
        while True:
            try:
                doc = self.overrides.read()
                current = doc.model_dump_json() if doc else None
                if current != previous:
                    await self.publish()
                    previous = current
            except Exception:
                logger.exception("Control override watcher failed; normal Core remains available")
            await asyncio.sleep(1)

    def status(self):
        doc = self.overrides.read()
        real = self.state_service.current()
        presented = self.state_service.display_state()
        return redact(dict(release=asdict(release_info()), release_path=str(release_root().resolve()), core_uptime_seconds=int(time.monotonic() - self.started),
            local_time=datetime.now(ZoneInfo(self.settings.timezone)).isoformat(), night_schedule={k: str(v) for k, v in asdict(self.settings.night).items()},
            auto_night=real.time_policy.is_night, effective_night=presented.time_policy.is_night,
            real_scene=real.mode.value, scene=presented.mode.value, display_clients=self.hub.connection_count,
            kiosk_url="http://127.0.0.1:8000/ (default; installed kiosk.env may override)",
            overrides=doc.model_dump(mode="json") if doc else None,
            real=real.model_dump(mode="json"), presented=presented.model_dump(mode="json"), restart_required=self.config.restart_required))

    def releases(self):
        root = Path("/opt/olympus/releases")
        installed = []
        if root.is_dir():
            installed = [dict(path=str(p), **asdict(release_info(p))) for p in sorted(root.iterdir()) if p.is_dir() and not p.is_symlink() and VERSION_PATTERN.fullmatch(p.name)]
        return dict(active=str(release_root().resolve()), **asdict(release_info()), installed=installed)

    def backups(self):
        directory = self.settings.backup.resolved_directory
        entries = [dict(name=p.name, size=p.stat().st_size, timestamp=p.stat().st_mtime) for p in sorted(directory.glob("*.db"), reverse=True) if p.is_file() and not p.is_symlink()]
        return dict(directory=str(directory), retention_days=self.settings.backup.retention_days, count=len(entries), entries=entries[:100])

    async def deferred_action(self, service, action):
        async with self.action_lock:
            await asyncio.sleep(.3)  # BackgroundTasks executes only after the HTTP body was sent.
            try:
                result = await asyncio.to_thread(self.services.action, service, action)
                atomic_write(self.runtime / "last-action.json", json.dumps(result))
            except ControlError as error:
                atomic_write(self.runtime / "last-action.json", json.dumps({"error": redact(error.message)}))
                logger.warning("Control service action failed: %s", error.code)


def install_control(app: FastAPI, control: Control):
    @app.exception_handler(ControlError)
    async def control_error(request, error):
        return JSONResponse({"ok": False, "error": {"code": error.code, "message": redact(error.message)}}, status_code=error.status)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        is_control = request.url.path.startswith(("/api/control", "/control"))
        if is_control and request.method not in {"GET", "HEAD"}:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 300000:
                    return JSONResponse({"ok": False, "error": {"code": "too_large", "message": "Request too large"}}, status_code=413)
            request._body = bytes(body)
        try:
            response = await call_next(request)
        except Exception:
            if not is_control:
                raise
            logger.exception("Control request failed")
            response = JSONResponse({"ok": False, "error": {"code": "unavailable", "message": "Control operation failed. Inspect approved Core logs."}}, status_code=503)
        if is_control:
            response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
            if response.status_code == 422:
                response = JSONResponse({"ok": False, "error": {"code": "invalid_request", "message": "Request schema validation failed"}}, status_code=422, headers={k: v for k, v in response.headers.items() if k != "content-length"})
        return response

    public = APIRouter(prefix="/api/control")
    private = APIRouter(prefix="/api/control", dependencies=[Depends(control.auth.require)])

    @public.post("/login")
    def login(body: Login, request: Request):
        control.auth.origin(request)
        token, csrf = control.auth.login(body.password, request.client.host if request.client else "unknown")
        # Replace an existing browser session rather than retaining a fixed identifier.
        control.auth.logout(request)
        response = ok({"csrf": csrf})
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=request.url.scheme == "https", samesite="strict", path="/")
        return response

    @private.get("/session")
    def session(request: Request):
        return ok({"csrf": control.auth.session(request)["csrf"]})

    @private.post("/logout")
    def logout(request: Request):
        control.auth.logout(request)
        response = ok()
        response.delete_cookie(COOKIE, path="/")
        return response

    @private.get("/status")
    def status():
        return ok(control.status())

    @private.get("/overrides")
    def overrides():
        doc = control.overrides.read()
        return ok(doc.model_dump(mode="json") if doc else None)

    @private.put("/overrides")
    async def put_overrides(body: OverrideRequest):
        doc = control.overrides.write(body)
        await control.publish()
        # A goal is a real normal Display event, not a second transport.
        if body.simulation and body.simulation.kind == "football" and body.simulation.variant in {"bayern-goal", "opponent-goal"}:
            from olympus_core.models.football import FootballDisplayEvent
            from datetime import timezone
            import secrets
            presented = control.state_service.display_state()
            matchday = presented.football.matchday
            await control.hub.broadcast_event(FootballDisplayEvent(id="control-" + secrets.token_hex(8), type="football.goal", timestamp=datetime.now(timezone.utc), source="control-simulation", payload={"for_tracked_team": body.simulation.variant == "bayern-goal", "match": matchday.match.model_dump(mode="json"), "event": matchday.events[0].model_dump(mode="json")}))
        return ok(doc.model_dump(mode="json") if doc else None)

    @private.delete("/overrides")
    async def reset_overrides():
        control.overrides.clear()
        await control.publish()
        return ok()

    @private.get("/services")
    def services():
        last = None
        try:
            last = json.loads(read_private(control.runtime / "last-action.json"))
        except (OSError, ValueError):
            pass
        return ok({"units": control.services.states(), "last_action": last})

    @private.post("/services/{service}/{action}")
    async def action(service: str, action: str, body: Confirm, background: BackgroundTasks):
        control.services.validate(service, action)
        if not body.confirm:
            raise ControlError("confirmation", "Explicit confirmation required")
        if service == "core" and action in {"restart", "stop"}:
            background.add_task(control.deferred_action, service, action)
            return ok({"scheduled": True, "action": action, "message": "Request received; reconnect and inspect status for outcome."}, 202)
        async with control.action_lock:
            return ok(await asyncio.to_thread(control.services.action, service, action))

    @private.get("/config")
    def config():
        return ok(control.config.load())

    @private.post("/config/validate")
    def validate(body: ConfigInput):
        return ok(control.config.preview(body.text, body.checksum))

    @private.post("/config/structured")
    def structured(body: StructuredInput):
        return ok(control.config.preview(control.config.patch(body.text, body.changes), body.checksum))

    @private.post("/config/apply")
    def apply(body: ConfigInput):
        if not body.confirm:
            raise ControlError("confirmation", "Explicit confirmation required")
        return ok(control.config.apply(body.text, body.checksum))

    @private.get("/config/history")
    def history():
        return ok(control.config.list_history())

    @private.get("/config/history/{name}")
    def historical(name: str):
        from .config_api import safe_text
        import difflib
        text, _ = safe_text(control.config.historical(name))
        current = control.config.load()["text"]
        return ok({"text": text, "diff": "".join(difflib.unified_diff(current.splitlines(True), text.splitlines(True), fromfile="current", tofile=name))})

    @private.post("/config/restore")
    def restore(body: Restore):
        if not body.confirm:
            raise ControlError("confirmation", "Explicit confirmation required")
        return ok(control.config.apply(control.config.historical(body.name), body.checksum))

    @private.get("/logs")
    def logs(unit: str = "core", count: int = 100, priority: str = "7", text: str = ""):
        if len(text) > 200:
            raise ControlError("filter", "Filter too long")
        rows = redact(control.services.logs(unit, count, priority))
        return ok([r for r in rows if text.casefold() in str(r["message"]).casefold()])

    @private.get("/devices")
    def devices():
        online = control.state_service.current().machines
        return ok([dict(agent_id=d.agent_id, display_name=d.display_name, platform=d.platform, fingerprint=d.public_key_fingerprint, last_seen=d.last_seen_at.isoformat() if d.last_seen_at else None, revoked=d.revoked, online=bool(online.get(d.agent_id) and online[d.agent_id].online)) for d in control.devices.list()])

    @private.post("/enrollment")
    def enrollment(body: Enrollment):
        token = control.enrollment.create(body.ttl_minutes, body.label)
        return ok(dict(token=token.token, expires_at=token.expires_at.isoformat(), label=body.label, single_use=True))

    @private.post("/devices/{agent_id}/revoke")
    def revoke(agent_id: str, body: Confirm):
        if not body.confirm:
            raise ControlError("confirmation", "Explicit confirmation required")
        if not control.devices.revoke(agent_id):
            raise ControlError("not_found", "Active device not found", 404)
        return ok({"revoked": True, "note": "Existing connections recheck trust on the configured revocation interval."})

    @private.get("/backups")
    def backups():
        return ok(control.backups())

    @private.post("/backups")
    async def backup():
        async with control.backup_lock:
            path = await asyncio.to_thread(create_backup, control.settings.persistence.resolved_database_path, control.settings.backup.resolved_directory)
            await asyncio.to_thread(prune_backups, control.settings.backup.resolved_directory, control.settings.backup.retention_days)
            return ok({"created": path.name})

    @private.get("/releases")
    def releases():
        return ok(control.releases())

    @private.get("/diagnostics")
    def diagnostics():
        status = control.status()
        try:
            status["units"] = control.services.states()
        except ControlError as error:
            status["units_error"] = error.code
        try:
            loaded = control.config.load()
            control.config.validate(loaded["text"])
            status["config"] = {"valid": True, "checksum": loaded["checksum"]}
        except (ControlError, OSError) as error:
            status["config"] = {"valid": False, "error": redact(getattr(error, "message", "Config unavailable"))}
        return ok({"bundle": json.dumps(redact(status), indent=2)})

    app.include_router(public)
    app.include_router(private)

    @app.get("/control", include_in_schema=False)
    def redirect_control():
        return RedirectResponse("/control/")

    @app.get("/control/", include_in_schema=False)
    def index(request: Request):
        try:
            control.auth.session(request)
        except ControlError:
            return RedirectResponse("/control/login")
        return FileResponse(STATIC / "index.html")

    @app.get("/control/login", include_in_schema=False)
    def login_page():
        return FileResponse(STATIC / "login.html")

    @app.get("/control/static/{name}", include_in_schema=False)
    def asset(name: str):
        if name not in {"control.css", "control.js", "login.js"}:
            raise ControlError("not_found", "Not found", 404)
        return FileResponse(STATIC / name)
