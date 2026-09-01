# ADR-0007: Codex Docker Security Boundary

## Status
accepted

## Date
2026-09-02

## Context
Codex와 scheduler는 실제 side effect를 수행하므로 model output과 host 권한을 분리해야 한다.

## Decision
Codex는 기본 30일 persistent Docker workspace에서 container root로 실행할 수 있으나 privileged와 host Docker socket은 금지한다. Permission controller, secret broker, scoped credential, egress audit, resource reservation을 둔다. Scheduler permission은 notify-only부터 external-write까지 명시한다.

## Alternatives Considered
Host execution, privileged container, raw secret environment injection, model-authorized execution을 배제했다.

## Consequences
Broker와 policy plane 구현 비용이 있지만 host와 credential 위험을 제한한다.

## Security Impact
Local PC/SSH/external write는 fresh explicit approval을 요구한다.

## Data Impact
Workspace persistence, audit log, task result와 revision의 retention policy가 필요하다.

## Validation
Tool/scheduler schema invalid examples, threat model, safety gate, trace D-007/D-011로 검증한다.

## Supersedes
None

## Superseded By
None

