# Subagent Orchestration Report

## Window

V0.2.0 RTX 5090 GPU Data Worker security review, 2026-09-03.

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

OpenCode는 독립 SECURITY_REVIEWER/CRITIC 역할로만 사용했다. 첫 review의 job ownership,
cache authenticity/materialization, input TOCTOU, model binding, false completion과 metrics
지적을 parent가 구현했다. 재검토에서 cache copy race와 forged stale completion을 찾아
추가 수정했다. Provider 비율을 맞추기 위한 의미 없는 작업은 만들지 않았다.

Credential은 repository 밖 `.env`에서 wrapper가 필요한 key 하나만 child process에
전달했고 captured stdout/stderr를 저장 또는 표시하기 전에 redaction했다. Raw provider
transcript, credential, model cache와 session state는 Git에 넣지 않았다.
