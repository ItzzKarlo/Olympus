#!/usr/bin/env python3
"""Validate Olympus production config without exposing secret values."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib


ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def declared_value(keys: dict[str, tuple[int, str]], key: str) -> str:
    value = keys.get(key, (0, ""))[1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def parse_secrets(path: Path) -> tuple[dict[str, tuple[int, str]], list[str]]:
    keys: dict[str, tuple[int, str]] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return {}, [f"{path}: unreadable: {error}"]
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            errors.append(f"{path}:{number}: remove unsupported export prefix; expected KEY=value")
            continue
        if "=" not in line:
            errors.append(f"{path}:{number}: expected KEY=value")
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if not ENV_KEY.fullmatch(key):
            errors.append(f"{path}:{number}: invalid environment key {key!r}")
        elif key in keys:
            errors.append(f"{path}:{number}: duplicate key {key} (first declared on line {keys[key][0]})")
        else:
            keys[key] = (number, value)
    return keys, errors


def validate(config_path: Path, secrets_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with config_path.open("rb") as file:
            config = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"{config_path}: invalid TOML: {error}"]
    keys, secret_errors = parse_secrets(secrets_path)
    errors.extend(secret_errors)

    security = config.get("security", {})
    if not isinstance(security, dict) or security.get("require_agent_auth") is not True:
        errors.append(f"{config_path}: security.require_agent_auth must be true in production")

    calendar = config.get("calendar", {})
    if isinstance(calendar, dict) and bool(calendar.get("enabled")):
        provider = str(calendar.get("provider", "google")).strip().lower()
        if provider != "google":
            errors.append(f"{config_path}: calendar.provider is unsupported: {provider!r}")
        else:
            required = {
                "OLYMPUS_GOOGLE_CLIENT_ID", "OLYMPUS_GOOGLE_CLIENT_SECRET", "OLYMPUS_GOOGLE_REFRESH_TOKEN"
            }
            missing = sorted(key for key in required if not declared_value(keys, key))
            if missing:
                errors.append(
                    f"{config_path}: calendar.enabled=true but {secrets_path} is missing credential keys: "
                    + ", ".join(missing)
                )

    football = config.get("football", {})
    if isinstance(football, dict) and bool(football.get("enabled")):
        provider = str(football.get("provider", "api-football")).strip().lower()
        required_by_provider = {
            "api-football": "OLYMPUS_FOOTBALL_API_KEY",
            "football-data": "OLYMPUS_FOOTBALL_DATA_API_KEY",
            "fixture": "OLYMPUS_FOOTBALL_FIXTURE_PATH",
        }
        required = required_by_provider.get(provider)
        if required is None:
            errors.append(f"{config_path}: football.provider is unsupported: {provider!r}")
        elif not declared_value(keys, required):
            errors.append(
                f"{config_path}: football.enabled=true with provider {provider!r} but "
                f"{secrets_path} is missing credential key {required}"
            )

    spotify_enabled = declared_value(keys, "OLYMPUS_SPOTIFY_ENABLED").casefold() in {
        "1", "true", "yes", "on"
    }
    spotify_credentials = {
        "OLYMPUS_SPOTIFY_CLIENT_ID", "OLYMPUS_SPOTIFY_CLIENT_SECRET", "OLYMPUS_SPOTIFY_REFRESH_TOKEN"
    }
    missing_spotify = {
        key for key in spotify_credentials if not declared_value(keys, key)
    }
    if spotify_enabled and missing_spotify:
        missing = ", ".join(sorted(missing_spotify))
        errors.append(f"{secrets_path}: Spotify enable key is declared but credential keys are missing: {missing}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/olympus/config.toml"))
    parser.add_argument("--secrets", type=Path, default=Path("/etc/olympus/secrets.env"))
    args = parser.parse_args(argv)
    errors = validate(args.config, args.secrets)
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"PASS  configuration syntax and declarations: {args.config}, {args.secrets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
