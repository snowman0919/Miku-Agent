# ADR-0013: RTX 3080 Canonical Data Node and Manifest-Bound Remote Workers

## Status
accepted

## Date
2026-09-03

## Context

RTX 5090은 고비용 처리에 유용하지만 V0.1.0의 CONDITIONAL 결과상 production VoiceChat 해법이 아니며, 원격 worker가 canonical registry를 직접 수정하면 권한과 재현성이 분산된다.

## Decision

RTX 3080 노드를 source code, object store, SQLite registry와 release evidence의 canonical owner로 고정한다. RTX 5090은 job ID, input digest, code commit, worker/model/environment revision에 결속된 explicit grant가 있을 때만 disposable worker로 사용한다. 원격 결과는 output hash manifest로 돌아오며 3080이 bytes를 재검증한 뒤 local transaction으로만 등록한다.

## Alternatives Considered

- GPU 여유량만 보고 자동 실행: 외부 side effect 권한을 증명하지 못한다.
- 공유 SQLite를 원격 mount: corruption, latency와 writer ownership 위험이 있다.
- 5090을 canonical node로 전환: 현재 Git/data control node 경계와 충돌한다.

## Consequences

5090이 없어도 local pipeline은 계속된다. Remote cache는 disposable이고 canonical DB DSN을 job package에 넣지 않는다.

## Security Impact

Grant가 없거나 source binding/hash가 다르면 runner를 호출하지 않는다. 다른 GPU process를 종료하거나 V0.1 environment를 변경하지 않는다.

## Data Impact

모든 remote output은 input과 runtime provenance, hash receipt를 갖는다. Canonical bytes와 metadata는 3080에서만 승격된다.

## Validation

Missing/stale/wrong-job grant, output hash mismatch와 canonical DB 접근 부재를 테스트한다.

## Supersedes
None

## Superseded By
None
