# Miku Agent

Miku Agent는 실시간 한국어 음성 대화, 미쿠형 페르소나와 고정 음성, 장기 기억, 도구 사용, Codex 구현 위임, scheduler, Flutter 모바일 UI, Unity 데스크톱 캐릭터를 하나의 개인용 캐릭터 에이전트로 통합하는 프로젝트다.

## 현재 상태

- 버전: `0.0.0`
- 단계: Product Definition Lock
- 실행 환경: local-only
- 초기 캐릭터: `miku`

V0.0.0은 애플리케이션·모델 구현 단계가 아니다. 제품 의미, 컴포넌트 경계, 보안 정책, 데이터 계약, 평가 기준을 문서와 기계 검증 가능한 schema로 잠그는 단계다. 서버 접속, 모델 다운로드·학습, 데이터 수집, Flutter/Unity scaffold, production 인증 구성은 수행하지 않는다.

## V1.0 목표

프로젝트 소유자와 명시적으로 허용된 소수 사용자가 모바일 또는 데스크톱에서 미쿠와 자연스럽게 음성으로 대화하고, 사용자-캐릭터별 기억과 도구·Codex·예약 작업을 안전하게 이용하는 개인 시스템을 제공한다.

## 저장소 정책

이 저장소는 비공개 개인 연구용이다. 공개 배포, GitHub Pages, 공개 release를 허용하지 않는다. 원시 데이터, 미디어, VRM asset, 모델 weight, secret은 Git에 넣지 않는다.

## 로컬 검증

Python 3.11 이상에서 개발 의존성을 설치한 뒤 실행한다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
make validate
```

## Source of truth

충돌 시 다음 순서를 적용한다.

1. `spec/product-lock.yaml`
2. accepted ADR
3. `docs/product-charter.md`
4. JSON Schema
5. `docs/roadmap.md`
6. component README

## V0.1.0 진입 조건

모든 V0.0.0 schema와 invariant가 검증되고, validation report가 생성되며, 비공개 원격 가시성이 확인되고, clean한 release commit에 `v0.0.0` annotated tag가 있어야 한다. 그 뒤에만 `docs/handoff/v0.1.0-server-readiness.md`에 따라 RTX 5090 reference feasibility를 시작한다.
