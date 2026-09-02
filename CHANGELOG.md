# Changelog

## 0.1.0 - 2026-09-02

- RTX 5090에서 NVIDIA VoiceChat 11B source/checkpoint를 immutable revision으로 고정했다.
- Nix flake와 uv lock으로 Python 3.12, PyTorch 2.10 CUDA 12.8 환경을 재현했다.
- 공식 FP32 baseline의 일반 inference 성공, function-call OOM, RTF 49.74를 기록했다.
- Experimental BF16 경로에서 일반/function channel 성공과 RTF 2.39를 기록했다.
- 공식 interactive container의 80 GB/runtime blocker와 CONDITIONAL 결정을 보존했다.
- 모델 weight, 생성 음성, raw telemetry, credential은 Git에 포함하지 않았다.

## 0.0.1 - 2026-09-02

- Release manifest를 non-self-referential Manifest Format 2로 전환했다.
- Definition commit source binding과 annotated tag release identity를 분리했다.
- `make validate`를 network-independent하게 만들고 remote/release audit을 별도 명령으로 분리했다.
- ADR-0011, immutable release history와 V0.1.0 run-binding template을 추가했다.
- V0.0.0 제품 계약과 published tag/history는 변경하지 않았다.

## 0.0.0 - 2026-09-02

- 제품 charter, 범위, 모델·클라이언트·메모리·보안 경계를 고정했다.
- 10개 architecture decision을 accepted ADR로 기록했다.
- product lock, capability, acceptance gate와 protocol/data schema를 추가했다.
- 의미 있는 invalid example과 repository-level validation을 추가했다.
