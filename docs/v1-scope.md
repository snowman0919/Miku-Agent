# V1.0 Scope

## 포함

- initial `character_id=miku`와 미래 확장 필드를 가진 단일 캐릭터 runtime
- 한국어 중심, 영어 유지와 code-switching을 포함한 full-duplex voice
- reference audio 없이 일관된 static speaker adaptation
- evidence·revision·conflict를 가진 user-and-character memory
- server-side tool, Codex workspace, scheduler와 push result notification
- Flutter 모바일 경험과 Unity desktop embodiment
- Clerk identity와 backend access grant의 이중 gate

## 제외

- 사용자에게 공개된 SaaS와 public repository/release
- V1.0 내 다중 캐릭터 제품 UI
- zero-shot voice cloning을 주 음성 경로로 사용
- client에서 11B main agent 또는 main voice generation 실행
- WebRTC, per-frame LLM bone control, raw data·weights의 Git 저장

## 버전 경계

V0.0.0은 정의 계약만, V0.1.0은 RTX 5090 reference feasibility만 수행한다. 이후 단계는 `docs/roadmap.md`의 entry/exit gate를 따른다.

