from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .config import FoundryPaths
from .jobs import canonical_json
from .lineage import add_lineage, plan_transform
from .registry import Registry
from .store import ObjectStore


SCHEMA_ROOT = Path(__file__).resolve().parents[4] / "schemas" / "gpu-worker"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _validate(name: str, value: dict[str, Any]) -> None:
    schema = _load(SCHEMA_ROOT / f"{name}.schema.json")
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ValueError(f"{name} schema: {errors[0].message}")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(job: dict[str, Any], worker_spec: dict[str, Any]) -> str:
    transform = job["transform"]
    value = {
        "task_type": job["task_type"],
        "model": worker_spec.get("model_binding"),
        "software_environment": worker_spec["software_environment"],
        "parameters": transform.get("parameters", {}),
        "transform": {"name": transform["name"], "version": transform["version"]},
        "input_hashes": [item["sha256"] for item in job["inputs"]],
        "code_commit": worker_spec["code_commit"],
    }
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _safe_output(package: Path, relative: str) -> Path:
    path = package / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(package.resolve()):
        raise ValueError("worker output path escapes the staged package")
    if not path.is_file() or path.is_symlink():
        raise ValueError("worker output must be a package-local regular file")
    return path


def import_worker_result(
    paths: FoundryPaths, registry: Registry, package: Path, *, actor: str
) -> dict[str, Any]:
    package = package.resolve(strict=True)
    if not package.is_dir() or any(path.is_symlink() for path in package.rglob("*")):
        raise ValueError("worker result package must be a symlink-free directory")
    staging = paths.root / "staging" / "worker-results" / f"{package.name}-{uuid.uuid4()}"
    staging.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copytree(package, staging)
    try:
        values = {
            name: _load(staging / f"{name}.json")
            for name in (
                "job", "input-manifest", "worker-spec", "source-binding",
                "result", "output-manifest", "environment",
            )
        }
        for name in ("job", "input-manifest", "worker-spec", "source-binding", "result", "output-manifest", "environment"):
            _validate(name, values[name])
        job = values["job"]
        job_id = job["job_id"]
        if any(values[name]["job_id"] != job_id for name in ("input-manifest", "source-binding", "result", "output-manifest")):
            raise ValueError("worker package job IDs differ")
        if values["result"]["status"] != "completed":
            raise ValueError("only completed worker results can be imported")
        expected_fingerprint = _fingerprint(job, values["worker-spec"])
        if values["result"]["transform_fingerprint"] != expected_fingerprint:
            raise ValueError("worker transform fingerprint differs")
        if values["result"]["outputs"] != values["output-manifest"]["outputs"]:
            raise ValueError("result and output manifest differ")
        if values["result"]["worker"] != values["environment"]:
            raise ValueError("result worker binding differs from environment receipt")
        if values["environment"].get("code_commit") != values["worker-spec"]["code_commit"]:
            raise ValueError("worker environment code commit differs")

        with registry.connect() as connection:
            planned = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if planned is None:
                raise KeyError(f"unknown canonical job: {job_id}")
            manifest = json.loads(planned["input_manifest_json"])
            canonical_package = paths.root / "jobs" / "remote-5090" / job_id
            for name in ("job", "input-manifest", "worker-spec", "source-binding"):
                if values[name] != _load(canonical_package / f"{name}.json"):
                    raise ValueError(f"{name} differs from canonical job package")
            previous = connection.execute(
                "SELECT * FROM worker_result_imports WHERE job_id=?", (job_id,)
            ).fetchone()
            result_sha256 = _hash(staging / "result.json")
            if previous:
                if previous["result_sha256"] != result_sha256:
                    raise ValueError("job was already imported with a different result")
                return {
                    "job_id": job_id,
                    "idempotent": True,
                    "outputs": json.loads(previous["imported_outputs_json"]),
                }
            if planned["state"] != "staged":
                raise PermissionError("canonical job lacks an execution grant")
            for source_id in values["source-binding"]["source_ids"]:
                rights = registry.current_rights(connection, source_id)
                if not rights or rights["status"] != values["source-binding"]["rights_status"]:
                    raise PermissionError("current rights differ from the worker source binding")

        output_manifest_sha256 = _hash(staging / "output-manifest.json")
        for item in values["output-manifest"]["outputs"]:
            output = _safe_output(staging, item["path"])
            if output.stat().st_size != item["size_bytes"] or _hash(output) != item["sha256"]:
                raise ValueError(f"worker output hash mismatch: {item['path']}")
        source_id = values["source-binding"]["source_ids"][0]
        store = ObjectStore(paths, registry)
        imported = []
        transform_id = plan_transform(
            registry,
            job["task_type"],
            manifest["input_object_hashes"],
            {
                "worker_transform": job["transform"],
                "transform_fingerprint": expected_fingerprint,
                "model_binding": values["worker-spec"].get("model_binding"),
            },
            tool="miku-gpu-worker",
            tool_version=str(values["result"]["protocol_version"]),
        )
        for item in values["output-manifest"]["outputs"]:
            output = _safe_output(staging, item["path"])
            digest = store.ingest(
                output, source_id, role=f"worker:{item['logical_role']}",
                media_type=item["media_type"],
            )
            if digest != item["sha256"]:
                raise ValueError("canonical ingest digest differs from worker output")
            add_lineage(registry, transform_id, manifest["input_object_hashes"], digest)
            imported.append({"logical_role": item["logical_role"], "sha256": digest})

        environment_sha256 = _hash(staging / "environment.json")
        with registry.transaction() as connection:
            connection.execute(
                """INSERT INTO worker_result_imports VALUES (?,?,?,?,?,?,?,?)""",
                (
                    job_id, result_sha256, output_manifest_sha256, expected_fingerprint,
                    environment_sha256,
                    json.dumps(values["worker-spec"].get("model_binding"), sort_keys=True),
                    json.dumps(imported, sort_keys=True), registry.now(),
                ),
            )
            connection.execute(
                "UPDATE jobs SET state='completed',output_manifest_json=?,updated_at=? WHERE job_id=?",
                (json.dumps(values["output-manifest"], sort_keys=True), registry.now(), job_id),
            )
            connection.execute(
                "INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    registry.new_id(), "worker_result", job_id, 1, actor, None,
                    "quarantine", "technical result requires canonical review", registry.now(),
                ),
            )
            registry.audit(
                connection, "worker_result.imported", actor, "job", job_id,
                {"outputs": imported, "transform_fingerprint": expected_fingerprint},
            )
        return {"job_id": job_id, "idempotent": False, "outputs": imported}
    except BaseException:
        quarantine = paths.root / "quarantine" / "worker-results" / staging.name
        quarantine.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if staging.exists():
            os.replace(staging, quarantine)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
