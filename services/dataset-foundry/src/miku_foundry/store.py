from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from .config import FoundryPaths
from .registry import Registry


class ObjectStore:
    def __init__(self, paths: FoundryPaths, registry: Registry):
        self.paths = paths
        self.registry = registry

    @staticmethod
    def hash_file(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def ingest(self, source_path: Path, source_id: str, *, role: str = "raw",
               media_type: str | None = None, dry_run: bool = False) -> str:
        source_path = source_path.resolve(strict=True)
        if not source_path.is_file():
            raise ValueError("intake source must be a regular file")
        if dry_run:
            return self.hash_file(source_path)[0]

        ingest_id = str(uuid.uuid4())
        staged = self.paths.root / "staging" / f"{ingest_id}.partial"
        with self.registry.transaction() as connection:
            connection.execute(
                "INSERT INTO pending_ingests VALUES (?,?,?,?,?,?)",
                (ingest_id, str(staged), None, source_id, "copying", self.registry.now()),
            )
        digest = hashlib.sha256()
        size = 0
        try:
            with source_path.open("rb") as incoming, staged.open("xb") as outgoing:
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    outgoing.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            hexdigest = digest.hexdigest()
            target = self.paths.object_path(hexdigest)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.registry.transaction() as connection:
                connection.execute(
                    "UPDATE pending_ingests SET sha256=?, state='promoting' WHERE ingest_id=?",
                    (hexdigest, ingest_id),
                )
            if target.exists():
                actual, actual_size = self.hash_file(target)
                if actual != hexdigest or actual_size != size:
                    raise IOError("existing canonical object failed integrity verification")
                staged.unlink()
            else:
                os.replace(staged, target)
                target.chmod(0o400)
                directory_fd = os.open(target.parent, os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            with self.registry.transaction() as connection:
                now = self.registry.now()
                connection.execute(
                    "INSERT INTO objects VALUES (?,?,?,?,?) ON CONFLICT(sha256) DO UPDATE SET verified_at=excluded.verified_at",
                    (hexdigest, size, media_type, now, now),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO source_objects VALUES (?,?,?,?)",
                    (source_id, hexdigest, source_path.name, role),
                )
                connection.execute("DELETE FROM pending_ingests WHERE ingest_id=?", (ingest_id,))
                self.registry.audit(connection, "object.ingested", "local-writer", "object", hexdigest,
                                    {"source_id": source_id, "size_bytes": size, "role": role})
            return hexdigest
        except BaseException:
            if staged.exists():
                staged.unlink()
            raise

    def verify(self) -> list[dict[str, object]]:
        failures: list[dict[str, object]] = []
        with self.registry.connect() as connection:
            for row in connection.execute("SELECT sha256,size_bytes FROM objects ORDER BY sha256"):
                path = self.paths.object_path(row["sha256"])
                if not path.is_file():
                    failures.append({"sha256": row["sha256"], "error": "missing"})
                    continue
                actual, size = self.hash_file(path)
                if actual != row["sha256"] or size != row["size_bytes"]:
                    failures.append({"sha256": row["sha256"], "actual": actual, "size_bytes": size,
                                     "error": "hash_mismatch"})
        return failures

    def reconcile(self) -> dict[str, int]:
        removed_staging = 0
        removed_orphans = 0
        with self.registry.transaction() as connection:
            pending = list(connection.execute("SELECT * FROM pending_ingests"))
            referenced = {row[0] for row in connection.execute("SELECT sha256 FROM objects")}
            for row in pending:
                staged = Path(row["staged_path"])
                if staged.exists():
                    staged.unlink()
                    removed_staging += 1
                digest = row["sha256"]
                if digest and digest not in referenced:
                    target = self.paths.object_path(digest)
                    if target.exists():
                        target.chmod(0o600)
                        target.unlink()
                        removed_orphans += 1
                connection.execute("DELETE FROM pending_ingests WHERE ingest_id=?", (row["ingest_id"],))
        return {"removed_staging": removed_staging, "removed_orphans": removed_orphans}
