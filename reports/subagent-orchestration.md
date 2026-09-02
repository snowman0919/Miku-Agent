# Subagent Orchestration Report

## Canonical Foundry Pilot

- Codex parent: requirement, integration, code mutation, tests, commits와 release decision.
- Codex read-only subordinates: architecture/implementer design 1, test/security design 1; 둘 다 completed.
- Command Code: credential available, runtime executable missing; `MODEL_UNAVAILABLE`, eligible completed jobs 0.
- OpenCode: CLI invocation reached a missing/default model and paid model balance failure. Direct API attempts produced `AUTH_INVALID`, timeout/provider error 또는 schema-invalid partial output. Accepted review jobs 0.

Provider ratio는 `0:0`이라 정의하지 않는다. 2:1을 맞추기 위한 의미 없는 호출을 만들지 않았고, independent design 결과는 parent가 실제 code/test evidence로 adjudicate했다.

## RTX 5090 Worker Security Review

2026-09-03 worker branch window:

```text
jobs by provider:
  Command Code: 0
  OpenCode: 3
actual ratio: 0:3
target eligible-work ratio: 2:1
ratio deviation: Command Code runtime unavailable; availability override
reported token usage: unavailable
reported monetary usage: unavailable
result commits accepted: 0 (reviewers were read-only)
result commits rejected: 0
```

OpenCode의 job ownership, cache authenticity/materialization, input TOCTOU, model binding, false completion과 metrics 지적을 parent가 구현했고, 재검토에서 cache copy race와 forged stale completion을 추가 수정했다.

## Accepted Findings

- Filesystem/SQLite cross-resource transaction은 durable intent와 reconciliation이 필요하다.
- Rights/quality/review/training state는 독립 gate여야 한다.
- Split leakage는 transitive lineage와 frozen eval을 검사해야 한다.
- Canonical identity는 integer unit의 sorted JSONL이고 Parquet compression과 분리해야 한다.
- Git safety는 SQLite/Parquet suffix와 magic bytes를 차단해야 한다.
- Worker cache와 stale recovery는 원본 fingerprint, manifest와 output hash를 재검증해야 한다.

Credential은 repository 밖 `.env`에서 wrapper가 필요한 key 하나만 child process에 전달했고 captured stdout/stderr를 저장 또는 표시하기 전에 redaction했다. Raw provider transcript, credential, model cache와 session state는 Git에 넣지 않았다.
