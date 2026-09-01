# ADR-0001: Miku-specific Character Strategy

## Status
accepted

## Date
2026-09-02

## Context
V1.0의 캐릭터 정체성을 유지하면서 미래 protocol 확장을 허용해야 한다.

## Decision
초기 `character_id`는 `miku` 하나이며 캐릭터별 dataset, persona/voice adaptation, 전용 배포 모델 전략을 사용한다. Schema는 character/profile/model/asset/animation/memory version field로 미래 다중 캐릭터를 수용한다.

## Alternatives Considered
Shared multi-character model과 zero-shot voice cloning은 V1.0 주 경로에서 제외하고 후속 실험으로 둔다.

## Consequences
미쿠 fidelity에 집중할 수 있으나 다른 캐릭터 추가에는 새 data·evaluation·namespace가 필요하다.

## Security Impact
Character ID를 authorization과 memory query에 항상 포함해야 한다.

## Data Impact
Dataset provenance와 모든 sample은 character ID를 가진다.

## Validation
Product lock, character schema, persona gates, trace D-001로 검증한다.

## Supersedes
None

## Superseded By
None

