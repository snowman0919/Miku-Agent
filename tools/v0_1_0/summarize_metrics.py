#!/usr/bin/env python3
"""Reduce a raw load-probe receipt to small, committable metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = json.loads(args.receipt.read_text(encoding="utf-8"))
    samples = raw.get("telemetry", [])
    gpu_used = [s.get("gpu", {}).get("memory_used_mib") for s in samples]
    gpu_used = [x for x in gpu_used if isinstance(x, (int, float))]
    rss = [s.get("process", {}).get("VmRSS_kib") for s in samples]
    rss = [x for x in rss if isinstance(x, int)]
    available = [s.get("system", {}).get("MemAvailable_kib") for s in samples]
    available = [x for x in available if isinstance(x, int)]
    inference = raw.get("inference")
    if isinstance(inference, dict):
        inference = {key: value for key, value in inference.items() if key not in {"input_wav", "output_paths"}}
        paths = raw["inference"].get("output_paths", {})
        output_path = Path(paths["output"]) if paths.get("output") else None
        if output_path and output_path.is_file():
            with wave.open(str(output_path), "rb") as handle:
                inference["output_audio"] = {
                    "artifact_id": output_path.name,
                    "duration_seconds": handle.getnframes() / handle.getframerate(),
                    "sample_rate_hz": handle.getframerate(),
                    "channels": handle.getnchannels(),
                    "size_bytes": output_path.stat().st_size,
                    "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
                }
    keep = {
        "schema_version": 1,
        "mode": raw.get("mode"),
        "result": raw.get("result"),
        "duration_seconds": raw.get("duration_seconds"),
        "load_seconds": raw.get("load_seconds"),
        "torch": raw.get("torch"),
        "exception_type": raw.get("exception_type"),
        "exception": raw.get("exception"),
        "cuda_max_memory_allocated_bytes": raw.get("cuda_max_memory_allocated_bytes"),
        "cuda_max_memory_reserved_bytes": raw.get("cuda_max_memory_reserved_bytes"),
        "peak_nvidia_smi_memory_used_mib": max(gpu_used, default=None),
        "peak_process_rss_kib": max(rss, default=None),
        "minimum_system_available_kib": min(available, default=None),
        "inference": inference,
        "raw_artifact_id": args.receipt.name,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(keep, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
