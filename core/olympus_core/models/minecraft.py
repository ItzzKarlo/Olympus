from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MinecraftConnection(BaseModel):
    type: Literal["singleplayer", "multiplayer"]
    server_name: str | None = None
    server_address: str | None = None
    world_name: str | None = None


class MinecraftWorld(BaseModel):
    dimension: str = Field(min_length=1, max_length=256)
    biome: str = Field(min_length=1, max_length=256)


class MinecraftPosition(BaseModel):
    x: float | None = None
    y: float | None = None
    z: float | None = None


class MinecraftExperience(BaseModel):
    level: int | None = Field(default=None, ge=0)
    progress: float | None = Field(default=None, ge=0, le=1)


class MinecraftPlayer(BaseModel):
    position: MinecraftPosition
    health: float | None = Field(default=None, ge=0)
    max_health: float | None = Field(default=None, gt=0)
    food: int | None = Field(default=None, ge=0)
    max_food: int | None = Field(default=None, gt=0)
    armor: int | None = Field(default=None, ge=0)
    experience: MinecraftExperience | None = None
    game_mode: Literal[
        "survival", "creative", "adventure", "spectator", "unknown"
    ] = "unknown"


class MinecraftState(BaseModel):
    connection: MinecraftConnection
    world: MinecraftWorld
    player: MinecraftPlayer
    observed_at: datetime
    low_health: bool = False
