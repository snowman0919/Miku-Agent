# Traceability Matrix

| Decision ID | Decision statement | Source document | ADR | Machine-readable spec | Schema | Evaluation | Implementation target | Status |
|---|---|---|---|---|---|---|---|---|
| D-001 | V1 initial character는 miku이며 character-specific fine-tuning을 사용 | persona-constitution.md | ADR-0001 | product-lock.character | character-profile | EVAL-PERSONA-HARD/PAIR | V0.4.x | accepted |
| D-002 | Main cognition은 server, 2~4B local model은 reflex/fallback | system-context.md | ADR-0002 | product-lock.clients | product-lock | EVAL-TTFA/EVAL-PERSONAL | V0.7.x/V0.8.x | accepted |
| D-003 | Clerk signup gate와 backend grant runtime gate를 함께 사용 | authentication-and-access-control.md | ADR-0003 | product-lock.auth | auth-access-grant | EVAL-SAFETY | V0.7.x | accepted |
| D-004 | Memory namespace는 user AND character이고 history를 versioning | memory-architecture.md | ADR-0004 | product-lock.memory | memory-record/memory-commit | EVAL-MEM-RECALL/INFER/PROV | V0.7.x | accepted |
| D-005 | Audio/events는 분리 WebSocket, API HTTPS, 내부 gRPC, WebRTC 제외 | realtime-protocol.md | ADR-0005 | product-lock.transport | agent-event | EVAL-TTFA/EVAL-INTERRUPT | V0.6.x | accepted |
| D-006 | Mobile은 Flutter, desktop은 Unity이며 protocol만 공유 | client-experience.md | ADR-0006 | product-lock.clients | reaction-command | EVAL-CHAR-CONSIST | V0.8.x/V0.9.x | accepted |
| D-007 | Codex는 제한된 Docker workspace와 독립 authorization을 사용 | codex-execution.md | ADR-0007 | product-lock.codex | agent-tool-call | EVAL-TOOL-COMPLETE/EVAL-SAFETY | V0.7.x | accepted |
| D-008 | VoiceChat 11B를 STT/LLM/TTS로 분리 평가하고 codec을 freeze | model-boundaries.md | ADR-0008 | product-lock.model | model-profile | EVAL-ASR-CLEAN/EVAL-TTS-CER | V0.1.0-0.6.x | accepted |
| D-009 | Repository는 private이며 data/weight/media/secret을 commit하지 않음 | data-governance.md | ADR-0009 | product-lock.repository | project-state | EVAL-SAFETY | V0.0.0 | accepted |
| D-010 | Animation은 procedural/FSM/BT/reaction hybrid이고 per-frame LLM bone 출력을 금지 | animation-and-embodiment.md | ADR-0010 | product-lock.animation | reaction-command | EVAL-CHAR-CONSIST | V0.9.x | accepted |
| D-011 | Scheduler는 server-side이며 external write는 explicit approval 필요 | scheduler-and-notifications.md | ADR-0007 | product-lock.scheduler | scheduler-task | EVAL-SAFETY | V0.7.x | accepted |
| D-012 | Dataset acceptance는 rights와 quality/alignment를 모두 요구 | data-governance.md | ADR-0009 | product-lock.data | dataset-source/dataset-sample | EVAL-ASR-CLEAN/EVAL-TTS-CER | V0.2.0 | accepted |
| D-013 | Release source는 definition commit, release identity는 annotated tag이며 offline validation과 remote audit을 분리 | versioning-and-release.md | ADR-0011 | release-history | release-manifest/release-history | offline validation + release audit | V0.0.1 | accepted |
| D-014 | Dataset object는 SHA-256 identity와 recoverable ingest intent를 사용하고 SQLite만 canonical mutable metadata를 보유 | dataset/architecture.md | ADR-0012 | dataset-foundry | dataset/object, dataset/transform | object integrity + recovery | V0.2.0 | accepted |
| D-015 | RTX 3080만 canonical data를 쓰며 RTX 5090은 manifest와 grant에 결속된 disposable worker | dataset/gpu-worker-topology.md | ADR-0013 | dataset-foundry.remote_worker | dataset/remote-job | remote lease + hash import | V0.2.0 | accepted |
| D-016 | Rights, quality, review, training 상태는 독립이며 모든 gate가 통과해야 training accepted | dataset/rights-promotion.md | ADR-0014 | dataset-quality-gates | dataset/rights-record, dataset/review | rights promotion + export gate | V0.2.0 | accepted |

Schema 표기의 짧은 이름은 `schemas/<name>.schema.json`, machine-readable 경로는 `spec/product-lock.yaml`을 뜻한다.
