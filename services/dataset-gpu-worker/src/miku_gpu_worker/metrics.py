"""Portable host/GPU metrics collection."""

from __future__ import annotations

import os
import platform
import resource
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def nvidia_smi_command() -> str | None:
    command = shutil.which("nvidia-smi")
    if command:
        return command
    wsl_command = "/usr/lib/wsl/lib/nvidia-smi"
    return wsl_command if Path(wsl_command).is_file() and os.access(wsl_command, os.X_OK) else None


def _nvidia_query(fields: str) -> list[str] | None:
    command = nvidia_smi_command()
    if command is None:
        return None
    try:
        completed = subprocess.run(
            [command, f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    lines = completed.stdout.splitlines()
    return [part.strip() for part in lines[0].split(",")] if lines else None


def environment_snapshot(code_commit: str) -> dict[str, Any]:
    gpu = _nvidia_query("name,uuid,driver_version,memory.total")
    return {
        "hostname": socket.gethostname(), "platform": platform.platform(),
        "python": platform.python_version(), "code_commit": code_commit,
        "gpu": None if gpu is None else {
            "name": gpu[0], "uuid": gpu[1], "driver": gpu[2], "memory_total_mib": int(gpu[3]),
        },
    }


@dataclass(slots=True)
class MetricsRecorder:
    started: float = field(default_factory=time.monotonic)
    retry_count: int = 0
    error_count: int = 0
    cache_hit: bool = False
    input_duration_seconds: float | None = None
    output_count: int = 0
    gpu_peak_vram_mib: float | None = None
    gpu_average_utilization_percent: float | None = None
    gpu_energy_joules: float | None = None

    def finish(self) -> dict[str, Any]:
        wall = time.monotonic() - self.started
        duration = self.input_duration_seconds
        return {
            "wall_seconds": wall,
            "input_duration_seconds": duration,
            "processed_audio_seconds_per_wall_second": None if duration is None or wall == 0 else duration / wall,
            "output_count": self.output_count,
            "host_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "gpu_peak_vram_mib": self.gpu_peak_vram_mib,
            "gpu_average_utilization_percent": self.gpu_average_utilization_percent,
            "gpu_energy_joules": self.gpu_energy_joules,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "cache_hit": self.cache_hit,
        }


class GpuSampler:
    """Sample supported nvidia-smi metrics without failing the job when unavailable."""

    def __init__(self, recorder: MetricsRecorder, interval_seconds: float = 0.1):
        self.recorder = recorder
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._memory: list[float] = []
        self._utilization: list[float] = []
        self._power: list[tuple[float, float]] = []

    def _sample(self) -> None:
        values = _nvidia_query("memory.used,utilization.gpu,power.draw")
        if values is None or len(values) != 3:
            return
        try:
            memory, utilization, power = (float(value) for value in values)
        except ValueError:
            return
        self._memory.append(memory)
        self._utilization.append(utilization)
        self._power.append((time.monotonic(), power))

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def __enter__(self) -> "GpuSampler":
        self._sample()
        self._thread = threading.Thread(target=self._run, name="miku-gpu-metrics", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_seconds * 2))
        self._sample()
        if self._memory:
            self.recorder.gpu_peak_vram_mib = max(self._memory)
            self.recorder.gpu_average_utilization_percent = sum(self._utilization) / len(self._utilization)
            self.recorder.gpu_energy_joules = sum((left[1] + right[1]) * (right[0] - left[0]) / 2 for left, right in zip(self._power, self._power[1:]))
