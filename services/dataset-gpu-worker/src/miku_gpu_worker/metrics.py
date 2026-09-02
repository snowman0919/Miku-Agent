"""Portable host/GPU metrics collection."""

from __future__ import annotations

import platform
import resource
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


def _nvidia_query(fields: str) -> list[str] | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    line = completed.stdout.splitlines()
    return [part.strip() for part in line[0].split(",")] if line else None


def environment_snapshot(code_commit: str) -> dict[str, Any]:
    gpu = _nvidia_query("name,uuid,driver_version,memory.total")
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "code_commit": code_commit,
        "gpu": None if gpu is None else {
            "name": gpu[0], "uuid": gpu[1], "driver": gpu[2], "memory_total_mib": int(gpu[3]),
        },
    }


@dataclass(slots=True)
class MetricsRecorder:
    started: float = field(default_factory=time.monotonic)
    retry_count: int = 0
    cache_hit: bool = False
    input_duration_seconds: float | None = None
    output_count: int = 0

    def finish(self) -> dict[str, Any]:
        wall = time.monotonic() - self.started
        duration = self.input_duration_seconds
        return {
            "wall_seconds": wall,
            "input_duration_seconds": duration,
            "processed_audio_seconds_per_wall_second": None if duration is None or wall == 0 else duration / wall,
            "output_count": self.output_count,
            "host_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "gpu_peak_vram_mib": None,
            "gpu_average_utilization_percent": None,
            "gpu_energy_joules": None,
            "error_count": 0,
            "retry_count": self.retry_count,
            "cache_hit": self.cache_hit,
        }

