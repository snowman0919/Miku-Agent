#!/usr/bin/env python3
"""Attach a sanitized official function-calling failure to run metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--stderr", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--wall-seconds", required=True, type=float)
    parser.add_argument("--error-output", required=True, type=Path)
    args = parser.parse_args()
    gpu_memory, available = [], []
    with args.telemetry.open(encoding="utf-8") as handle:
        for line in handle:
            sample = json.loads(line)
            csv = sample.get("gpu_csv")
            if csv:
                gpu_memory.append(float(csv.split(",")[0].strip()))
            value = sample.get("system_kib", {}).get("MemAvailable")
            if value is not None:
                available.append(value)
    stderr = args.stderr.read_text(encoding="utf-8", errors="replace")
    excerpt = stderr[-12000:]
    args.error_output.write_text(excerpt + ("\n" if not excerpt.endswith("\n") else ""), encoding="utf-8")
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    metrics["function_calling"] = {
        "result": "failed",
        "exit_code": 1,
        "wall_seconds": args.wall_seconds,
        "tool_side_effects_executed": False,
        "mock_response_used": True,
        "toolcall_envelope_parsed": False,
        "spoken_continuation": False,
        "failure_stage": "pass-1 autoregressive inference near step 550 of 859",
        "exception_type": "torch.AcceleratorError",
        "exception": "CUDA error: out of memory (cudaErrorMemoryAllocation)",
        "peak_gpu_memory_used_mib": max(gpu_memory, default=None),
        "minimum_system_available_kib": min(available, default=None),
        "raw_artifact_ids": [args.stderr.name, args.telemetry.name],
    }
    args.metrics.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
