# ADR-0008: Modular VoiceChat Training Boundaries

## Status
accepted

## Date
2026-09-02

## Context
Integrated VoiceChat의 한 능력 개선이 다른 능력을 손상시키는 원인을 분리해야 한다.

## Decision
NVIDIA Nemotron VoiceChat 11B 계열을 DuplexSTT, LLM, DuplexEARTTS로 독립 평가한다. Codec은 freeze하고 LoRA/adapter pilot 전에는 full tuning을 허용하지 않는다. A/B/C/D 순서 branch를 비교한다.

## Alternatives Considered
즉시 joint/full tuning, codec 재학습, 하나의 aggregate metric을 배제했다.

## Consequences
실험 수는 늘지만 regression 원인과 promotion evidence가 명확하다.

## Security Impact
Checkpoint access와 hash, 실행 provenance를 기록한다.

## Data Impact
STT/persona/agentic/TTS dataset과 evaluation split을 독립 versioning한다.

## Validation
Model schema codec invariant, component gates, trace D-008로 검증한다.

## Supersedes
None

## Superseded By
None

