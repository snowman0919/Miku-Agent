"""OS-level exclusive GPU lock."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import IO


class GpuLock:
    def __init__(self, path: Path):
        self.path = path
        self._stream: IO[str] | None = None

    def acquire(self, blocking: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+", encoding="utf-8")
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(stream.fileno(), flags)
        except BlockingIOError:
            stream.close()
            raise
        self._stream = stream

    def release(self) -> None:
        if self._stream is not None:
            fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            self._stream.close()
            self._stream = None

    def __enter__(self) -> "GpuLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

