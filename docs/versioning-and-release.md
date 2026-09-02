# Versioning and Release

## Version dimensions

Semantic version을 사용하되 제품 계약과 release evidence format을 분리한다. V0.0.1의 product version은 `0.0.1`, 고정된 product contract는 `0.0.0`, release evidence format은 `2`다. 이번 patch는 제품 기능이나 accepted V0.0.0 architecture를 변경하지 않는다.

## Release identity model

- Source identity: `release_identity.definition_commit`
- Release identity: annotated Git tag
- Release evidence: `release-manifest.yaml`과 versioned validation report
- Current remote policy: `make audit-remote`

Definition commit(Commit A)은 docs, ADR, schema, validator와 tests를 포함한 검증된 source다. Release commit(Commit B)은 Commit A의 직계 자식이며 최종 manifest, project state, changelog와 validation report를 포함한다. Annotated `v0.0.1` tag는 Commit B를 식별한다.

Tag target commit을 같은 commit의 tracked manifest 내부에 기록하지 않는다. `repository_commit`, `release_commit`, `tag_target_commit`, `self_commit`, `head_commit` field는 금지한다. Manifest Format 2는 Commit B 자체가 아니라 Commit A를 가리키므로 content-addressed Git에서 자기참조를 만들지 않는다.

## Document binding

Manifest document hash는 working tree가 아니라 definition commit의 Git object bytes에 대한 SHA-256이다. 검증은 개념적으로 `git show <definition_commit>:<path>`를 읽는다. 따라서 release evidence 이후 main 문서가 바뀌어도 과거 source binding은 재현 가능하다.

## Validation responsibilities

- `make validate`: network 없이 schema, examples, product/ADR/document, definition binding, release history, safety와 local Git invariant를 검사한다.
- `make audit-remote`: 현재 origin identity, PRIVATE/default branch, Wiki/Pages/Actions policy, remote refs를 검사한다.
- `make audit-release TAG=v0.0.1`: 특정 annotated tag, peeled commit, manifest binding과 local/remote tag 일치를 검사한다.

Remote policy 변화는 과거 offline validation 결과를 바꾸지 않는다. Release 준비 report에는 pre-tag remote audit만 기록하며 아직 존재하지 않는 tag를 PASS라고 쓰지 않는다.

## Immutability

Published tag와 commit을 amend, rebase, delete, move, force update하지 않는다. V0.0.0의 tag object `d1e97d732498f67b848264819e6316954a6ec52b`와 peeled commit `08ea6c6dc06e0a1a3a2a71fc8daa704b35e368d4`는 release history invariant다. 결함은 새 patch release로만 교정한다.

Accepted decision 변경은 새 ADR이 기존 ADR을 supersede하고 product lock, schema, docs, tests와 traceability를 같은 release에서 갱신해야 한다. V0.0.1은 ADR-0011만 추가하며 ADR-0001~0010을 supersede하지 않는다.
