from __future__ import annotations

import hashlib
import json

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
