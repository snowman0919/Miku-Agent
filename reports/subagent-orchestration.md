# Subagent Orchestration Pilot

## Routing

- Codex parent: requirement, integration, code mutation, tests, commits와 release decision.
- Codex read-only subordinates: architecture/implementer design 1, test/security design 1; 둘 다 completed.
- Command Code: credential available, runtime executable missing; `MODEL_UNAVAILABLE`, eligible completed jobs 0.
- OpenCode: CLI invocation reached a missing/default model and paid model balance failure. Direct API attempts produced `AUTH_INVALID`, timeout/provider error 또는 schema-invalid partial output. Accepted review jobs 0.

Provider ratio는 `0:0`이라 정의하지 않는다. 2:1을 맞추기 위한 의미 없는 호출을 만들지 않았고, independent design 결과는 parent가 실제 code/test evidence로 adjudicate했다. Credential 값과 raw provider transcript는 저장하지 않았다.

## Accepted Findings

- Filesystem/SQLite cross-resource transaction은 durable intent와 reconciliation이 필요하다.
- Rights/quality/review/training state는 독립 gate여야 한다.
- Split leakage는 transitive lineage와 frozen eval을 검사해야 한다.
- Canonical identity는 integer unit의 sorted JSONL이고 Parquet compression과 분리해야 한다.
- Git safety는 SQLite/Parquet suffix와 magic bytes를 차단해야 한다.
