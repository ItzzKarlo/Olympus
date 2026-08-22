from pathlib import Path

from olympus_agent_common.identity import load_or_create_agent_id as load_identity


def load_or_create_agent_id(path: Path) -> str:
    return load_identity(path, "win")
