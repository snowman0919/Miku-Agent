# GPU Worker Model Selection

## 상태

현재 result는 `UNRESOLVED`다. 실제 host가 RTX 5090이 아니고 다른 GPU workload가
실행 중이어서 model download, cold/warm run, batch scaling과 quality comparison을
수행하지 않았다. Internet popularity나 V0.1.0 VoiceChat 결과만으로 default를
선택하지 않는다.

## RTX 5090에서 필요한 비교

| Task | Candidate family scope | Required evidence before selection |
|---|---|---|
| source separation | Demucs, MDX, UVR-compatible | known-mixture objective test, no-reference artifact review, license |
| ASR | 최소 두 독립 family | Korean, synthetic voice, Japanese, code switch, short/long, singing vocal |
| forced alignment | word/phoneme capable candidates | unaligned span and duration anomaly rate by language |
| speaker embedding | 최소 두 family | synthetic voice correlation, speech/singing and separation preservation |
| audio embedding | semantic/audio candidates | near-duplicate and source-family retrieval behavior |
| quality | component metrics and learned proxy | calibrated component behavior; scalar acceptance 금지 |
| critic | VoiceChat 11B 포함 복수 후보 | Korean/persona/agentic agreement, throughput, license and cost |

모든 candidate record는 immutable revision, weight/config SHA-256, weight/code license,
commercial/redistribution/output restriction, dtype, environment와 measured peak VRAM을
포함해야 한다. `main` 또는 `latest`만 기록한 profile은 runtime에서 거부한다.

