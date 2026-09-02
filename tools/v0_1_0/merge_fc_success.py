#!/usr/bin/env python3
"""Merge sanitized BF16 function-channel evidence into run metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path


def audio_metadata(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as handle:
        result = {
            "artifact_id": path.name,
            "duration_seconds": handle.getnframes() / handle.getframerate(),
            "sample_rate_hz": handle.getframerate(),
            "channels": handle.getnchannels(),
        }
    result.update({"size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--output-wav", required=True, type=Path)
    args = parser.parse_args()
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    gpu_memory, available = [], []
    with args.telemetry.open(encoding="utf-8") as handle:
        for line in handle:
            sample = json.loads(line)
            if sample.get("gpu_csv"):
                gpu_memory.append(float(sample["gpu_csv"].split(",")[0].strip()))
            if sample.get("system_kib", {}).get("MemAvailable") is not None:
                available.append(sample["system_kib"]["MemAvailable"])
    function_output = receipt.get("function_output", {})
    calls = function_output.get("tool_calls", [])
    responses = function_output.get("tool_responses", [])
    metrics["function_calling"] = {
        "result": receipt.get("result"),
        "tool_side_effects_executed": False,
        "mock_response_used": True,
        "toolcall_envelope_parsed": bool(calls),
        "tool_name": calls[0].get("name") if calls else None,
        "arguments": calls[0].get("arguments") if calls else None,
        "response": responses[0].get("response") if responses else None,
        "spoken_continuation": bool(receipt.get("generated_text")),
        "generated_text": receipt.get("generated_text"),
        "call_step": receipt.get("call_step"),
        "response_step": receipt.get("response_step"),
        "load_seconds": receipt.get("load_seconds"),
        "inference_seconds": receipt.get("inference_seconds"),
        "duration_seconds": receipt.get("duration_seconds"),
        "cuda_max_memory_allocated_bytes": receipt.get("cuda_max_memory_allocated_bytes"),
        "cuda_max_memory_reserved_bytes": receipt.get("cuda_max_memory_reserved_bytes"),
        "peak_gpu_memory_used_mib": max(gpu_memory, default=None),
        "minimum_system_available_kib": min(available, default=None),
        "output_audio": audio_metadata(args.output_wav),
        "raw_artifact_ids": [args.receipt.name, args.telemetry.name],
    }
    args.metrics.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
