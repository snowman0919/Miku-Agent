# Audio Quality Pilot

- Unique sources/objects: 10/10.
- Decoded format: mono PCM16 WAV, 16,000 Hz, unique physical duration 10,000 ms.
- Logical segment-reference duration: 100,000 ms.
- Maximum clipping ratio: 0 ppm; maximum measured DC offset: 0 ppm.
- Accepted/effective speech: 0/0 ms.

Audio는 deterministic sine probe다. Object ingest, decode metric, sample indexing과 review 경로만 검증하며 ASR, alignment, speaker identity, speech likeness 또는 target voice quality를 PASS로 만들지 않는다. GPU separation/ASR job은 실행하지 않았다.
