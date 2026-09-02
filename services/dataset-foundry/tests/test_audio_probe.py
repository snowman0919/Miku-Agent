from __future__ import annotations

import math
import struct
import wave

from conftest import source
from miku_foundry.store import ObjectStore
from miku_foundry.workers.audio_probe import probe_pcm_wave


def test_pcm_probe_measures_decoded_audio_without_modifying_raw(foundry, tmp_path):
    paths, registry = foundry
    source_id = source(registry)
    wav = tmp_path / "probe.wav"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(2 * math.pi * 220 * i / 16000))) for i in range(16000)))
    digest = ObjectStore(paths, registry).ingest(wav, source_id, media_type="audio/wav")
    before = paths.object_path(digest).read_bytes()
    metrics = probe_pcm_wave(registry, digest, paths.object_path(digest))
    assert metrics["sample_rate_hz"] == 16000
    assert metrics["duration_ms"] == 1000
    assert metrics["clipping_ppm"] == 0
    assert paths.object_path(digest).read_bytes() == before
