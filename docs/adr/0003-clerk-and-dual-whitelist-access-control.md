# ADR-0003: Clerk and Dual Whitelist Access Control

## Status
accepted

## Date
2026-09-02

## Context
가입 제한과 기존 계정의 즉시 runtime 차단은 서로 다른 lifecycle이다.

## Decision
Clerk exact-email Allowlist를 signup gate로, backend access grant를 runtime gate로 사용한다. Internal UUID가 primary key이고 모든 요청은 token, active grant, ownership을 deny-by-default로 검증한다.

## Alternatives Considered
Clerk metadata-only authorization, email primary key, domain wildcard, backend-only signup을 배제했다.

## Consequences
두 상태를 동기화해야 하지만 suspension/revocation을 application이 통제한다.

## Security Impact
WebSocket을 주기적·중요 action 시 재검사하고 client에 secret을 두지 않는다.

## Data Impact
Clerk metadata에 장기 memory를 저장하지 않는다.

## Validation
Auth schema conditional, invalid revoke example, security tests, trace D-003으로 검증한다.

## Supersedes
None

## Superseded By
None

