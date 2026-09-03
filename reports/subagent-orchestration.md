# Subagent Orchestration Report

## Accepted Window 001

- Attempts 59, accepted 30, first-pass accepted 24.
- Command Code accepted 20: `poolside/laguna-s-2.1-free` 12, `meituan/LongCat-2.0:free` 8.
- OpenCode accepted 10: `opencode/nemotron-3-ultra-free` 10.
- Actual ratio 2.0, target ratio 2:1.
- Mean/p50/p95 latency: 47,740 / 25,464 / 147,024 ms.
- Failures excluded from ratio: `OUTPUT_SCHEMA_INVALID` 14, `PROVIDER_UNAVAILABLE` 14,
  `AGENT_RUNTIME_ERROR` 1.

Command Code generation을 OpenCode가 독립 비평했고 deterministic schema/hash 검사 후 parent가
200 seed와 10 critique를 직접 adjudicate했다. 194 seed를 speech render bundle 설계에 사용하고
문법·오탈자·부자연스러운 code switch 6개는 quarantine했다.

채택한 규칙은 raw/spoken/normalized 분리, 숫자·단위·약어 발음 명시, 관계/말높임 metadata,
종결·길이 분포, exact/family dedup, 문법/code-switch quarantine이다. Receipt와 provider output은
`$MIKU_DATA_ROOT/jobs/subagents/window-001`에 있고 Git에는 넣지 않았다.

Paid Command Code provider는 HTTP 429 quota로 실패했다. 공개 입력만 free fallback에 보냈고,
credential, private raw audio, 권리 미확인 원문과 repository secret은 보내지 않았다.
