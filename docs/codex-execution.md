# Codex Execution

## Roles and flow

사용자와 미쿠는 요구와 성공 조건을 구체화한다. 미쿠가 초안 goal을 만들고 Codex가 구현 전략·risk·검증 가능성을 검토한다. 필요한 제품 결정을 사용자와 마무리한 뒤 permission controller가 side effect 범위를 승인하고 격리 workspace가 실행된다. Codex는 검증 결과를 남기고 미쿠는 적용 내용과 한계를 보고한다.

## Container boundary

Codex는 서버의 Docker workspace에서 실행한다. Container 내부 root는 격리 namespace의 root일 뿐 host root 권한이 아니다. `--privileged`와 host Docker socket mount는 금지한다. 기본 lifetime은 30일이며 workspace volume은 유지하고 explicit kill과 자체 환경 구성을 지원한다.

Internet은 허용할 수 있으나 destination·volume·actor를 기록 가능한 egress control을 둔다. Git operation은 scoped credential 또는 broker로 수행한다. SSH key는 매번 목적을 설명한 사용자 동의와 제한된 TTL이 필요하다. 로컬 PC 접근도 매번 명시 승인한다.

Secret을 평문 환경 변수로 상시 주입하지 않고 broker/proxy가 최소 범위 작업을 대신한다. 모델·repository code는 credential을 직접 읽을 수 없어야 한다. Malicious dependency, prompt/tool injection, outbound exfiltration을 policy와 audit으로 탐지한다.

Voice runtime reserved VRAM/RAM, OS reserved disk, runaway process watchdog, Codex GPU admission control로 interactive voice workload를 보호한다. Failure report는 permission decision, command exit, partial side effect, validation evidence와 recovery action을 포함한다. V0.0.0에는 container, broker, integration 구현이 없다.

