#!/usr/bin/env python3
"""Validate Olympus production config without exposing secret values."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib


ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
            line = line[7:].lstrip()
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
    if isinstance(security, dict) and security.get("require_agent_auth") is not True:
        errors.append(f"{config_path}: security.require_agent_auth must be true in production")

    integration_credentials = {
        "calendar.enabled": (
            bool(isinstance(config.get("calendar"), dict) and config["calendar"].get("enabled")),
            {"OLYMPUS_GOOGLE_CLIENT_ID", "OLYMPUS_GOOGLE_CLIENT_SECRET", "OLYMPUS_GOOGLE_REFRESH_TOKEN"},
        ),
        "football.enabled": (
            bool(isinstance(config.get("football"), dict) and config["football"].get("enabled")),
            {"OLYMPUS_FOOTBALL_API_KEY", "OLYMPUS_FOOTBALL_DATA_API_KEY"},
        ),
    }
    for label, (enabled, alternatives) in integration_credentials.items():
        if enabled and not any(keys.get(key, (0, ""))[1] for key in alternatives):
            errors.append(
                f"{config_path}: {label}=true but {secrets_path} declares no matching credential key"
            )
    spotify_enabled = keys.get("OLYMPUS_SPOTIFY_ENABLED", (0, ""))[1].casefold() in {
        "1", "true", "yes", "on"
    }
    spotify_credentials = {
        "OLYMPUS_SPOTIFY_CLIENT_ID", "OLYMPUS_SPOTIFY_CLIENT_SECRET", "OLYMPUS_SPOTIFY_REFRESH_TOKEN"
    }
    missing_spotify = {
        key for key in spotify_credentials if not keys.get(key, (0, ""))[1]
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
