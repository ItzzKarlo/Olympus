#!/usr/bin/env python3
"""Generate and validate immutable Olympus release provenance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SOURCE_STATES = {"clean", "dirty"}


def read_version(path: Path) -> str:
    version = path.read_text(encoding="ascii").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid Olympus version in {path}")
    return version


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def source_identity(root: Path) -> tuple[str, str]:
    try:
        inside = git_output(root, "rev-parse", "--is-inside-work-tree") == "true"
    except (FileNotFoundError, subprocess.CalledProcessError):
        inside = False
    if inside:
        revision = git_output(root, "rev-parse", "HEAD").casefold()
        state = "dirty" if git_output(root, "status", "--porcelain", "--untracked-files=normal") else "clean"
    else:
        revision = os.getenv("OLYMPUS_SOURCE_REVISION", "").strip().casefold()
        state = os.getenv("OLYMPUS_SOURCE_STATE", "clean").strip().casefold()
    if not REVISION_PATTERN.fullmatch(revision):
        raise ValueError("A full 40-character Git source revision is required")
    if state not in SOURCE_STATES:
        raise ValueError("Olympus source state must be clean or dirty")
    return revision, state


def generate(root: Path, output: Path, *, allow_dirty: bool = False) -> dict[str, str]:
    version = read_version(root / "VERSION")
    revision, source_tree = source_identity(root)
    if source_tree != "clean" and not allow_dirty:
        raise ValueError(
            "Refusing to build deployable release metadata from a dirty source tree; "
            "use --allow-dirty only for local development artifacts"
        )
    metadata = {
        "revision": revision,
        "source_tree": source_tree,
        "version": version,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return metadata


def validate(metadata_path: Path, version_path: Path, *, require_clean: bool) -> dict[str, str]:
    try:
        value = json.loads(metadata_path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid release metadata: {metadata_path}") from error
    if not isinstance(value, dict):
        raise ValueError("Release metadata must be a JSON object")
    expected = {"revision", "source_tree", "version"}
    if set(value) != expected or not all(isinstance(value[key], str) for key in expected):
        raise ValueError("Release metadata has unexpected or missing fields")
    version = read_version(version_path)
    if value["version"] != version:
        raise ValueError("Release metadata version does not match VERSION")
    if not REVISION_PATTERN.fullmatch(value["revision"]):
        raise ValueError("Release metadata revision is not a full Git SHA")
    if value["source_tree"] not in SOURCE_STATES:
        raise ValueError("Release metadata source_tree is invalid")
    if require_clean and value["source_tree"] != "clean":
        raise ValueError("Dirty development artifacts cannot be installed")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("write")
    write.add_argument("--root", type=Path, required=True)
    write.add_argument("--output", type=Path, required=True)
    write.add_argument("--allow-dirty", action="store_true")
    check = subparsers.add_parser("validate")
    check.add_argument("--metadata", type=Path, required=True)
    check.add_argument("--version-file", type=Path, required=True)
    check.add_argument("--require-clean", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "write":
            value = generate(args.root.resolve(), args.output, allow_dirty=args.allow_dirty)
        else:
            value = validate(args.metadata, args.version_file, require_clean=args.require_clean)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Olympus release metadata error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
