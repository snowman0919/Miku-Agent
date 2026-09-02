from __future__ import annotations

import hashlib
import json
import os
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
        manifest = json.loads(job["input_manifest_json"])
        expected_digest = hashlib.sha256(
            canonical_json(manifest["input_object_hashes"]).encode()
        ).hexdigest()
        if (
            grant["input_digest"] != expected_digest
            or grant["code_commit"] != manifest["foundry_code_commit"]
        ):
            raise PermissionError("remote grant source binding differs from the prepared job")
        connection.execute("UPDATE jobs SET state='staged', updated_at=? WHERE job_id=?",
                           (registry.now(), job_id))


def prepare_remote_package(paths: FoundryPaths, registry: Registry,
                           manifest: dict[str, object]) -> tuple[str, str]:
    required = {
        "task_type", "input_object_hashes", "foundry_code_commit", "worker_spec",
        "source_binding", "transform", "resource_request", "created_at",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValueError(f"remote manifest missing fields: {missing}")
    job_id = ensure_job(registry, "remote-5090", manifest)
    package = paths.root / "jobs" / "remote-5090" / job_id
    package.mkdir(parents=True, exist_ok=True, mode=0o700)
    inputs = []
    with registry.connect() as connection:
        binding = manifest["source_binding"]
        source_ids = binding.get("source_ids", [])
        if not source_ids:
            raise ValueError("remote source binding requires at least one source")
        for source_id in source_ids:
            rights = registry.current_rights(connection, source_id)
            if not rights or rights["status"] != binding.get("rights_status"):
                raise PermissionError("remote source binding differs from current rights")
        for index, digest in enumerate(manifest["input_object_hashes"]):
            row = connection.execute(
                "SELECT size_bytes,media_type FROM objects WHERE sha256=?", (digest,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown input object: {digest}")
            suffix = ".wav" if row["media_type"] == "audio/wav" else ".bin"
            relative = f"inputs/input-{index}{suffix}"
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            source = paths.object_path(digest)
            if not target.exists():
                os.link(source, target)
            inputs.append({
                "id": f"input-{index}", "path": relative, "sha256": digest,
                "size_bytes": row["size_bytes"],
            })
    worker_spec = {**manifest["worker_spec"], "protocol_version": 1}
    source_binding = {
        **manifest["source_binding"],
        "protocol_version": 1,
        "job_id": job_id,
        "foundry_code_commit": manifest["foundry_code_commit"],
    }
    files = {
        "job.json": {
            "protocol_version": 1,
            "job_id": job_id,
            "task_type": manifest["task_type"],
            "created_at": manifest["created_at"],
            "priority": manifest.get("priority", 50),
            "inputs": inputs,
            "transform": manifest["transform"],
            "resource_request": manifest["resource_request"],
        },
        "input-manifest.json": {
            "protocol_version": 1,
            "job_id": job_id,
            "inputs": [
                {key: item[key] for key in ("id", "sha256", "size_bytes")}
                for item in inputs
            ],
        },
        "worker-spec.json": worker_spec,
        "source-binding.json": source_binding,
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
