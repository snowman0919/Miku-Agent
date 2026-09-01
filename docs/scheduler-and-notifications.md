# Scheduler and Notifications

Scheduler는 V0.7.x부터 서버에서 실행되어 client가 종료되어도 작업을 수행한다. Permission level은 `notify-only`, `read-only`, `tool-use`, `workspace-write`, `external-write` 순이며 상위 단계가 하위 승인을 암묵적으로 포함하지 않는다.

Task는 owner, character, schedule, timezone, action, permission, delivery, memory policy, created/updated time와 선택적 expiry를 가진다. `external-write`는 구체 target·scope·approval freshness·revocation policy를 필수로 한다. 실행 시에도 owner grant, task status, permission과 target allowlist를 재검사해 생성 당시 승인만 신뢰하지 않는다.

결과 본문과 provenance는 서버에 저장한다. Push payload에는 `task_id`, title, short status, result revision만 포함하고 memory, transcript, secret, 전체 결과를 넣지 않는다. 앱은 인증된 HTTPS로 ownership을 재검사한 뒤 결과를 조회한다.

