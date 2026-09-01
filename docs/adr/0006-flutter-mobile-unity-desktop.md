# ADR-0006: Flutter Mobile and Unity Desktop

## Status
accepted

## Date
2026-09-02

## Context
앱 내부 character-first UX와 OS 공간의 상주 캐릭터는 서로 다른 rendering·interaction 요구를 가진다.

## Decision
Mobile framework는 Flutter, desktop은 Unity로 고정하고 UI code 대신 protocol과 character-runtime contract만 공유한다.

## Alternatives Considered
하나의 Unity UI codebase와 native mobile 전용 구현을 배제했다. 모바일 VRM surface 경로만 후속 비교한다.

## Consequences
두 UI를 유지하지만 각 플랫폼의 UX와 desktop embodiment를 최적화할 수 있다.

## Security Impact
두 client 모두 동일 auth/ownership contract를 구현해야 한다.

## Data Impact
Local snapshot과 asset metadata만 schema contract로 공유한다.

## Validation
Product lock clients, reaction schema, character gates, trace D-006으로 검증한다.

## Supersedes
None

## Superseded By
None

