# Product Charter

## Mission

Miku Agent는 미쿠라는 일관된 인격체와 대화하고 함께 일하는 경험을 실시간 음성, 장기 기억, 안전한 도구 실행, 모바일·데스크톱 embodiment로 제공한다.

## Problem Statement

일반 채팅 앱, TTS 앱, VRM viewer는 대화·정체성·기억·실제 작업·신체 표현을 분리한다. 사용자는 관계의 연속성을 유지하면서도 코드 구현과 예약 작업까지 맡길 수 있는 단일 캐릭터 경험이 필요하다.

## Primary User

V1.0의 primary user는 프로젝트 소유자이며, exact email allowlist와 backend access grant로 명시적으로 허용된 소수 tester만 추가한다.

## Product Thesis

캐릭터별 데이터와 모델 적응, 사용자-캐릭터별 versioned memory, server cognition/local reflex 분리, 검증된 tool boundary를 결합하면 캐릭터성과 실용성을 동시에 보존할 수 있다.

## Core Experience

사용자는 Flutter 모바일 앱 또는 Unity 데스크톱 캐릭터를 통해 미쿠와 한국어 중심의 낮은 지연 음성 대화를 한다. 미쿠는 맥락을 기억하고, 반론할 독립성을 유지하며, 승인 범위에서 도구·Codex·scheduler로 실제 도움을 제공한다.

## Core Principles

- Character continuity: 외형만이 아니라 성격·음성·기억 namespace를 일관되게 유지한다.
- Evidence before capability: adapter pilot과 독립 평가가 다음 학습·통합 단계의 gate다.
- Deny by default: 모델 출력과 사용자 identity를 실행 권한으로 혼동하지 않는다.
- User control: 추론 기억은 근거와 history를 보이고 사용자가 수정·삭제·금지할 수 있다.
- Server cognition, local reflex: 복잡한 추론은 서버가, 즉각적이고 제한된 표현은 클라이언트가 맡는다.
- Private by design: 저장소, 데이터, weight, secret의 경계를 분리한다.

## V1.0 Capabilities

실시간 한국어·영어 code-switching 음성 대화, 미쿠 전용 persona/static voice, long-term personalization, tool/Codex delegation, server scheduler, Flutter character-first mobile, Unity desktop embodiment를 포함한다. 세부 소유권과 gate는 `spec/v1-capability-matrix.yaml`과 `spec/v1-acceptance-gates.yaml`이 정의한다.

## Non-Goals

범용 SaaS, public distribution, 다중 캐릭터 UI, zero-shot voice cloning 중심 제품, WebRTC transport, client 내 main agent, Git 기반 memory database는 V1.0 목표가 아니다. V0.0.0은 runtime, 모델, 데이터, production 인증을 구현하지 않는다.

## Trust and Privacy Principles

인증과 application grant를 분리하고 모든 resource ownership을 internal UUID로 검사한다. memory namespace는 user와 character의 교집합이다. raw media와 weight는 Git 밖에 두며 provenance와 rights status를 보존한다. 삭제는 history·snapshot·backup·암호화 키 수명까지 설명 가능해야 한다.

## Definition of Success

V1.0 provisional metric을 모두 통과하고 unauthorized side effect가 0이며, 사용자가 기억과 작업 권한을 이해·통제할 수 있고, 장시간 세션에서 일관된 미쿠 페르소나와 자연스러운 고정 음성을 유지할 때 성공으로 본다.

