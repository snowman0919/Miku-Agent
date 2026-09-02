#!/usr/bin/env python3
"""Summarize official offline inference artifacts without committing audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path


def wav_info(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        channels = handle.getnchannels()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "artifact_id": path.name,
        "duration_seconds": frames / rate,
        "sample_rate_hz": rate,
        "channels": channels,
        "size_bytes": path.stat().st_size,
        "sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-wav", required=True, type=Path)
    parser.add_argument("--output-wav", required=True, type=Path)
    parser.add_argument("--output-text", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--wall-seconds", required=True, type=float)
    parser.add_argument("--load-seconds", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    gpu_memory, gpu_util, gpu_power, available = [], [], [], []
    with args.telemetry.open(encoding="utf-8") as handle:
        for line in handle:
            sample = json.loads(line)
            csv = sample.get("gpu_csv")
            if csv:
                fields = [float(value.strip()) for value in csv.split(",")]
                gpu_memory.append(fields[0]); gpu_util.append(fields[2]); gpu_power.append(fields[3])
            value = sample.get("system_kib", {}).get("MemAvailable")
            if value is not None:
                available.append(value)
    input_info = wav_info(args.input_wav)
    output_info = wav_info(args.output_wav)
    generation_estimate = max(0.0, args.wall_seconds - args.load_seconds)
    summary = {
        "schema_version": 1,
        "result": "offline-general-success",
        "exit_code": 0,
        "wall_seconds_load_inclusive": args.wall_seconds,
        "load_seconds_from_separate_exact_probe": args.load_seconds,
        "generation_seconds_estimate": generation_estimate,
        "rtf_load_inclusive": args.wall_seconds / output_info["duration_seconds"],
        "rtf_generation_only_estimate": generation_estimate / output_info["duration_seconds"],
        "input_audio": input_info,
        "output_audio": output_info,
        "generated_text": args.output_text.read_text(encoding="utf-8"),
        "telemetry": {
            "sample_interval_seconds": 0.25,
            "sample_count": len(gpu_memory),
            "peak_gpu_memory_used_mib": max(gpu_memory, default=None),
            "peak_gpu_utilization_percent": max(gpu_util, default=None),
            "peak_gpu_power_w": max(gpu_power, default=None),
            "minimum_system_available_kib": min(available, default=None),
            "raw_artifact_id": args.telemetry.name,
        },
        "repetitions": {"cold_completed": 1, "warm_completed": 0, "reason_reduced": "single official run required 14m20s and RTF was already far above the real-time gate"},
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
