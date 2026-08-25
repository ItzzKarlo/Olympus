from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    revision: str = "unknown"
    source_tree: str = "development"


def release_root() -> Path:
    override = os.getenv("OLYMPUS_RELEASE_ROOT")
    return Path(override) if override else Path(__file__).resolve().parents[2]


def _version(root: Path) -> str:
    try:
        value = (root / "VERSION").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return "unknown"
    return value if VERSION_PATTERN.fullmatch(value) else "unknown"


def release_info(root: Path | None = None) -> ReleaseInfo:
    resolved = root or release_root()
    version = _version(resolved)
    try:
        value: Any = json.loads(
            (resolved / "RELEASE-METADATA.json").read_text(encoding="ascii")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ReleaseInfo(version=version)
    if not isinstance(value, dict):
        return ReleaseInfo(version=version)
    revision = value.get("revision")
    source_tree = value.get("source_tree")
    metadata_version = value.get("version")
    if (
        metadata_version != version
        or not isinstance(revision, str)
        or not REVISION_PATTERN.fullmatch(revision)
        or source_tree not in {"clean", "dirty"}
    ):
        return ReleaseInfo(version=version)
    return ReleaseInfo(version=version, revision=revision, source_tree=source_tree)
