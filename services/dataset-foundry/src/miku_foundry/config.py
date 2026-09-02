from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FoundryPaths:
    root: Path

    @property
    def objects(self) -> Path:
        return self.root / "objects" / "sha256"

    @property
    def registry(self) -> Path:
        return self.root / "registry" / "registry.sqlite3"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots" / "parquet"

    def object_path(self, digest: str) -> Path:
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("digest must be 64 lowercase hexadecimal characters")
        return self.objects / digest[:2] / digest


def paths_from_env(explicit: str | None = None) -> FoundryPaths:
    configured = explicit or os.environ.get("MIKU_DATA_ROOT")
    if not configured:
        raise RuntimeError("MIKU_DATA_ROOT is required; the foundry never guesses a large-data location")
    root = Path(configured).expanduser().resolve()
    if root == Path("/") or root == Path.home():
        raise RuntimeError("MIKU_DATA_ROOT must be a dedicated directory, not / or the home directory")
    return FoundryPaths(root)


def initialize_layout(paths: FoundryPaths) -> None:
    directories = (
        paths.root,
        paths.root / "objects",
        paths.objects,
        paths.root / "staging",
        paths.root / "quarantine",
        paths.root / "registry",
        paths.root / "registry" / "backups",
        paths.root / "snapshots",
        paths.snapshots,
        paths.root / "indexes",
        paths.root / "cache",
        paths.root / "exports",
        paths.root / "reviews",
        paths.root / "jobs",
        paths.root / "jobs" / "local",
        paths.root / "jobs" / "remote-5090",
        paths.root / "logs",
        paths.root / "reports",
        paths.root / "tmp",
        paths.root / "intake",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
