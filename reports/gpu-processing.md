# GPU Processing

## RTX 3080 Canonical Node

Canonical registry/object store만 authoritative writer다. Worker package 생성, 반환 hash 검증,
atomic object ingest, lineage와 quarantine review 등록을 수행했다. Canonical root는 약 800.6 MB,
free 약 63.70 GB다. 50 GiB 아래에서는 대량 intake/transform을 중단하고 원본이나
accepted data를 삭제하지 않는다.

## RTX 5090 Worker

- Root: configured worker root, 약 14.15 GB; free 846,326,464,512 bytes.
- Completed/imported: separation 10, ASR 100, alignment 50, embedding 100, quality 100, prosody 100.
- Idempotency: 460개 successful result package를 각각 재수입했고 canonical count가 증가하지 않았다.
- Failure: X-vector config 선택 오류 1건은 `MODEL_HASH_MISMATCH`로 fail-closed; 수정 후 replacement 성공.
- Legacy job 1건은 원래 `waiting_for_lease` 상태로 보존했다.
- Model cache 약 5.71 GB는 revision이 기록된 재다운로드 가능 cache이며 이번에 삭제하지 않았다.

Pinned model은 htdemucs, Whisper large-v3-turbo, MMS Korean aligner와 SpeechBrain X-vector다.
MMS output은 `BLOCKED_NONCOMMERCIAL`, X-vector output은 `NOT CALIBRATED`로 유지했다.
V0.1.0 process, repository와 system package는 변경하지 않았다.
