from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from conftest import source
from miku_foundry.jobs import authorize_remote_5090, canonical_json, prepare_remote_package
from miku_foundry.rights import register_rights
from miku_foundry.store import ObjectStore
from miku_foundry.worker_import import _fingerprint, import_worker_result


COMMIT = "b" * 40


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def test_worker_result_requires_canonical_binding_and_imports_idempotently(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry)
    register_rights(registry, source_id, "owned", "fixture", "test", "technical-pilot",
                    reviewer="operator", actor_type="user")
    raw = paths.root / "intake" / "input.bin"
    raw.write_bytes(b"input")
    digest = ObjectStore(paths, registry).ingest(raw, source_id)
    manifest = {
        "task_type": "audio_quality", "input_object_hashes": [digest],
        "foundry_code_commit": COMMIT, "created_at": "2026-09-03T00:00:00Z",
        "worker_spec": {"code_commit": COMMIT, "software_environment": {"python": "3.11"},
                        "determinism": "deterministic", "seed": 0, "model_binding": None},
        "source_binding": {"source_ids": [source_id], "rights_status": "owned"},
        "transform": {"name": "audio_quality", "version": "reference-1", "parameters": {}},
        "resource_request": {"gpu_count": 0, "min_vram_bytes": 0,
                             "cpu_threads": 1, "ram_bytes": 1024},
    }
    job_id, _ = prepare_remote_package(paths, registry, manifest)
    authorize_remote_5090(registry, job_id, {
        "job_id": job_id, "allowed": True,
        "input_digest": hashlib.sha256(canonical_json([digest]).encode()).hexdigest(),
        "code_commit": COMMIT,
    })

    package = tmp_path / "result"
    shutil.copytree(paths.root / "jobs" / "remote-5090" / job_id, package)
    outputs = package / "outputs"
    outputs.mkdir()
    feature = outputs / "features.json"
    feature.write_text('{"score":1}\n', encoding="utf-8")
    item = {
        "path": "outputs/features.json", "sha256": hashlib.sha256(feature.read_bytes()).hexdigest(),
        "size_bytes": feature.stat().st_size, "media_type": "application/json",
        "logical_role": "technical_scores", "sample_rate": None, "duration_seconds": None,
    }
    job = json.loads((package / "job.json").read_text(encoding="utf-8"))
    spec = json.loads((package / "worker-spec.json").read_text(encoding="utf-8"))
    environment = {"hostname": "worker", "platform": "linux", "python": "3.11.0",
                   "code_commit": COMMIT, "gpu": None}
    write_json(package / "environment.json", environment)
    write_json(package / "output-manifest.json", {
        "protocol_version": 1, "job_id": job_id, "outputs": [item],
    })
    write_json(package / "result.json", {
        "protocol_version": 1, "job_id": job_id, "status": "completed",
        "task_type": "audio_quality", "transform_fingerprint": _fingerprint(job, spec),
        "started_at": "2026-09-03T00:00:00Z", "completed_at": "2026-09-03T00:00:01Z",
        "worker": environment, "outputs": [item], "warnings": [], "errors": [],
    })

    tampered = tmp_path / "tampered"
    shutil.copytree(package, tampered)
    binding = json.loads((tampered / "source-binding.json").read_text(encoding="utf-8"))
    binding["source_ids"] = ["different-source"]
    write_json(tampered / "source-binding.json", binding)
    with pytest.raises(ValueError, match="differs from canonical"):
        import_worker_result(paths, registry, tampered, actor="operator")

    first = import_worker_result(paths, registry, package, actor="operator")
    second = import_worker_result(paths, registry, package, actor="operator")
    assert first["idempotent"] is False
    assert second == {**first, "idempotent": True}
    with registry.connect() as connection:
        assert connection.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()[0] == "completed"
        assert connection.execute("SELECT count(*) FROM worker_result_imports").fetchone()[0] == 1
        assert connection.execute("SELECT decision FROM reviews WHERE entity_id=?", (job_id,)).fetchone()[0] == "quarantine"
