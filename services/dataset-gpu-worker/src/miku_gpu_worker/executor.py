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
from .metrics import GpuSampler, MetricsRecorder, environment_snapshot, nvidia_smi_command
from .protocol import assert_noncanonical_output, resolve_package_path, validate_job_package, validate_schema
from .registry import REPOSITORY_ROOT, validate_binding
from .tasks import (
    run_alignment,
    run_asr,
    run_audio_quality,
    run_prosody,
    run_separation,
    run_speaker_embedding,
)

Task = Callable[[Path, dict[str, Any]], dict[str, Any]]
IMPLEMENTED_TASKS: dict[str, Task] = {
    "audio_quality": run_audio_quality,
    "prosody_extract": run_prosody,
    "source_separation": run_separation,
    "asr_transcribe": run_asr,
    "forced_alignment": run_alignment,
    "speaker_embedding": run_speaker_embedding,
}
MODEL_TASKS = frozenset({
    "source_separation", "asr_transcribe", "forced_alignment", "speaker_embedding",
})
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
        for relative in ("jobs/.locks", "objects/input-cache", "objects/output-cache", "models", "environments", "metrics", "logs", "tmp"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def state_path(self, state: str, job_id: str) -> Path:
        if state not in STATES or not job_id or "/" in job_id or "\\" in job_id or job_id in {".", ".."}:
            raise ValueError("unsafe state or job ID")
        return self.root / "jobs" / state / job_id

    def job_lock(self, job_id: str) -> GpuLock:
        self.state_path("inbox", job_id)
        return GpuLock(self.root / "jobs" / ".locks" / f"{job_id}.lock")

    def submit(self, source: Path) -> Path:
        job, _ = validate_job_package(source)
        with self.job_lock(job["job_id"]):
            target = self.state_path("inbox", job["job_id"])
            if any(self.state_path(state, job["job_id"]).exists() for state in STATES):
                raise FileExistsError(f"job already exists: {job['job_id']}")
            staging = self.root / "tmp" / f"submit-{job['job_id']}-{os.getpid()}"
            try:
                shutil.copytree(source, staging, symlinks=False)
                validate_job_package(staging)
                staging.replace(target)
            except Exception:
                if staging.exists():
                    shutil.rmtree(staging)
                raise
            return target

    def _gpu_preflight(self, job: dict[str, Any]) -> None:
        request = job["resource_request"]
        if request["gpu_count"] == 0:
            return
        command = nvidia_smi_command()
        if command is None:
            raise WorkerError("ENVIRONMENT_MISMATCH", "requested GPU is unavailable")
        try:
            lines = subprocess.run(
                [command, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout.splitlines()
            free_bytes = int(lines[0].strip()) * 1024 * 1024
        except (FileNotFoundError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            raise WorkerError("ENVIRONMENT_MISMATCH", "requested GPU is unavailable") from exc
        if free_bytes < request["min_vram_bytes"]:
            raise WorkerError("ENVIRONMENT_MISMATCH", "available VRAM is below resource request")

    def _snapshot_input(self, package: Path, item: dict[str, Any]) -> Path:
        source = resolve_package_path(package, item["path"])
        suffix = Path(item["path"]).suffix.lower()
        target = self.root / "objects" / "input-cache" / f"{item['sha256']}{suffix}"
        if target.is_file() and target.stat().st_size == item["size_bytes"] and sha256_file(target) == item["sha256"]:
            return target
        temporary = self.root / "tmp" / f"input-{item['sha256']}-{os.getpid()}"
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            if temporary.stat().st_size != item["size_bytes"] or sha256_file(temporary) != item["sha256"]:
                raise WorkerError("INPUT_HASH_MISMATCH", f"input changed during snapshot: {item['id']}")
            os.chmod(temporary, 0o444)
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.stat().st_size != item["size_bytes"] or sha256_file(target) != item["sha256"]:
                    raise WorkerError("INPUT_HASH_MISMATCH", "content-addressed input cache conflict")
            return target
        finally:
            if temporary.exists():
                temporary.unlink()

    def _model_context(self, task: str, binding: dict[str, Any] | None) -> tuple[dict[str, Any], Path]:
        if binding is None:
            raise WorkerError("MODEL_HASH_MISMATCH", f"{task} requires a model binding")
        entry = validate_binding(task, binding)
        lock = REPOSITORY_ROOT / "experiments/v0.2.0-gpu-worker/environments/audio/uv.lock"
        if sha256_file(lock) != binding["environment_lock_sha256"]:
            raise WorkerError("ENVIRONMENT_MISMATCH", "audio environment lock hash differs")
        if task == "source_separation":
            model_path = self.root / "models" / "torch"
            weight = model_path / "hub" / "checkpoints" / entry["weight_file"]
        else:
            repository = entry.get("repository", "")
            model_id = (
                repository.removeprefix("https://huggingface.co/").rstrip("/")
                if repository.startswith("https://huggingface.co/")
                else entry["model_id"]
            )
            model_path = (
                self.root / "models" / "huggingface" / "hub"
                / f"models--{model_id.replace('/', '--')}"
                / "snapshots" / entry["revision"]
            )
            weight = model_path / entry["weight_file"]
        if not model_path.is_dir() or not weight.is_file() or sha256_file(weight) != binding["weight_sha256"]:
            raise WorkerError("MODEL_HASH_MISMATCH", "pinned model bytes are missing or changed")
        config_file = entry.get("config_file")
        if config_file:
            config = model_path / config_file
            if not config.is_file() or sha256_file(config) != binding["config_sha256"]:
                raise WorkerError("MODEL_HASH_MISMATCH", "pinned model config changed")
        return dict(binding), model_path

    def _verify_package(self, package: Path, expected_fingerprint: str | None = None) -> bool:
        try:
            result = json.loads((package / "result.json").read_text(encoding="utf-8"))
            validate_schema("result", result)
            if result["status"] != "completed" or result["job_id"] != package.name or not isinstance(result["transform_fingerprint"], str) or (expected_fingerprint and result["transform_fingerprint"] != expected_fingerprint):
                return False
            manifest = json.loads((package / "output-manifest.json").read_text(encoding="utf-8"))
            validate_schema("output-manifest", manifest)
            if manifest["job_id"] != result["job_id"] or manifest["outputs"] != result["outputs"]:
                return False
            for item in manifest["outputs"]:
                path = resolve_package_path(package, item["path"])
                if path.stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
                    return False
                if item["media_type"] == "application/json":
                    assert_noncanonical_output(json.loads(path.read_text(encoding="utf-8")))
            return True
        except (OSError, ValueError, json.JSONDecodeError, WorkerError):
            return False

    def find_cache(self, fingerprint: str) -> Path | None:
        pointer = self.root / "objects" / "output-cache" / fingerprint
        if not pointer.is_file():
            return None
        try:
            result = self.state_path("completed", pointer.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
        return result if self._verify_package(result, fingerprint) else None

    def _materialize_cache(self, cached: Path, running: Path, job_id: str) -> dict[str, Any]:
        source_manifest = json.loads((cached / "output-manifest.json").read_text(encoding="utf-8"))
        outputs = []
        for item in source_manifest["outputs"]:
            source = resolve_package_path(cached, item["path"])
            destination = running / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
            if destination.stat().st_size != item["size_bytes"] or sha256_file(destination) != item["sha256"]:
                raise WorkerError("OUTPUT_HASH_FAILED", f"cache output changed during copy: {item['path']}")
            copied = dict(item)
            outputs.append(copied)
        return {"protocol_version": 1, "job_id": job_id, "outputs": outputs}

    def run(self, job_id: str, *, force: bool = False) -> Path:
        with self.job_lock(job_id):
            return self._run_owned(job_id, force=force)

    def _run_owned(self, job_id: str, *, force: bool) -> Path:
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
                manifest = self._materialize_cache(cached, running, job_id)
                recorder.input_duration_seconds = manifest["outputs"][0].get("duration_seconds")
            else:
                self._gpu_preflight(job)
                task = IMPLEMENTED_TASKS.get(job["task_type"])
                if task is None:
                    raise WorkerError("MODEL_ACCESS_FAILED", f"no pinned backend is installed for {job['task_type']}")
                if job["task_type"] not in MODEL_TASKS and worker_spec.get("model_binding") is not None:
                    raise WorkerError("MODEL_HASH_MISMATCH", f"{job['task_type']} reference backend cannot honor a model binding")
                input_path = self._snapshot_input(running, job["inputs"][0])
                outputs = running / "outputs"
                outputs.mkdir(exist_ok=True)
                parameters = dict(job["transform"].get("parameters", {}))
                if job["task_type"] in MODEL_TASKS:
                    binding, model_path = self._model_context(
                        job["task_type"], worker_spec.get("model_binding")
                    )
                    parameters.update({
                        "_model_binding": binding,
                        "_model_path": str(model_path),
                        "_output_dir": str(outputs),
                    })
                sampler = GpuSampler(recorder) if job["resource_request"]["gpu_count"] else None
                with GpuLock(self.root / "gpu0.lock"):
                    if sampler is None:
                        output = task(input_path, parameters)
                    else:
                        with sampler:
                            output = task(input_path, parameters)
                artifacts = output.pop("_artifacts", [])
                assert_noncanonical_output(output)
                atomic_json(outputs / "features.json", output)
                recorder.input_duration_seconds = output.get("duration_seconds")
                manifest_outputs = [{
                    "path": "outputs/features.json", "sha256": sha256_file(outputs / "features.json"),
                    "size_bytes": (outputs / "features.json").stat().st_size,
                    "media_type": "application/json", "logical_role": "technical_scores",
                    "sample_rate": None, "duration_seconds": recorder.input_duration_seconds,
                }]
                for artifact in artifacts:
                    artifact_path = Path(artifact["path"])
                    if artifact_path.parent != outputs or not artifact_path.is_file():
                        raise WorkerError("MODEL_OUTPUT_INVALID", "task artifact escaped output directory")
                    manifest_outputs.append({
                        "path": f"outputs/{artifact_path.name}",
                        "sha256": sha256_file(artifact_path),
                        "size_bytes": artifact_path.stat().st_size,
                        "media_type": artifact["media_type"],
                        "logical_role": artifact["logical_role"],
                        "sample_rate": artifact.get("sample_rate"),
                        "duration_seconds": recorder.input_duration_seconds,
                    })
                manifest = {"protocol_version": 1, "job_id": job_id, "outputs": manifest_outputs}
            validate_schema("output-manifest", manifest)
            atomic_json(running / "output-manifest.json", manifest)
            recorder.output_count = len(manifest["outputs"])
            metrics = recorder.finish()
            validate_schema("metrics", metrics)
            atomic_json(running / "metrics.json", metrics)
            environment = environment_snapshot(worker_spec["code_commit"])
            validate_schema("environment", environment)
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
                (self.root / "objects" / "output-cache" / fingerprint).write_text(job_id + "\n", encoding="utf-8")
            return target
        except Exception as exc:
            recorder.error_count = 1
            error = exc if isinstance(exc, WorkerError) else WorkerError("UNKNOWN", str(exc))
            atomic_json(running / "metrics.json", recorder.finish())
            failure = {
                "protocol_version": 1, "job_id": job_id, "status": "failed",
                "task_type": None if job is None else job["task_type"],
                "transform_fingerprint": fingerprint, "started_at": started,
                "completed_at": utc_now(), "worker": {}, "outputs": [], "warnings": [],
                "errors": [error.as_dict()],
            }
            validate_schema("result", failure)
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
            lock = self.job_lock(path.name)
            try:
                lock.acquire()
            except BlockingIOError:
                continue
            try:
                if not path.exists() or now - path.stat().st_mtime < stale_after_seconds:
                    continue
                result = path / "result.json"
                try:
                    job, worker_spec = validate_job_package(path)
                    expected_fingerprint = transform_fingerprint(job, worker_spec)
                except (OSError, ValueError, json.JSONDecodeError, WorkerError):
                    expected_fingerprint = None
                target_state = "completed" if expected_fingerprint and self._verify_package(path, expected_fingerprint) else "failed"
                if target_state == "failed" and not result.exists():
                    atomic_json(result, {
                        "protocol_version": 1, "job_id": path.name, "status": "failed", "task_type": None,
                        "transform_fingerprint": None, "started_at": None, "completed_at": utc_now(),
                        "worker": {}, "outputs": [], "warnings": [],
                        "errors": [WorkerError("UNKNOWN", "stale running job recovered").as_dict()],
                    })
                path.replace(self.state_path(target_state, path.name))
                recovered.append(path.name)
            finally:
                lock.release()
        return recovered

    def verify(self, job_id: str) -> bool:
        return self._verify_package(self.state_path("completed", job_id))
