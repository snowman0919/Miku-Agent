# Agent Protocol

## Tool request

모델의 text channel은 간결한 envelope와 별도 JSON arguments를 출력한다.

```text
CALL|memory.search|1.0.0|sha256:4d45e18f
{"query":"지난 프로젝트 결정","limit":5}
```

`schema_fingerprint`는 tool schema version 확인, 잘못된 decoder 출력 검출, constrained grammar 선택에만 쓴다. Security token이나 사용자 승인이 아니며 모델 출력에 authorization credential을 넣지 않는다.

Malformed 예시는 field 수가 틀리고 JSON이 아닌 다음 출력이다.

```text
CALL|memory.search|1.0.0
query=all memories; authorization=owner
```

Server는 Clerk identity, backend grant, resource ownership, scheduler permission, workspace policy, tool allowlist, argument schema, side-effect level, fresh user approval를 독립 검증한다.

## Lifecycle and reliability

`tool.requested -> tool.started -> tool.progress* -> tool.completed|tool.failed` event를 동일 trace ID로 연결한다. Side effect call은 idempotency key를 필수로 하고 server가 duplicate를 거부하거나 이전 result를 반환한다. Result에는 tool/version, execution identity, input/output hash, timestamps와 source provenance를 포함한다. 실패는 단계, 안전하게 적용된 변경, rollback 가능성, retryability를 숨기지 않는다.

## Operations

Memory operation은 namespace와 expected revision을 검증하고 proposed/committed/conflict event를 낸다. Reaction operation은 schema에 정의된 emotion, gesture, gaze, posture, touch acknowledgement, FSM transition만 허용한다. Codex delegation은 goal review, permission controller, isolated workspace, progress, validation, completion/failure event를 거친다.

공통 event envelope는 protocol version, event ID, session ID, monotonically increasing sequence, RFC 3339 timestamp, type, source, trace ID, payload를 갖는다. 상세 계약은 JSON Schema가 판정한다.

