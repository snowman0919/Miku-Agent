# Risk Register

척도는 likelihood/impact/detectability 각각 Low/Medium/High이며 detectability High는 쉽게 발견됨을 뜻한다.

| Risk | Likelihood | Impact | Detectability | Mitigation | Owner | Decision deadline | Target version |
|---|---|---|---|---|---|---|---|
| VoiceChat 11B의 RTX 5090 32GB 적재 가능성 | Medium | High | High | checkpoint별 VRAM profile, quantization 없이 baseline부터 측정 | Voice runtime | V0.1.0 exit | 0.1.0 |
| GeForce kernel/runtime 호환성 | Medium | High | High | driver/CUDA/container inventory와 minimal inference matrix | Platform | V0.1.0 exit | 0.1.0 |
| Full-duplex latency | High | High | Medium | stage timing, TTFA/interruption p95, bounded buffering | Voice runtime | V0.6.x exit | 0.1.0-0.6.x |
| 한국어 adaptation 중 영어·agentic 손실 | High | High | High | 독립 holdout, non-inferiority regression gate, adapter rollback | Model | V0.3.x exit | 0.3.x |
| 미쿠 persona overfitting | Medium | High | Medium | hard/vector/pairwise 3계층 평가, utility holdout | Persona | V0.4.x exit | 0.4.x |
| 노래 데이터 speech contamination | High | High | Medium | corpus 분리, speech-likeness, source-level audit | Data | V0.2.0 exit | 0.2.0 |
| 음성 자료 권리 상태 | High | High | Low | provenance/rights quarantine, accepted invariant, legal review | Data owner | source acceptance 전 | 0.2.0 |
| Clerk production Allowlist 비용 | Medium | Medium | High | plan 확인, 예상 사용자 수 비용표, provider는 유지 | Auth | V0.7.x entry | 0.7.x |
| Flutter Clerk integration 경로 | Medium | Medium | High | community SDK와 native wrapper security/maintenance spike | Mobile | V0.8.1 | 0.8.1 |
| Flutter-Unity integration memory overhead | Medium | High | High | 세 경로 prototype의 RAM/frame/startup 비교 | Mobile | V0.8.1 | 0.8.1 |
| WebSocket audio 품질/reconnect | Medium | High | Medium | PCM/Opus loss/jitter/resume benchmark | Protocol | V0.1.0/V0.6.x | 0.6.x |
| MongoDB/Redis/vector/graph 복잡성 | High | Medium | High | canonical/projection 역할 분리, 최소 topology benchmark | Memory | V0.7.x design | 0.7.x |
| 자동 추론 memory 오판 | High | High | Medium | evidence, candidate lifecycle, precision >=0.95, user correction | Memory | V0.7.x exit | 0.7.x |
| Docker secret exfiltration | Medium | Critical | Low | broker/proxy, scoped TTL, egress audit, hostile repo tests | Security | V0.7.x entry | 0.7.x |
| Codex와 voice workload 자원 충돌 | High | High | High | reserved VRAM/RAM/disk, watchdog, GPU admission | Platform | V0.7.x exit | 0.7.x |

## V0.1.0 measured updates

| Risk ID | Before likelihood | After likelihood | Evidence | Remaining uncertainty | Next mitigation | Owner | Target version |
|---|---|---|---|---|---|---|---|
| `voicechat_11b_rtx5090_feasibility` | Medium | High | R0 FP32 general RTF 49.74; official function sample CUDA OOM; R3 BF16 RTF 2.39 | upstream-supported low-memory path | validate official optimized path on 80 GB+ GPU | Voice runtime | 0.1.1 |
| `geforce_kernel_runtime_compatibility` | Medium | Low | RTX 5090 sm_120 passed BF16/FP16 matmul, SDPA, Triton, Mamba2 and causal-conv1d | container-only fused kernels were not run | repeat kernel matrix inside immutable NVIDIA container | Platform | 0.1.1 |
| `full_duplex_latency` | High | High | no interactive server; best offline generation RTF 2.39 | TTFA and interruption remain unmeasured | loopback benchmark on supported container host | Voice runtime | 0.1.1-0.6.x |
| `voice_and_codex_resource_contention` | High | High | R0 used 32,137/32,607 MiB; R3 function peak used 25,158 MiB | co-resident model behavior untested | separate service/GPU or enforce admission and reserved memory | Platform | 0.7.x |
| `server_disk_capacity` | Medium | Low | about 869 GiB remained after the 44.4 GB checkpoint and environment | dataset growth not yet sized | reserve 20% and size V0.2.0 sources before download | Platform/Data | 0.2.0 |
| `interactive_container_access` | Medium | High | pinned docs require 80 GB, Docker and NVIDIA Container Toolkit; host has 32 GB and neither runtime | availability of a supported 80 GB+ host and immutable image digest | provision supported host and bind image digest | Platform | 0.1.1 |
