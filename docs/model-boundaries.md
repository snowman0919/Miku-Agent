# Model Boundaries

## Component map

- DuplexSTT: 한국어·영어 이해, code-switching, streaming partial/final transcript와 timing confidence를 담당한다.
- Nemotron LLM backbone: 한국어 언어 능력, 미쿠 persona, tool-use, memory retrieval 판단, Codex 위임을 담당한다.
- DuplexEARTTS: 미쿠형 고정 화자, 한국어, emotion preset, streaming prosody를 담당한다.
- Audio codec: V1에서 고정하며 별도 accepted ADR 없이 재학습하지 않는다.

최종 배포 단위의 가칭은 `Miku-Nemotron-VoiceChat-v1`이지만 checkpoint, adapter, evaluation report는 STT/LLM/TTS별 version을 독립 보존한다.

## Training policy

각 능력은 LoRA 또는 adapter pilot으로 데이터 방향을 먼저 검증한다. full-parameter LLM tuning은 pilot이 목표 개선, English/tool/persona regression gate, provenance·rights gate를 모두 통과하고 compute plan이 승인된 뒤에만 고려한다. STT, LLM, TTS를 독립 평가한 뒤 제한된 joint calibration을 허용한다.

비교 branch는 A `Korean -> Persona -> Agentic`, B `Korean -> Agentic -> Persona`, C `Korean -> Persona+Agentic joint`, D `Korean base + Persona adapter + Agentic adapter composition`이다. 한 단계가 기존 능력을 acceptance gate 아래로 낮추면 promotion하지 않는다.

## Voice and codec

V1 voice mode는 zero-shot cloning이 아닌 static speaker adaptation이다. singing corpus는 speaker identity, formant, spectral/synthetic texture, style representation에만 보조 사용하고 speech duration/alignment의 주 자료로 쓰지 않는다. Codec은 학습 관점에서 frozen이며 transport codec 선택은 V0.1.0 PCM16/low-delay Opus benchmark까지 열어 둔다.

## Execution boundary

NVIDIA Nemotron VoiceChat 11B 계열의 정확한 checkpoint access, RTX 5090 32GB 적재, kernel/runtime, VRAM·latency·30분 soak는 오직 V0.1.0에서 검증한다. V0.0.0에서는 download, inference, tuning을 수행하지 않는다.

