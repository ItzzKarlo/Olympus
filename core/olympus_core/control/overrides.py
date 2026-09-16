from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
import time
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .storage import atomic_write, read_private

logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Environment(StrictModel):
    enabled: Literal["auto", "on", "off"] = "auto"
    intensity: Literal["auto", "full", "calm", "reduced", "minimal"] = "auto"
    animations: Literal["auto", "on", "off"] = "auto"
    reduced_motion: bool = False


class Simulation(StrictModel):
    kind: Literal["news", "system", "football", "media", "gaming", "development"]
    variant: str = Field(default="", max_length=40)
    title: str = Field(default="Olympus simulation", max_length=240)
    source: str = Field(default="Control", max_length=100)
    artist: str = Field(default="Olympus", max_length=120)
    album: str = Field(default="Control sessions", max_length=120)
    machine: str = Field(default="Simulated Zeus", max_length=100)
    application: str = Field(default="Code", max_length=100)
    cpu: float = Field(default=25, ge=0, le=100)
    ram: float = Field(default=40, ge=0, le=100)
    progress: int = Field(default=30, ge=0, le=86400)
    duration: int = Field(default=240, ge=1, le=86400)
    fps: float = Field(default=60, gt=0, le=1000)

    @field_validator("variant")
    @classmethod
    def variant_valid(cls, value, info):
        variants = {
            "news": {"", "notable", "important", "major", "critical", "outage", "recovery"},
            "system": {"", "blocker", "warning", "critical", "dns-degraded", "dns-down", "gateway-down", "internet-down", "service-down", "agent-offline"},
            "football": {"", "pre-match", "kickoff", "live", "bayern-goal", "opponent-goal", "halftime", "second-half", "full-time", "victory", "defeat", "draw", "outage", "recovery", "score-correction"},
            "media": {"", "playing", "paused", "local", "outage", "recovery"},
            "gaming": {"", "fortnite", "minecraft", "among-us", "goat-simulator", "custom"},
            "development": {"", "active"},
        }
        if value not in variants.get(info.data.get("kind"), set()):
            raise ValueError("Unknown simulation variant")
        return value


class OverrideRequest(StrictModel):
    seasonal_date: date | None = None
    day_night: Literal["auto", "day", "night"] = "auto"
    scene: Literal["auto", "idle", "night", "media", "development", "gaming", "matchday", "news"] = "auto"
    simulation: Simulation | None = None
    environment: Environment = Field(default_factory=Environment)
    ttl_minutes: Literal[15, 30, 60, 0] = 30

    @property
    def active(self):
        return bool(self.seasonal_date or self.day_night != "auto" or self.scene != "auto" or self.simulation or self.environment != Environment())


class OverrideDocument(StrictModel):
    settings: OverrideRequest
    created_at: float
    expires_at: float | None


class OverrideStore:
    def __init__(self, path: Path, clock=time.time):
        self.path, self.clock, self.lock = path, clock, RLock()
        self._bad_signature = None

    def read(self) -> OverrideDocument | None:
        with self.lock:
            try:
                raw = read_private(self.path, 16384)
                doc = OverrideDocument.model_validate_json(raw)
                if doc.expires_at is not None and doc.expires_at <= self.clock():
                    self.path.unlink(missing_ok=True)
                    return None
                return doc if doc.settings.active else None
            except FileNotFoundError:
                return None
            except (OSError, ValueError) as error:
                signature = str(type(error))
                if signature != self._bad_signature:
                    logger.warning("Ignoring invalid Control overrides (%s)", type(error).__name__)
                    self._bad_signature = signature
                return None

    def write(self, settings: OverrideRequest):
        with self.lock:
            if not settings.active:
                self.clear()
                return None
            now = self.clock()
            doc = OverrideDocument(settings=settings, created_at=now, expires_at=now + settings.ttl_minutes * 60 if settings.ttl_minutes else None)
            atomic_write(self.path, doc.model_dump_json())
            self._bad_signature = None
            return doc

    def clear(self):
        with self.lock:
            self.path.unlink(missing_ok=True)

    def apply(self, real):
        doc = self.read()
        if doc is None:
            return real
        from .simulation import present
        try:
            return present(real, doc)
        except Exception:
            logger.exception("Control presentation failed; preserving real state")
            return real
