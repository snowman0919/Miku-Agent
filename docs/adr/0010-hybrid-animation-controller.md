# ADR-0010: Hybrid Animation Controller

## Status
accepted

## Date
2026-09-02

## Context
캐릭터 움직임은 frame-stable하면서 대화 의미와 감정을 반영해야 한다.

## Decision
Procedural physiology, FSM, behavior tree, high-level reaction tool의 계층형 controller를 사용한다. LLM은 임의 per-frame bone transform을 생성하지 않는다.

## Alternatives Considered
LLM direct bone generation과 clip-only animation을 배제했다.

## Consequences
Authoring된 state/gesture가 필요하지만 latency, stability, controllability가 향상된다.

## Security Impact
Reaction command allowlist와 touch region policy로 abusive/unbounded pose를 막는다.

## Data Impact
Voice cue와 reaction event에 timestamp, emotion, semantic emphasis가 필요하다.

## Validation
Reaction schema는 six high-level commands만 허용하고 character consistency gate와 trace D-010으로 검증한다.

## Supersedes
None

## Superseded By
None
