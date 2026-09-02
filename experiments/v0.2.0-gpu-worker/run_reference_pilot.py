#!/usr/bin/env python3
"""Generate permitted synthetic PCM fixtures and exercise worker packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "services" / "dataset-gpu-worker" / "src"))

from miku_gpu_worker.executor import Worker  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def make_package(root: Path, task: str, index: int, code_commit: str) -> Path:
    job_id = f"reference-{task}-{index:03d}"
    package = root / job_id
    inputs = package / "inputs"
    inputs.mkdir(parents=True)
    audio = inputs / "input-0.wav"
    rate, duration, frequency = 16000, 0.2, 180 + index * 7
    samples = [int(6000 * math.sin(2 * math.pi * frequency * offset / rate)) for offset in range(int(rate * duration))]
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    item = {"id": "input-0", "path": "inputs/input-0.wav", "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "size_bytes": audio.stat().st_size}
    write_json(package / "job.json", {"protocol_version": 1, "job_id": job_id, "task_type": task, "created_at": "2026-09-03T00:00:00Z", "priority": 50, "inputs": [item], "transform": {"name": task, "version": "reference-1", "parameters": {"frame_ms": 20} if task == "prosody_extract" else {}}, "resource_request": {"gpu_count": 0, "min_vram_bytes": 0, "cpu_threads": 1, "ram_bytes": 67108864}})
    write_json(package / "input-manifest.json", {"protocol_version": 1, "job_id": job_id, "inputs": [{"id": item["id"], "sha256": item["sha256"], "size_bytes": item["size_bytes"]}]})
    write_json(package / "worker-spec.json", {"protocol_version": 1, "code_commit": code_commit, "software_environment": {"python": f"{sys.version_info.major}.{sys.version_info.minor}"}, "determinism": "deterministic", "seed": index, "model_binding": None})
    write_json(package / "source-binding.json", {"protocol_version": 1, "job_id": job_id, "foundry_code_commit": code_commit, "source_ids": [f"generated-tone-{index}"], "rights_status": "owned"})
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count-per-task", type=int, default=50)
    parser.add_argument("--code-commit", default="0" * 40)
    args = parser.parse_args()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="miku-worker-pilot-") as temporary:
        base = Path(temporary)
        worker = Worker(base / "worker")
        completed = failed = cache_hits = input_bytes = output_bytes = 0
        for task in ("audio_quality", "prosody_extract"):
            for index in range(args.count_per_task):
                package = make_package(base / "packages", task, index, args.code_commit)
                input_bytes += (package / "inputs" / "input-0.wav").stat().st_size
                worker.submit(package)
                target = worker.run(package.name)
                result = json.loads((target / "result.json").read_text(encoding="utf-8"))
                if target.parent.name == "completed" and worker.verify(package.name):
                    completed += 1
                    metrics = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
                    cache_hits += int(metrics["cache_hit"])
                    output_bytes += sum(item["size_bytes"] for item in result["outputs"])
                else:
                    failed += 1
        print(json.dumps({
            "fixture_kind": "generated_synthetic_pcm_tones", "job_count": completed + failed,
            "completed": completed, "failed": failed, "cache_hits": cache_hits,
            "input_bytes": input_bytes, "processed_audio_duration_seconds": completed * 0.2,
            "output_bytes": output_bytes, "wall_seconds": time.monotonic() - started,
        }, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
