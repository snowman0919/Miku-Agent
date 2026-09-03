# GPU Processing

## RTX 3080 Canonical Node

Canonical registry/object store만 authoritative writer다. Worker package 생성, 반환 hash 검증,
atomic object ingest, lineage와 quarantine review 등록을 수행했다. Canonical root는
4,564,347,015 bytes, free 70,636,040,192 bytes다. 50 GiB 아래에서는 대량 intake/transform을
중단하고 원본이나 accepted data를 삭제하지 않는다.

## RTX 5090 Worker

- Root: configured worker root, 23,716,787,998 bytes; free 836,602,642,432 bytes.
- Completed/imported: separation 10, ASR 100, alignment 51, embedding 100, quality 100, prosody 100.
- Idempotency: 461개 successful result package를 각각 재수입했고 canonical count가 증가하지 않았다.
- Failure: X-vector config 선택 오류 1건은 `MODEL_HASH_MISMATCH`로 fail-closed; 수정 후 replacement 성공.
- Legacy job 1건은 원래 `waiting_for_lease` 상태로 보존했다.
- Model store 6,754,049,432 bytes는 revision/hash가 기록된 재다운로드 가능 asset이며 삭제하지 않았다.
- Korean Wikipedia 처리와 lexical/semantic duplicate audit를 수행했다. 최종 clean bundle은
  78,112 documents와 129,341,916 tokens이며, 전체-row 13항목 독립 검사를 통과했다.
- Semantic audit는 `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`을
  사용했고 report SHA-256은 `87c6ae8ce6f63b728017ac408df7ab544f29829a5fe58543c1b7ea8727a0ac50`다.

Pinned audio model은 htdemucs, Whisper large-v3-turbo, Korean MFA 3.0.0, blocked MMS Korean aligner와
SpeechBrain X-vector다. MFA는 word/phone timing을 내는 `ATTRIBUTION_REQUIRED` default이고,
MMS output은 `BLOCKED_NONCOMMERCIAL`, X-vector output은 `NOT CALIBRATED`로 유지했다.
V0.1.0 process, repository와 system package는 변경하지 않았다.
