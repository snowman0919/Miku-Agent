#!/usr/bin/env python3
"""Write high-frequency GPU/process/system telemetry as JSON Lines."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def read_kv(path: str, keys: set[str]) -> dict[str, int]:
    result = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            key, _, raw = line.partition(":")
            if key in keys:
                result[key] = int(raw.strip().split()[0])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    if not 0.1 <= args.interval <= 0.5:
        parser.error("--interval must be between 0.1 and 0.5 seconds")
    start = time.monotonic()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        while args.duration is None or time.monotonic() - start < args.duration:
            sample: dict[str, object] = {
                "unix_seconds": time.time(),
                "elapsed_seconds": time.monotonic() - start,
                "system_kib": read_kv("/proc/meminfo", {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}),
            }
            if args.pid and Path(f"/proc/{args.pid}/status").exists():
                sample["process_kib"] = read_kv(f"/proc/{args.pid}/status", {"VmRSS", "VmHWM", "VmSize", "VmPeak"})
            query = subprocess.run([
                "/usr/lib/wsl/lib/nvidia-smi",
                "--query-gpu=memory.used,memory.free,utilization.gpu,power.draw,temperature.gpu,clocks.sm,clocks.mem",
                "--format=csv,noheader,nounits",
            ], text=True, capture_output=True, check=False)
            sample["gpu_csv"] = query.stdout.strip() if query.returncode == 0 else None
            output.write(json.dumps(sample, sort_keys=True) + "\n")
            output.flush()
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
