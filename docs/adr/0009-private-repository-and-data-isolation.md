# ADR-0009: Private Repository and Data Isolation

## Status
accepted

## Date
2026-09-02

## Context
개인 연구 source와 권리·개인정보가 있는 data/model asset의 storage lifecycle이 다르다.

## Decision
Repository는 private, public distribution은 false다. Raw/processed data, media, VRM, model weight, secret을 Git에 넣지 않는다. Metadata schema와 가상 example만 추적한다.

## Alternatives Considered
Public repository, Git LFS에 raw asset 저장, private이면 권리 검토 생략을 배제했다.

## Consequences
별도 object/model storage가 필요하지만 source control leak 범위를 줄인다.

## Security Impact
Remote visibility API 확인, forbidden tracked-file/secret scan을 release gate로 둔다.

## Data Impact
Rights unknown/restricted는 accepted dataset이 될 수 없다.

## Validation
Project state/product lock schema, repository safety tests, trace D-009/D-012로 검증한다.

## Supersedes
None

## Superseded By
None

