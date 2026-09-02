from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import FoundryPaths
from .registry import Registry


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ensure_job(registry: Registry, kind: str, input_manifest: dict[str, object]) -> str:
    body = canonical_json(input_manifest)
    key = hashlib.sha256(f"{kind}\0{body}".encode()).hexdigest()
    with registry.transaction() as connection:
        existing = connection.execute("SELECT job_id FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            return existing["job_id"]
        job_id = registry.new_id()
        now = registry.now()
        connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                           (job_id, kind, key, "prepared", body, None, None, now, now))
    return job_id


def authorize_remote_5090(registry: Registry, job_id: str, grant: dict[str, object] | None) -> None:
    if not grant:
        raise PermissionError("remote dataset execution requires an explicit job-bound grant")
    if grant.get("job_id") != job_id or grant.get("allowed") is not True:
        raise PermissionError("remote grant is not bound to this job")
    if not grant.get("input_digest") or not grant.get("code_commit"):
        raise PermissionError("remote grant lacks source binding")
    with registry.transaction() as connection:
        job = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not job or job["state"] not in {"prepared", "waiting_for_lease"}:
            raise PermissionError("remote job is not eligible")
        connection.execute("UPDATE jobs SET state='staged', updated_at=? WHERE job_id=?",
                           (registry.now(), job_id))


def prepare_remote_package(paths: FoundryPaths, registry: Registry,
                           manifest: dict[str, object]) -> tuple[str, str]:
    required = {"input_object_hashes", "code_commit", "worker_spec", "source_binding"}
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValueError(f"remote manifest missing fields: {missing}")
    job_id = ensure_job(registry, "remote-5090", manifest)
    package = paths.root / "jobs" / "remote-5090" / job_id
    package.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = {
        "input-manifest.json": {"job_id": job_id, "input_object_hashes": manifest["input_object_hashes"]},
        "worker-spec.json": manifest["worker_spec"],
        "source-binding.json": manifest["source_binding"],
        "expected-output.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["job_id", "outputs"],
            "properties": {"job_id": {"const": job_id}, "outputs": {"type": "array", "items": {
                "type": "object", "required": ["sha256", "size_bytes"],
                "properties": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                               "size_bytes": {"type": "integer", "minimum": 0}}}}},
        },
    }
    for name, value in files.items():
        target = package / name
        body = json.dumps(value, indent=2, sort_keys=True) + "\n"
        if target.exists() and target.read_text(encoding="utf-8") != body:
            raise RuntimeError(f"existing remote package differs: {name}")
        if not target.exists():
            target.write_text(body, encoding="utf-8")
            target.chmod(0o600)
    with registry.transaction() as connection:
        connection.execute(
            "UPDATE jobs SET state='waiting_for_lease', updated_at=? WHERE job_id=? AND state='prepared'",
            (registry.now(), job_id),
        )
        state = connection.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0]
    return job_id, state
