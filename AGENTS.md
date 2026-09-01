# Agent Working Agreement

## Source of truth

1. `spec/product-lock.yaml`
2. accepted ADR
3. `docs/product-charter.md`
4. JSON Schema
5. `docs/roadmap.md`
6. component README

## Mandatory rules

- V0.0.0의 accepted 결정을 임의로 수정하지 않는다. 변경은 기존 ADR을 supersede하는 새 ADR로만 한다.
- 저장소를 public으로 전환하거나 공개 package, release, Pages를 만들지 않는다.
- raw data, media, VRM asset, model weight, checkpoint, secret을 commit하지 않는다.
- V0.1.0 이전에는 서버·GPU·Docker runtime·production Clerk를 사용하지 않는다.
- 사용자가 이미 고정한 결정을 다시 묻지 않는다.
- 미결정 사항을 사실처럼 확정하지 않고 `docs/open-questions.md`에서 관리한다.
- 테스트는 보호하는 요구 또는 failure mode와 decision value를 `tests/TEST_INTENT.md`에 기록한다.
- 통과 수나 coverage 자체를 위한 테스트, 빈 파일·getter·동일 상수의 중복 확인 테스트를 만들지 않는다.
- 실제 실행하지 않은 검증을 성공으로 보고하지 않는다.
- schema와 identifier는 en-US, 설명 문서는 ko-KR, 파일은 UTF-8/LF를 사용한다.
- 모든 외부 side effect는 단계 경계와 permission policy를 먼저 확인한다.

