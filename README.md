# Miku Agent

Miku Agent는 실시간 한국어 음성 대화, 미쿠형 페르소나와 고정 음성, 장기 기억, 도구 사용, Codex 구현 위임, scheduler, Flutter 모바일 UI, Unity 데스크톱 캐릭터를 하나의 개인용 캐릭터 에이전트로 통합하는 프로젝트다.

## 현재 상태

- 버전: `0.1.0`
- 단계: RTX 5090 Reference Feasibility
- 결과: `CONDITIONAL`
- 실행 환경: Nix flake 기반 server reference environment
- 초기 캐릭터: `miku`

V0.1.0은 NVIDIA VoiceChat 11B의 RTX 5090 재현성과 서비스 가능성을 측정했다. 공식 FP32 경로는 일반 offline inference는 성공했지만 function-calling에서 OOM이 발생했고 실시간 기준을 통과하지 못했다. Experimental BF16 경로는 일반/function channel이 동작했지만 RTF 2.39이며, 공식 interactive container는 80 GB VRAM 전제 때문에 이 서버에서 검증하지 못했다. 상세 근거는 `reports/v0.1.0-reference-feasibility.md`에 있다.

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
make audit-remote
make audit-release TAG=v0.1.0
```

## Source of truth

충돌 시 다음 순서를 적용한다.

1. `spec/product-lock.yaml`
2. accepted ADR
3. `docs/product-charter.md`
4. JSON Schema
5. `docs/roadmap.md`
6. component README

## V0.2.0 진입 조건

V0.1.0 release evidence와 annotated tag를 검증한 뒤 Dataset Foundry의 데이터·권리·품질 관리 작업을 시작할 수 있다. 모델 training은 별도 gate 전까지 시작하지 않으며, RTX 5090 production deployment가 해결됐다고 간주하지 않는다.
