"""Job package validation and safe path resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import WorkerError
from .hashing import sha256_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPOSITORY_ROOT / "schemas" / "gpu-worker"
TASK_TYPES = frozenset(
    {
        "source_separation", "asr_transcribe", "forced_alignment",
        "speaker_embedding", "speaker_similarity", "audio_embedding",
        "speech_singing_score", "prosody_extract", "audio_quality",
        "miku_voice_consistency", "persona_critic", "agentic_critic",
        "synthetic_persona_generate", "synthetic_agentic_generate",
    }
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerError("MODEL_OUTPUT_INVALID", f"invalid JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkerError("MODEL_OUTPUT_INVALID", f"{path.name} must contain an object")
    return value


def validate_schema(name: str, value: dict[str, Any]) -> None:
    schema = json.loads((SCHEMA_ROOT / f"{name}.schema.json").read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(error.message for error in errors)
        raise WorkerError("MODEL_OUTPUT_INVALID", f"{name} schema validation failed: {details}")


def resolve_package_path(package_root: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not relative or Path(relative).is_absolute():
        raise WorkerError("UNSUPPORTED_FORMAT", "package paths must be non-empty and relative")
    root = package_root.resolve()
    candidate = package_root.joinpath(relative)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise WorkerError("INPUT_DECODE_FAILED", f"cannot resolve package path: {relative}") from exc
    if not resolved.is_relative_to(root):
        raise WorkerError("UNSUPPORTED_FORMAT", f"package path escapes root: {relative}")
    cursor = candidate
    while cursor != package_root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise WorkerError("UNSUPPORTED_FORMAT", f"symlink package path rejected: {relative}")
        cursor = cursor.parent
    return resolved


def validate_job_package(package_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    job = load_json(package_root / "job.json")
    input_manifest = load_json(package_root / "input-manifest.json")
    worker_spec = load_json(package_root / "worker-spec.json")
    source_binding = load_json(package_root / "source-binding.json")
    validate_schema("job", job)
    validate_schema("input-manifest", input_manifest)
    validate_schema("worker-spec", worker_spec)
    validate_schema("source-binding", source_binding)
    if input_manifest["job_id"] != job["job_id"] or source_binding["job_id"] != job["job_id"]:
        raise WorkerError("MODEL_OUTPUT_INVALID", "package job IDs do not agree")
    expected = {(item["id"], item["sha256"], item["size_bytes"]) for item in job["inputs"]}
    manifested = {(item["id"], item["sha256"], item["size_bytes"]) for item in input_manifest["inputs"]}
    if manifested != expected:
        raise WorkerError("INPUT_HASH_MISMATCH", "input manifest does not match job inputs")
    if job["task_type"] not in TASK_TYPES:
        raise WorkerError("UNSUPPORTED_FORMAT", f"unknown task type: {job['task_type']}")
    for item in job["inputs"]:
        path = resolve_package_path(package_root, item["path"])
        if not path.is_file() or path.stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
            raise WorkerError("INPUT_HASH_MISMATCH", f"input integrity mismatch: {item['id']}")
    return job, worker_spec


def assert_noncanonical_output(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = {"accepted_for_training", "training_status", "rights_status", "eval_split"}
        intersection = forbidden.intersection(value)
        if intersection:
            raise WorkerError("MODEL_OUTPUT_INVALID", f"canonical fields forbidden in worker output: {sorted(intersection)}")
        for nested in value.values():
            assert_noncanonical_output(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_noncanonical_output(nested)
