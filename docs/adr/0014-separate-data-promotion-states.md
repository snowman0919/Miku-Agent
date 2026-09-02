# ADR-0014: Separate Rights, Quality, Review and Training States

## Status
accepted

## Date
2026-09-03

## Context

하나의 `status`는 기술 품질이 좋지만 권리가 미확정인 source, 검토는 끝났지만 split이 없는 sample 같은 상태를 구분하지 못한다. 이는 `unknown` source의 우발적 training 승격 위험을 만든다.

## Decision

`intake_status`, `rights_status`, `quality_status`, `review_status`, `training_status`와 `quality_tier`를 독립 관리한다. `owned|licensed|permitted`는 evidence와 승인 actor가 있어야 하며 agent가 `unknown|restricted`를 스스로 승격하지 못한다. Training promotion은 current rights evidence, quality, review, object integrity, source-group split과 holdout gate를 같은 transaction에서 다시 검사한다. Human review는 append-only revision과 optimistic concurrency를 사용한다.

## Alternatives Considered

- 단일 enum: 상태 조합과 gate 실패 이유를 손실한다.
- 품질 점수 기반 자동 승인: 권리와 human review를 숫자로 상쇄한다.
- 기존 review overwrite: adjudication과 conflict evidence를 잃는다.

## Consequences

기술적으로 좋은 sample도 권리 미확정이면 quarantine이다. Frozen eval group은 training accepted가 아니다. Gold는 human review 없이 부여하지 않는다.

## Security Impact

권리 승격과 review 변경은 actor, 이전·새 결정, 이유를 audit event에 남긴다. Export는 cached status가 아니라 current rights를 fail-closed로 재검사한다.

## Data Impact

Raw/accepted/effective speech, singing auxiliary, quarantine, rejected duration을 따로 보고한다. Singing은 speech effective hours에 포함하지 않는다.

## Validation

권리 self-promotion, expiry/revocation, review conflict, holdout leakage와 effective-hours test로 검증한다.

## Supersedes
None

## Superseded By
None
