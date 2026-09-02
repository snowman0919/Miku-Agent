# ADR-0011: Non-Self-Referential Release Identity and Split Validation

## Status
accepted

## Date
2026-09-02

## Context

V0.0.0 manifest는 release commit SHA를 같은 commit에 포함되는 tracked manifest에 기록하려 했다. Git commit ID는 manifest를 포함한 tree에 의존하므로 manifest에 예상 SHA를 쓰는 순간 tree와 commit ID가 다시 바뀌는 자기참조 문제가 생긴다.

또한 offline content validation과 현재 GitHub Wiki, Pages, Actions, visibility audit가 같은 명령에 포함되어 과거 release의 재현 가능성이 미래 remote 상태와 network availability에 의존했다.

## Decision

다섯 책임을 분리한다.

- `definition_commit`: release evidence 생성 직전의 검증된 source binding이다.
- Release commit: manifest, project state, changelog, validation report를 추가하는 definition commit의 직계 자식이다.
- Annotated tag: release commit identity를 제공한다.
- Offline validation: repository content와 local Git object만 검증한다.
- Remote audit: 현재 GitHub policy와 local/remote ref 일치를 별도 명령으로 검증한다.

Manifest는 release commit 자신의 SHA를 저장하지 않는다. Document hash는 working tree가 아니라 definition commit의 Git object content에 bind한다.

## Alternatives Considered

- Manifest 안에 HEAD SHA 반복 기록: 매 기록이 commit SHA를 다시 바꾸므로 불가능하다.
- Tag를 이동해 manifest 값에 맞추기: published history immutability를 훼손하므로 거절한다.
- Git note만 사용: clone/fetch 정책에 따라 누락될 수 있고 schema-validated evidence를 대체하지 못한다.
- GitHub Release만 source of truth로 사용: provider와 network에 의존해 offline 재현성을 잃는다.
- External database release record: 개인 연구 단계에 불필요한 운영 의존성을 만들고 repository-contained evidence를 약화한다.

## Consequences

- Manifest는 자기 자신의 release commit SHA를 저장하지 않는다.
- Annotated tag가 release identity를 제공한다.
- Definition commit이 source identity를 제공한다.
- Offline validator는 network-independent하다.
- Current remote policy는 `make audit-remote`에서만 검증한다.
- Release commit은 definition commit의 직계 자식이어야 한다.

## Security Impact

Tag 이동과 force update를 허용하지 않으며 local/remote tag object와 peeled commit을 비교한다. Offline validation이 remote 성공 여부를 권한 증거로 오인하지 않는다.

## Data Impact

Document SHA-256은 definition commit의 Git blob bytes에 대해 계산한다. Working tree 변경은 역사적 binding을 바꾸지 않는다.

## Validation

Manifest v2 schema, self-reference invalid example, definition existence/ancestry tests, historical hash tests, offline-without-gh test, `audit-remote`, `audit-release`로 검증한다.

## Supersedes
None

## Superseded By
None

