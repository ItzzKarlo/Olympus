#!/usr/bin/env python3
"""Installer-only config migration. Not a privileged executable callable by Core."""
import os
from pathlib import Path
import pwd
import shutil
import tempfile


def migrate(base: Path, uid: int, gid: int):
    config = base / "config.toml"
    directory = base / "managed-config"
    target = directory / "config.toml"
    if directory.is_symlink():
        raise ValueError("Managed config directory must not be a symlink")
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chown(directory, uid, gid)
    directory.chmod(0o700)
    if config.is_symlink():
        if config.resolve() != target.resolve() or target.is_symlink() or not target.is_file():
            raise ValueError("Unexpected config symlink; refusing to migrate")
        return
    if not config.is_file() or target.exists() or target.is_symlink():
        raise ValueError("Ambiguous config migration; preserve and inspect existing files")
    # Preserve the original root-owned file for emergency rollback.
    backup = base / "config.pre-control.toml"
    if backup.exists() or backup.is_symlink():
        raise ValueError("Migration backup already exists; refusing to overwrite")
    with config.open("rb") as source, backup.open("xb") as saved:
        shutil.copyfileobj(source, saved)
        saved.flush(); os.fsync(saved.fileno())
    backup.chmod(0o600)
    fd, name = tempfile.mkstemp(prefix=".migrate-", dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output, config.open("rb") as source:
            shutil.copyfileobj(source, output)
            output.flush(); os.fsync(output.fileno())
        os.chown(temporary, uid, gid)
        temporary.replace(target)
        link = base / ".config-control.next"
        if link.exists() or link.is_symlink():
            raise ValueError("Migration link already exists")
        link.symlink_to("managed-config/config.toml")
        link.replace(config)
        for folder in (base, directory):
            fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run through the root Hermes installer")
    account = pwd.getpwnam("olympus")
    migrate(Path("/etc/olympus"), account.pw_uid, account.pw_gid)
