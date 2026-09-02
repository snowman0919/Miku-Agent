"""Dependency-free PCM WAV probes used for protocol pilots.

These are calibrated proxies, not canonical quality or acceptance decisions.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Any

from ..errors import WorkerError


def _samples(path: Path) -> tuple[list[float], int, int]:
    if path.suffix.lower() != ".wav":
        raise WorkerError("UNSUPPORTED_FORMAT", "reference audio probes support PCM WAV only")
    try:
        with wave.open(str(path), "rb") as stream:
            channels = stream.getnchannels()
            width = stream.getsampwidth()
            rate = stream.getframerate()
            frames = stream.getnframes()
            if width != 2 or stream.getcomptype() != "NONE":
                raise WorkerError("UNSUPPORTED_FORMAT", "reference audio probes require PCM16 WAV")
            raw = stream.readframes(frames)
    except (wave.Error, EOFError, OSError) as exc:
        raise WorkerError("INPUT_DECODE_FAILED", f"WAV decode failed: {exc}") from exc
    unpacked = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = [sum(unpacked[index:index + channels]) / (channels * 32768.0) for index in range(0, len(unpacked), channels)]
    return mono, rate, channels


def _basic(path: Path) -> tuple[dict[str, Any], list[float], int]:
    samples, rate, channels = _samples(path)
    if not samples:
        raise WorkerError("INPUT_DECODE_FAILED", "audio contains no frames")
    peak = max(abs(value) for value in samples)
    mean = sum(samples) / len(samples)
    rms = math.sqrt(sum(value * value for value in samples) / len(samples))
    duration = len(samples) / rate
    clipping = sum(abs(value) >= 0.999 for value in samples) / len(samples)
    zero_crossings = sum((a < 0) != (b < 0) for a, b in zip(samples, samples[1:]))
    return {
        "format": "audio/wav; codec=pcm_s16le",
        "sample_rate": rate,
        "channels": channels,
        "duration_seconds": duration,
        "peak": peak,
        "rms": rms,
        "dc_offset": mean,
        "clipping_fraction": clipping,
        "zero_crossing_rate": zero_crossings / max(1, len(samples) - 1),
    }, samples, rate


def run_audio_quality(path: Path, _: dict[str, Any]) -> dict[str, Any]:
    basic, samples, _rate = _basic(path)
    sorted_abs = sorted(abs(value) for value in samples)
    noise_floor = sorted_abs[max(0, int(len(sorted_abs) * 0.1) - 1)]
    basic.update(
        {
            "snr_proxy_db": None if noise_floor == 0 else 20 * math.log10(max(basic["rms"], 1e-12) / noise_floor),
            "noise_floor_amplitude_proxy": noise_floor,
            "calibration_status": "NOT CALIBRATED",
            "technical_quality_candidate": basic["clipping_fraction"] < 0.01 and abs(basic["dc_offset"]) < 0.05,
        }
    )
    return basic


def _f0(frame: list[float], rate: int, minimum: float = 80, maximum: float = 500) -> float | None:
    mean = sum(frame) / len(frame)
    centered = [value - mean for value in frame]
    minimum_lag = max(1, int(rate / maximum))
    maximum_lag = min(len(frame) - 2, int(rate / minimum))
    if maximum_lag <= minimum_lag:
        return None
    correlations = [sum(centered[index] * centered[index + lag] for index in range(len(centered) - lag)) for lag in range(minimum_lag, maximum_lag + 1)]
    best = max(range(len(correlations)), key=correlations.__getitem__)
    return rate / (minimum_lag + best) if correlations[best] > 0 else None


def run_prosody(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    basic, samples, rate = _basic(path)
    frame_ms = int(parameters.get("frame_ms", 20))
    frame_size = max(1, rate * frame_ms // 1000)
    energy = []
    for start in range(0, len(samples), frame_size):
        frame = samples[start:start + frame_size]
        energy.append(math.sqrt(sum(value * value for value in frame) / len(frame)))
    threshold = min(max(0.005, sorted(energy)[max(0, len(energy) // 5 - 1)] * 2), max(energy) * 0.5)
    voiced = [value >= threshold for value in energy]
    f0 = [_f0(samples[start:start + frame_size], rate) if active else None for start, active in zip(range(0, len(samples), frame_size), voiced)]
    pauses = []
    pause_start = None
    for index, active in enumerate(voiced + [True]):
        if not active and pause_start is None:
            pause_start = index
        elif active and pause_start is not None:
            pauses.append({"start_seconds": pause_start * frame_ms / 1000, "end_seconds": index * frame_ms / 1000})
            pause_start = None
    voiced_f0 = [value for value in f0 if value is not None]
    voiced_starts = sum(active and (index == 0 or not voiced[index - 1]) for index, active in enumerate(voiced))
    return {
        "duration_seconds": basic["duration_seconds"],
        "frame_ms": frame_ms,
        "energy_rms": energy,
        "voiced": voiced,
        "pause_intervals": pauses,
        "speaking_rate_estimate": voiced_starts / basic["duration_seconds"],
        "f0_hz": f0,
        "pitch_range_hz": None if not voiced_f0 else max(voiced_f0) - min(voiced_f0),
        "limitations": ["F0 uses reference autocorrelation", "voicing and speaking rate are energy proxies", "NOT CALIBRATED"],
    }
