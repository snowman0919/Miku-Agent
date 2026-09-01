# ADR-0004: User and Character Memory Namespace

## Status
accepted

## Date
2026-09-02

## Context
개인 기억과 캐릭터 관계의 경계를 보존하면서 자동 추론을 통제해야 한다.

## Decision
Memory namespace는 user ID와 character ID의 AND 관계다. Record와 commit을 versioning하고 inferred memory는 evidence lifecycle, conflict preservation, user control을 따른다.

## Alternatives Considered
User-global memory, character-global memory, silent overwrite, Git repository storage를 배제했다.

## Consequences
Query와 projection이 복잡해지지만 cross-user/character leak를 구조적으로 줄인다.

## Security Impact
모든 canonical·vector·graph·local query에 composite namespace filter가 필요하다.

## Data Impact
Correction은 supersede하고 deletion은 projection, snapshot, key lifecycle까지 전파한다.

## Validation
Memory schema conditional, invalid evidence/character examples, trace D-004로 검증한다.

## Supersedes
None

## Superseded By
None

