"""Atomic, cache-aware job execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .errors import WorkerError
from .hashing import canonical_json_bytes, sha256_file, transform_fingerprint
from .locking import GpuLock
from .metrics import MetricsRecorder, environment_snapshot
from .protocol import assert_noncanonical_output, resolve_package_path, validate_job_package, validate_schema
from .tasks import run_audio_quality, run_prosody

Task = Callable[[Path, dict[str, Any]], dict[str, Any]]
IMPLEMENTED_TASKS: dict[str, Task] = {
    "audio_quality": run_audio_quality,
    "prosody_extract": run_prosody,
}
STATES = ("inbox", "running", "completed", "failed", "cancelled")


def run_with_oom_backoff(operation: Callable[[int], Any], initial_batch: int, max_retries: int = 1) -> tuple[Any, int, int]:
    """Retry CUDA OOM with a halved batch, never beyond the explicit bound."""
    batch = initial_batch
    retries = 0
    while True:
        try:
            return operation(batch), batch, retries
        except WorkerError as exc:
            if exc.code != "CUDA_OOM" or retries >= max_retries or batch <= 1:
                raise
            retries += 1
            batch = max(1, batch // 2)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Worker:
    def __init__(self, root: Path):
        self.root = root.resolve()
        for state in STATES:
            (self.root / "jobs" / state).mkdir(parents=True, exist_ok=True)
        for relative in ("objects/input-cache", "objects/output-cache", "models", "environments", "metrics", "logs", "tmp"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def state_path(self, state: str, job_id: str) -> Path:
        if state not in STATES or not job_id or "/" in job_id or "\\" in job_id or job_id in {".", ".."}:
            raise ValueError("unsafe state or job ID")
        return self.root / "jobs" / state / job_id

    def submit(self, source: Path) -> Path:
        job, _ = validate_job_package(source)
        target = self.state_path("inbox", job["job_id"])
        if any(self.state_path(state, job["job_id"]).exists() for state in STATES):
            raise FileExistsError(f"job already exists: {job['job_id']}")
        staging = self.root / "tmp" / f"submit-{job['job_id']}-{os.getpid()}"
        shutil.copytree(source, staging, symlinks=False)
        validate_job_package(staging)
        staging.replace(target)
        return target

    def _gpu_preflight(self, job: dict[str, Any]) -> None:
        request = job["resource_request"]
        if request["gpu_count"] == 0:
            return
        try:
            output = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout.splitlines()
            free_bytes = int(output[0].strip()) * 1024 * 1024
        except (FileNotFoundError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            raise WorkerError("ENVIRONMENT_MISMATCH", "requested GPU is unavailable") from exc
        if free_bytes < request["min_vram_bytes"]:
            raise WorkerError("ENVIRONMENT_MISMATCH", "available VRAM is below resource request")

    def find_cache(self, fingerprint: str) -> Path | None:
        pointer = self.root / "objects" / "output-cache" / fingerprint
        if not pointer.is_file():
            return None
        job_id = pointer.read_text(encoding="utf-8").strip()
        result = self.state_path("completed", job_id)
        return result if (result / "result.json").is_file() else None

    def run(self, job_id: str, *, force: bool = False) -> Path:
        inbox = self.state_path("inbox", job_id)
        running = self.state_path("running", job_id)
        if not inbox.is_dir():
            raise FileNotFoundError(f"queued job not found: {job_id}")
        inbox.replace(running)
        started = utc_now()
        recorder = MetricsRecorder()
        job: dict[str, Any] | None = None
        fingerprint: str | None = None
        try:
            job, worker_spec = validate_job_package(running)
            fingerprint = transform_fingerprint(job, worker_spec)
            cached = None if force else self.find_cache(fingerprint)
            if cached is not None:
                recorder.cache_hit = True
                output = {"cache_source_job_id": cached.name, "technical_quality_candidate": None}
            else:
                self._gpu_preflight(job)
                task = IMPLEMENTED_TASKS.get(job["task_type"])
                if task is None:
                    raise WorkerError("MODEL_ACCESS_FAILED", f"no pinned backend is installed for {job['task_type']}")
                input_path = resolve_package_path(running, job["inputs"][0]["path"])
                with GpuLock(self.root / "gpu0.lock"):
                    output = task(input_path, job["transform"].get("parameters", {}))
                recorder.input_duration_seconds = output.get("duration_seconds")
            assert_noncanonical_output(output)
            outputs = running / "outputs"
            outputs.mkdir(exist_ok=True)
            atomic_json(outputs / "features.json", output)
            manifest = {
                "protocol_version": 1,
                "job_id": job_id,
                "outputs": [{
                    "path": "outputs/features.json", "sha256": sha256_file(outputs / "features.json"),
                    "size_bytes": (outputs / "features.json").stat().st_size,
                    "media_type": "application/json", "logical_role": "technical_scores",
                    "sample_rate": None, "duration_seconds": recorder.input_duration_seconds,
                }],
            }
            validate_schema("output-manifest", manifest)
            atomic_json(running / "output-manifest.json", manifest)
            recorder.output_count = 1
            metrics = recorder.finish()
            validate_schema("metrics", metrics)
            atomic_json(running / "metrics.json", metrics)
            environment = environment_snapshot(worker_spec["code_commit"])
            atomic_json(running / "environment.json", environment)
            result = {
                "protocol_version": 1, "job_id": job_id, "status": "completed",
                "task_type": job["task_type"], "transform_fingerprint": fingerprint,
                "started_at": started, "completed_at": utc_now(), "worker": environment,
                "outputs": manifest["outputs"], "warnings": [], "errors": [],
            }
            validate_schema("result", result)
            atomic_json(running / "result.json", result)
            target = self.state_path("completed", job_id)
            running.replace(target)
            if not recorder.cache_hit and fingerprint is not None:
                pointer = self.root / "objects" / "output-cache" / fingerprint
                pointer.write_text(job_id + "\n", encoding="utf-8")
            return target
        except Exception as exc:
            error = exc if isinstance(exc, WorkerError) else WorkerError("UNKNOWN", str(exc))
            failure = {
                "protocol_version": 1, "job_id": job_id, "status": "failed",
                "task_type": None if job is None else job["task_type"],
                "transform_fingerprint": fingerprint, "started_at": started,
                "completed_at": utc_now(), "worker": {}, "outputs": [], "warnings": [],
                "errors": [error.as_dict()],
            }
            atomic_json(running / "result.json", failure)
            target = self.state_path("failed", job_id)
            running.replace(target)
            return target

    def recover_stale(self, stale_after_seconds: float) -> list[str]:
        recovered = []
        now = time.time()
        for path in sorted((self.root / "jobs" / "running").iterdir()):
            if not path.is_dir() or now - path.stat().st_mtime < stale_after_seconds:
                continue
            result = path / "result.json"
            target_state = "completed" if result.is_file() and json.loads(result.read_text(encoding="utf-8")).get("status") == "completed" else "failed"
            if target_state == "failed" and not result.exists():
                atomic_json(result, {
                    "protocol_version": 1, "job_id": path.name, "status": "failed", "task_type": None,
                    "transform_fingerprint": None, "started_at": None, "completed_at": utc_now(),
                    "worker": {}, "outputs": [], "warnings": [],
                    "errors": [WorkerError("UNKNOWN", "stale running job recovered").as_dict()],
                })
            path.replace(self.state_path(target_state, path.name))
            recovered.append(path.name)
        return recovered

    def verify(self, job_id: str) -> bool:
        package = self.state_path("completed", job_id)
        manifest = json.loads((package / "output-manifest.json").read_text(encoding="utf-8"))
        validate_schema("output-manifest", manifest)
        for item in manifest["outputs"]:
            path = resolve_package_path(package, item["path"])
            if path.stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
                return False
        return True
