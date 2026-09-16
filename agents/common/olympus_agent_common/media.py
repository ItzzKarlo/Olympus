"""Optional, read-only desktop media observations. No listener or mandatory SDK."""
import asyncio
from datetime import datetime, timezone
import os
import json
import hashlib
import math
import sys
import time


def normalize_mpris(player: str, properties: dict) -> dict:
    def unwrap(value):
        if hasattr(value, "value"):
            return unwrap(value.value)
        if isinstance(value, dict):
            return {k: unwrap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [unwrap(v) for v in value]
        return value
    data = unwrap(properties)
    metadata = data.get("Metadata", {})
    status = str(data.get("PlaybackStatus", "unknown")).lower()
    title = metadata.get("xesam:title")
    track = None
    if isinstance(title, str) and title:
        track = {"id": metadata.get("mpris:trackid"), "title": title,
                 "artists": [{"name": a} for a in metadata.get("xesam:artist", []) if isinstance(a, str)],
                 "duration_ms": max(0, int(metadata.get("mpris:length", 0)) // 1000)}
        if metadata.get("xesam:album"):
            art = metadata.get("mpris:artUrl")
            track["album"] = {"name": metadata["xesam:album"],
                              "artwork_url": art if isinstance(art, str) and art.startswith("https://") else None}
    if track is not None and not track["id"]:
        identity = json.dumps(track, sort_keys=True, ensure_ascii=False)
        track["id"] = "metadata:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    return {"provider": player.removeprefix("org.mpris.MediaPlayer2."), "source": "local",
            "session_id": player, "available": True, "is_playing": status == "playing",
            "playback_status": status if status in {"playing", "paused", "stopped"} else "unknown",
            "observed_at": datetime.now(timezone.utc).isoformat(), "track": track,
            "progress_ms": max(0, int(data.get("Position", 0)) // 1000),
            "capabilities": ["metadata"] + (["position"] if "Position" in data else [])}


class LocalMediaCollector:
    def __init__(self):
        self._bus = None
        self._next_poll = 0.0
        self._cached = []
        self.health = "disabled"
        try:
            interval = float(os.getenv("OLYMPUS_LOCAL_MEDIA_POLL_SECONDS", "5"))
            self.interval = max(5.0, interval) if math.isfinite(interval) else 5.0
        except ValueError:
            self.interval = 5.0
        self.enabled = os.getenv("OLYMPUS_LOCAL_MEDIA_ENABLED", "").lower() in {"1", "true", "yes"}

    async def sample(self) -> list[dict]:
        if not self.enabled:
            return []
        if time.monotonic() < self._next_poll:
            return self._cached
        self._next_poll = time.monotonic() + self.interval
        try:
            self._cached = await asyncio.wait_for(self._collect(), 3.0)
            self.health = "available"
        except ImportError:
            self.health = "unsupported_missing_sdk"
            self._cached = []
            self._next_poll = time.monotonic() + 60
        except Exception:
            self.health = "unavailable"
            self._cached = []
            self._next_poll = time.monotonic() + 15
            self.close()
        return self._cached

    async def _collect(self):
        if sys.platform.startswith("linux"):
            from dbus_next.aio import MessageBus
            from dbus_next import Message, MessageType
            if self._bus is None:
                self._bus = await MessageBus().connect()  # user session bus only
            names = await self._bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                                                 interface="org.freedesktop.DBus", member="ListNames"))
            sessions = []
            for name in sorted(names.body[0]):
                if not name.startswith("org.mpris.MediaPlayer2."):
                    continue
                reply = await self._bus.call(Message(destination=name, path="/org/mpris/MediaPlayer2",
                    interface="org.freedesktop.DBus.Properties", member="GetAll", signature="s",
                    body=["org.mpris.MediaPlayer2.Player"]))
                if reply.message_type != MessageType.ERROR:
                    sessions.append(normalize_mpris(name, reply.body[0]))
                if len(sessions) >= 16:
                    break
            return sessions
        if sys.platform == "win32":
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            sessions = []
            for session in list(manager.get_sessions())[:16]:
                properties = await session.try_get_media_properties_async()
                playback = session.get_playback_info()
                timeline = session.get_timeline_properties()
                # Windows enum: Closed=0, Opened=1, Changing=2, Stopped=3, Playing=4, Paused=5.
                status = {3: "Stopped", 4: "Playing", 5: "Paused"}.get(int(playback.playback_status), "unknown")
                position = timeline.position.total_seconds()
                updated = timeline.last_updated_time
                if status == "Playing" and updated.tzinfo is not None:
                    position += max(0, (datetime.now(timezone.utc) - updated).total_seconds())
                position = min(position, timeline.end_time.total_seconds())
                sessions.append(normalize_mpris(session.source_app_user_model_id, {
                    "PlaybackStatus": status, "Position": int(position * 1_000_000),
                    "Metadata": {"xesam:title": properties.title, "xesam:artist": [properties.artist] if properties.artist else [],
                                 "xesam:album": properties.album_title,
                                 "mpris:length": int((timeline.end_time - timeline.start_time).total_seconds() * 1_000_000)}}))
            return sessions
        if sys.platform == "darwin":
            # Fixed JXA program, no interpolation or shell. Do not launch Spotify.
            self._next_poll = time.monotonic() + max(10.0, self.interval)
            script = '''const app = Application("com.spotify.client");
if (!app.running()) { JSON.stringify(null); } else {
 const t = app.currentTrack();
 JSON.stringify({PlaybackStatus: app.playerState(), Position: app.playerPosition() * 1000000,
 Metadata: {"mpris:trackid": t.id(), "xesam:title": t.name(), "xesam:artist": [t.artist()],
 "xesam:album": t.album(), "mpris:length": t.duration() * 1000, "mpris:artUrl": t.artworkUrl()}});
}'''
            process = await asyncio.create_subprocess_exec("/usr/bin/osascript", "-l", "JavaScript", "-e", script,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            try:
                stdout, _ = await process.communicate()
                if process.returncode:
                    raise RuntimeError("Spotify scripting unavailable")
                data = json.loads(stdout)
                return [normalize_mpris("spotify", data)] if data else []
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
        raise ImportError("No supported media adapter on this platform")

    def close(self):
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None
