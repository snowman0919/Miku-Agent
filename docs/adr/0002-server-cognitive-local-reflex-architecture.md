# ADR-0002: Server Cognitive and Local Reflex Architecture

## Status
accepted

## Date
2026-09-02

## Context
11B voice agent와 Codex는 mobile/desktop resource·security 경계에 맞지 않지만 UI reflex는 낮은 지연이 필요하다.

## Decision
Main cognition, memory integration, Codex, web research와 main voice는 server에서 실행한다. 2~4B급 local multimodal model은 UI intent, reflex, 제한 offline fallback, 간단 recognition과 장애 설명만 맡고 충돌 시 server가 우선한다.

## Alternatives Considered
Client-only main agent와 모든 interaction의 server round-trip을 배제했다.

## Consequences
Offline 기능은 제한되며 server availability가 핵심이지만 즉각적 표현은 보존한다.

## Security Impact
전체 local memory 접근은 explicit permission을 필요로 한다.

## Data Impact
Local snapshot은 canonical server memory와 revision으로 동기화한다.

## Validation
Product lock clients, system context, latency/personalization gates, trace D-002로 검증한다.

## Supersedes
None

## Superseded By
None

