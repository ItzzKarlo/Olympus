from typing import Any


GAME_MODES = {"survival", "creative", "adventure", "spectator", "unknown"}
CONNECTION_TYPES = {"singleplayer", "multiplayer"}
EVENTS = {
    "player.damage_taken",
    "player.healed",
    "player.died",
    "dimension.changed",
    "session.joined",
    "session.left",
}


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value.strip()[:256]


def _optional_number(value: Any, name: str, minimum: float | None = None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or null")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def _optional_integer(value: Any, name: str, minimum: int = 0) -> int | None:
    number = _optional_number(value, name, minimum)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"{name} must be an integer")
    return int(number)


def normalize_minecraft_state(payload: Any) -> dict[str, Any]:
    source = _object(payload, "payload")
    connection_source = _object(source.get("connection"), "connection")
    connection_type = connection_source.get("type")
    if connection_type not in CONNECTION_TYPES:
        raise ValueError("connection.type is invalid")
    connection = {
        "type": connection_type,
        "server_name": _optional_string(connection_source.get("server_name"), "server_name"),
        "server_address": _optional_string(connection_source.get("server_address"), "server_address"),
        "world_name": _optional_string(connection_source.get("world_name"), "world_name"),
    }

    world_source = _object(source.get("world"), "world")
    dimension = _optional_string(world_source.get("dimension"), "dimension")
    if dimension is None:
        raise ValueError("world.dimension is required")
    world = {
        "dimension": dimension.casefold(),
        "biome": (_optional_string(world_source.get("biome"), "biome") or "unknown").casefold(),
    }

    player_source = _object(source.get("player"), "player")
    position_source = _object(player_source.get("position"), "position")
    position = {
        axis: _optional_number(position_source.get(axis), f"position.{axis}")
        for axis in ("x", "y", "z")
    }
    game_mode = _optional_string(player_source.get("game_mode"), "game_mode") or "unknown"
    if game_mode.casefold() not in GAME_MODES:
        game_mode = "unknown"
    experience_source = player_source.get("experience")
    experience = None
    if experience_source is not None:
        experience_object = _object(experience_source, "experience")
        experience = {
            "level": _optional_integer(experience_object.get("level"), "experience.level"),
            "progress": _optional_number(experience_object.get("progress"), "experience.progress", 0),
        }
        if experience["progress"] is not None and experience["progress"] > 1:
            raise ValueError("experience.progress must not exceed 1")
    player = {
        "position": position,
        "health": _optional_number(player_source.get("health"), "health", 0),
        "max_health": _optional_number(player_source.get("max_health"), "max_health", 0),
        "food": _optional_integer(player_source.get("food"), "food"),
        "max_food": _optional_integer(player_source.get("max_food"), "max_food"),
        "armor": _optional_integer(player_source.get("armor"), "armor"),
        "experience": experience,
        "game_mode": game_mode.casefold(),
    }
    return {"connection": connection, "world": world, "player": player}


def normalize_minecraft_event(event: Any, payload: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(event, str):
        raise ValueError("event must be a string")
    normalized = event.removeprefix("minecraft.")
    if normalized not in EVENTS:
        raise ValueError("unsupported Minecraft event")
    data = _object(payload, "payload")
    safe: dict[str, Any] = {}
    if normalized in {"player.damage_taken", "player.healed"}:
        for field in ("amount", "health_after", "max_health"):
            value = _optional_number(data.get(field), field, 0)
            if value is not None:
                safe[field] = value
        source = _optional_string(data.get("source"), "source")
        if source:
            safe["source"] = source
    elif normalized == "dimension.changed":
        for field in ("from", "to"):
            value = _optional_string(data.get(field), field)
            if value:
                safe[field] = value.casefold()
    elif normalized in {"session.joined", "session.left"}:
        for field in ("type", "name"):
            value = _optional_string(data.get(field), field)
            if value:
                safe[field] = value
    return f"minecraft.{normalized}", safe
