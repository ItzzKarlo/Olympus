from pathlib import Path
from uuid import uuid4


def load_or_create_agent_id(path: Path, prefix: str) -> str:
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = ""

    if existing:
        return existing

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    agent_id = f"{prefix}-{uuid4().hex}"
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(f"{agent_id}\n", encoding="utf-8")
    try:
        temporary_path.chmod(0o600)
    except OSError:
        # Windows ACLs, rather than POSIX modes, protect the user profile path.
        pass
    temporary_path.replace(path)
    return agent_id
