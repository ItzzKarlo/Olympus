import os
from pathlib import Path


class SingleInstance:
    """Per-user OS lock; the file is metadata, not the source of truth."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: object | None = None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                if handle.read(1) == b"":
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                write_metadata = False
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                write_metadata = True
        except (BlockingIOError, OSError):
            handle.close()
            return False
        if write_metadata:
            handle.seek(0)
            handle.truncate()
            handle.write(f"{os.getpid()}\n".encode("ascii"))
            handle.flush()
        self._file = handle
        return True

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)  # type: ignore[attr-defined]
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        finally:
            handle.close()  # type: ignore[attr-defined]
            self._file = None

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise RuntimeError("Olympus Agent is already running.")
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def is_instance_running(path: Path) -> bool:
    if not path.parent.exists():
        return False
    candidate = SingleInstance(path)
    if not candidate.acquire():
        return True
    candidate.release()
    return False
