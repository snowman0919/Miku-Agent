# Memory Architecture

## Ownership and types

Canonical namespace는 `user_id AND character_id`이며 다른 사용자나 캐릭터로 자동 공유하지 않는다. Type은 `explicit`, `episodic`, `project`, `inferred`, `personalization`이다. Record는 subject-predicate-value, confidence, importance, evidence, provenance, creator와 revision을 가진다.

## Inferred lifecycle

상태는 `candidate`, `active`, `stable`, `superseded`, `rejected`다. Inferred memory는 confidence, evidence, observation count, first/last seen을 필수로 가지며 evidence가 없으면 active/stable이 될 수 없다. 신뢰 우선순위는 사용자 확인·수정 > 사용자 명시 > 검증 가능한 tool 관찰 > 반복 추론 > 단일 추론 > 근거 없는 추측이다.

사용자 correction은 새 explicit record와 `supersede` commit을 만들고 이전 inferred record와 증거를 보존한다. 충돌은 조용히 overwrite하지 않고 시간 version을 모두 보존한다. compiler는 resolution을 제안할 뿐 evidence를 삭제하지 않으며 미해결 충돌은 unresolved로 유지한다.

## Version model

Memory commit은 parent, actor, timestamp, reason과 create/replace/supersede/reject/delete/restore operation을 가진다. Revision, diff, snapshot은 재현과 sync에 사용하며 실제 Git 저장소를 database로 사용하지 않는다. Decay는 자동 삭제가 아니라 retrieval priority 감소이며 낮은 빈도의 중요한 기억은 importance boost로 보호한다.

## User control and deletion

사용자는 UI와 대화에서 목록·근거·confidence·생성 이유·history를 확인하고 수정, 삭제, 잘못된 추론 표시, 금지 범위 설정, 전체 초기화를 할 수 있어야 한다. 삭제 요청은 active view와 retrieval index에서 즉시 제외한다. Audit/history 보존 요구와 충돌할 때 policy와 retention을 사용자에게 설명하고, 향후 encryption key 폐기에 의한 crypto-shredding과 snapshot compaction으로 backup·projection까지 삭제를 전파한다.

## Storage roles

- MongoDB: canonical records, commits, sessions, user-character documents.
- Redis: session, queue, lock, pub/sub, temporary cache.
- SQLite: mobile/desktop local snapshot, revision metadata, offline cache.
- Vector retrieval: semantic projection이며 source of truth가 아니다.
- Graph database: entity/relationship projection이며 source of truth가 아니다.
- LangChain: retrieval/orchestration layer이며 source of truth가 아니다.

Vector/graph vendor는 후속 실험으로 결정한다. Projection은 canonical revision과 namespace filter를 필수로 가져야 한다.
