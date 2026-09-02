from __future__ import annotations

import struct
import wave
from pathlib import Path

from ..registry import Registry


def probe_pcm_wave(registry: Registry, object_sha256: str, path: Path) -> dict[str, int | str]:
    with wave.open(str(path), "rb") as audio:
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        rate = audio.getframerate()
        frames = audio.getnframes()
        payload = audio.readframes(frames)
    if width != 2:
        raise ValueError("pilot PCM probe supports signed 16-bit WAV; other codecs use a pinned ffprobe worker")
    values = struct.unpack(f"<{len(payload) // 2}h", payload)
    if not values:
        raise ValueError("audio contains no decodable samples")
    absolute_peak = max(abs(value) for value in values)
    clipping = sum(abs(value) >= 32760 for value in values)
    silent = sum(abs(value) <= 32 for value in values)
    mean = sum(values) / len(values)
    result: dict[str, int | str] = {
        "sample_rate_hz": rate,
        "channels": channels,
        "duration_ms": (frames * 1000) // rate,
        "sample_width_bytes": width,
        "peak_ppm": (absolute_peak * 1_000_000) // 32767,
        "clipping_ppm": (clipping * 1_000_000) // len(values),
        "dc_offset_ppm": int(abs(mean) * 1_000_000 // 32767),
        "silence_ppm": (silent * 1_000_000) // len(values),
        "decoder": "python-wave-pcm16-v1",
    }
    with registry.transaction() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO audio_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (object_sha256, result["sample_rate_hz"], result["channels"], result["duration_ms"],
             result["sample_width_bytes"], result["peak_ppm"], result["clipping_ppm"],
             result["dc_offset_ppm"], result["silence_ppm"], result["decoder"], registry.now()),
        )
        registry.audit(connection, "audio.probed", "audio-probe-worker", "object", object_sha256, result)
    return result
