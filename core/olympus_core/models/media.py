from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class MediaArtist(BaseModel):
    id: str | None = None
    name: str


class MediaAlbum(BaseModel):
    id: str | None = None
    name: str
    artwork_url: str | None = None


class MediaTrack(BaseModel):
    id: str | None = None
    title: str
    artists: list[MediaArtist] = Field(default_factory=list)
    duration_ms: int = Field(default=0, ge=0)
    album: MediaAlbum | None = None


class MediaContext(BaseModel):
    type: str
    name: str | None = None
    uri: str | None = None


class MediaQueueTrack(BaseModel):
    id: str | None = None
    title: str
    artists: list[str] = Field(default_factory=list)
    duration_ms: int = Field(default=0, ge=0)
    artwork_url: str | None = None


class MediaState(BaseModel):
    provider: Literal["spotify"] = "spotify"
    available: bool = True
    is_playing: bool = False
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    progress_ms: int = Field(default=0, ge=0)
    track: MediaTrack | None = None
    context: MediaContext | None = None
    queue: list[MediaQueueTrack] = Field(default_factory=list, max_length=3)

    @classmethod
    def unavailable(cls) -> "MediaState":
        return cls(available=False)
