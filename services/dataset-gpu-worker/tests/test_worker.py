from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import struct
import time
import wave
from pathlib import Path

import pytest

from miku_gpu_worker import metrics
from miku_gpu_worker.errors import WorkerError
from miku_gpu_worker.executor import Worker, run_with_oom_backoff
from miku_gpu_worker.hashing import transform_fingerprint
from miku_gpu_worker.locking import GpuLock
from miku_gpu_worker.protocol import assert_noncanonical_output, validate_job_package, validate_schema
from miku_gpu_worker.registry import load_registry
from miku_gpu_worker.tasks.audio import run_prosody

CODE_COMMIT = "1" * 40


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def make_wav(path: Path, seconds: float = 0.1) -> None:
    rate = 8000
    samples = [int(4000 * ((index % 40) / 20 - 1)) for index in range(int(rate * seconds))]
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def make_package(root: Path, job_id: str = "job-1", task: str = "audio_quality") -> Path:
    package = root / job_id
    inputs = package / "inputs"
    inputs.mkdir(parents=True)
    audio = inputs / "input-0.wav"
    make_wav(audio)
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    item = {"id": "input-0", "path": "inputs/input-0.wav", "sha256": digest, "size_bytes": audio.stat().st_size}
    write_json(package / "job.json", {"protocol_version": 1, "job_id": job_id, "task_type": task, "created_at": "2026-09-03T00:00:00Z", "priority": 50, "inputs": [item], "transform": {"name": task, "version": "reference-1", "parameters": {}}, "resource_request": {"gpu_count": 0, "min_vram_bytes": 0, "cpu_threads": None, "ram_bytes": None}})
    write_json(package / "input-manifest.json", {"protocol_version": 1, "job_id": job_id, "inputs": [{key: item[key] for key in ("id", "sha256", "size_bytes")} ]})
    write_json(package / "worker-spec.json", {"protocol_version": 1, "code_commit": CODE_COMMIT, "software_environment": {"python": "3.11"}, "determinism": "deterministic", "seed": 0, "model_binding": None})
    write_json(package / "source-binding.json", {"protocol_version": 1, "job_id": job_id, "source_ids": ["synthetic-fixture"], "rights_status": "owned"})
    return package


def test_integrity_atomic_completion_output_hash_and_cache(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    first = make_package(tmp_path / "source", "job-1")
    worker.submit(first)
    completed = worker.run("job-1")
    assert completed.parent.name == "completed"
    assert worker.verify("job-1")
    assert json.loads((completed / "result.json").read_text())["status"] == "completed"

    second = make_package(tmp_path / "source", "job-2")
    worker.submit(second)
    cached = worker.run("job-2")
    assert json.loads((cached / "metrics.json").read_text())["cache_hit"] is True
    assert (cached / "outputs" / "features.json").read_bytes() == (completed / "outputs" / "features.json").read_bytes()


def test_corrupted_cache_is_not_used(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    package = make_package(tmp_path / "source", "job-1")
    worker.submit(package); completed = worker.run("job-1")
    (completed / "outputs" / "features.json").write_text("corrupt", encoding="utf-8")
    second = make_package(tmp_path / "source", "job-2")
    worker.submit(second); rerun = worker.run("job-2")
    assert rerun.parent.name == "completed"
    assert json.loads((rerun / "metrics.json").read_text())["cache_hit"] is False


def test_cache_copy_revalidates_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = Worker(tmp_path / "worker")
    package = make_package(tmp_path / "source", "job-1")
    worker.submit(package); completed = worker.run("job-1")
    original = __import__("shutil").copy2
    def corrupt(source: Path, destination: Path, **kwargs: object) -> None:
        original(source, destination, **kwargs); Path(destination).write_bytes(b"changed")
    monkeypatch.setattr("miku_gpu_worker.executor.shutil.copy2", corrupt)
    second = make_package(tmp_path / "source", "job-2")
    worker.submit(second); failed = worker.run("job-2")
    assert failed.parent.name == "failed"
    assert json.loads((failed / "result.json").read_text())["errors"][0]["code"] == "OUTPUT_HASH_FAILED"


def test_corrupt_or_wrong_hash_is_rejected(tmp_path: Path) -> None:
    package = make_package(tmp_path)
    (package / "inputs" / "input-0.wav").write_bytes(b"corrupt")
    with pytest.raises(WorkerError, match="integrity mismatch") as caught:
        validate_job_package(package)
    assert caught.value.code == "INPUT_HASH_MISMATCH"


def test_path_and_symlink_escape_are_rejected(tmp_path: Path) -> None:
    package = make_package(tmp_path / "plain")
    job = json.loads((package / "job.json").read_text())
    job["inputs"][0]["path"] = "../outside.wav"
    write_json(package / "job.json", job)
    with pytest.raises(WorkerError):
        validate_job_package(package)

    package = make_package(tmp_path / "linked", "job-link")
    outside = tmp_path / "outside.wav"; make_wav(outside)
    audio = package / "inputs" / "input-0.wav"; audio.unlink(); audio.symlink_to(outside)
    job = json.loads((package / "job.json").read_text()); job["inputs"][0].update(sha256=hashlib.sha256(outside.read_bytes()).hexdigest(), size_bytes=outside.stat().st_size); write_json(package / "job.json", job)
    manifest = json.loads((package / "input-manifest.json").read_text()); manifest["inputs"][0].update(sha256=job["inputs"][0]["sha256"], size_bytes=outside.stat().st_size); write_json(package / "input-manifest.json", manifest)
    with pytest.raises(WorkerError, match="escapes|symlink"):
        validate_job_package(package)


def test_failed_job_never_promotes_partial_output(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    package = make_package(tmp_path / "source", task="asr_transcribe")
    worker.submit(package)
    target = worker.run("job-1")
    result = json.loads((target / "result.json").read_text())
    assert target.parent.name == "failed"
    assert result["status"] == "failed"
    assert result["errors"][0]["code"] == "MODEL_ACCESS_FAILED"


def _hold_lock(path: str, ready: multiprocessing.Event) -> None:
    with GpuLock(Path(path)):
        ready.set(); time.sleep(1)


def test_gpu_lock_is_process_exclusive(tmp_path: Path) -> None:
    ready = multiprocessing.Event()
    process = multiprocessing.Process(target=_hold_lock, args=(str(tmp_path / "gpu.lock"), ready))
    process.start(); assert ready.wait(2)
    with pytest.raises(BlockingIOError):
        GpuLock(tmp_path / "gpu.lock").acquire()
    process.join(3); assert process.exitcode == 0


def test_stale_recovery_and_bounded_oom_retry(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    stale = worker.state_path("running", "stale-job"); stale.mkdir()
    os.utime(stale, (0, 0))
    assert worker.recover_stale(1) == ["stale-job"]
    assert worker.state_path("failed", "stale-job").exists()

    seen = []
    def operation(batch: int) -> str:
        seen.append(batch)
        if batch > 32: raise WorkerError("CUDA_OOM", "test")
        return "ok"
    assert run_with_oom_backoff(operation, 64, max_retries=1) == ("ok", 32, 1)
    assert seen == [64, 32]


def test_stale_recovery_skips_job_with_live_owner_lock(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    stale = worker.state_path("running", "active-job"); stale.mkdir()
    os.utime(stale, (0, 0))
    with worker.job_lock("active-job"):
        assert worker.recover_stale(1) == []
        assert stale.exists()


def test_stale_recovery_does_not_promote_forged_completion(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    stale = worker.state_path("running", "forged"); stale.mkdir()
    write_json(stale / "result.json", {"protocol_version": 1, "job_id": "forged", "status": "completed", "task_type": "audio_quality", "transform_fingerprint": "1" * 64, "started_at": "2026-09-03T00:00:00Z", "completed_at": "2026-09-03T00:00:01Z", "worker": {}, "outputs": [{"path": "outputs/x", "sha256": "2" * 64, "size_bytes": 1, "media_type": "application/octet-stream", "logical_role": "x", "sample_rate": None, "duration_seconds": None}], "warnings": [], "errors": []})
    os.utime(stale, (0, 0))
    assert worker.recover_stale(1) == ["forged"]
    assert worker.state_path("failed", "forged").exists()


def test_input_snapshot_prevents_post_validation_mutation(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    package = make_package(tmp_path / "source")
    job, _ = validate_job_package(package)
    snapshot = worker._snapshot_input(package, job["inputs"][0])
    original = snapshot.read_bytes()
    (package / "inputs" / "input-0.wav").write_bytes(b"replaced")
    assert snapshot.read_bytes() == original
    assert snapshot.stat().st_mode & 0o222 == 0


def test_fingerprint_model_binding_and_canonical_boundary(tmp_path: Path) -> None:
    package = make_package(tmp_path)
    job, spec = validate_job_package(package)
    assert transform_fingerprint(job, spec) == transform_fingerprint(job, spec)
    with pytest.raises(WorkerError, match="canonical fields"):
        assert_noncanonical_output({"nested": {"accepted_for_training": True}})
    registry = tmp_path / "models.json"
    write_json(registry, [{"model_id": "x", "provider": "x", "task": "asr", "license": "x", "revision": "main", "weight_sha256": "1" * 64, "config_sha256": "2" * 64}])
    with pytest.raises(WorkerError, match="floating"):
        load_registry(registry)


def test_result_schema_rejects_false_completion() -> None:
    value = {"protocol_version": 1, "job_id": "x", "status": "completed", "task_type": "audio_quality", "transform_fingerprint": "1" * 64, "started_at": "2026-09-03T00:00:00Z", "completed_at": "2026-09-03T00:00:01Z", "worker": {}, "outputs": [], "warnings": [], "errors": [{"code": "UNKNOWN", "message": "bad", "retryable": False}]}
    with pytest.raises(WorkerError):
        validate_schema("result", value)
    value["errors"] = []
    with pytest.raises(WorkerError):
        validate_schema("result", value)


def test_reference_backend_rejects_false_model_binding(tmp_path: Path) -> None:
    worker = Worker(tmp_path / "worker")
    package = make_package(tmp_path / "source")
    spec = json.loads((package / "worker-spec.json").read_text())
    spec["model_binding"] = {"model_id": "unrelated/model", "revision": "1" * 40, "weight_sha256": "2" * 64, "config_sha256": "3" * 64, "license": "test"}
    write_json(package / "worker-spec.json", spec)
    worker.submit(package)
    target = worker.run("job-1")
    result = json.loads((target / "result.json").read_text())
    assert target.parent.name == "failed"
    assert result["errors"][0]["code"] == "MODEL_HASH_MISMATCH"


def test_wsl_nvidia_smi_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics.shutil, "which", lambda _: None)
    monkeypatch.setattr(metrics.Path, "is_file", lambda _: True)
    monkeypatch.setattr(metrics.os, "access", lambda *_: True)
    assert metrics.nvidia_smi_command() == "/usr/lib/wsl/lib/nvidia-smi"


def test_prosody_preserves_temporal_f0_features(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"; make_wav(path)
    result = run_prosody(path, {"frame_ms": 40})
    assert len(result["f0_hz"]) == len(result["energy_rms"]) == len(result["voiced"])
    assert any(value is not None for value in result["f0_hz"])
