# ADR-0005: Binary WebSocket Realtime Transport

## Status
accepted

## Date
2026-09-02

## Context
Audio와 agent event는 서로 다른 framing, backpressure, interruption 요구를 갖는다.

## Decision
Binary audio와 JSON event를 `/ws/audio`, `/ws/events`의 별도 WebSocket으로 전송한다. 외부 API는 HTTPS, 내부 RPC는 gRPC이며 V1에서 WebRTC를 제외한다.

## Alternatives Considered
단일 mixed WebSocket, HTTP polling, V1 WebRTC를 배제했다.

## Consequences
Connection coordination이 필요하지만 audio framing과 event evolution을 분리한다.

## Security Impact
각 연결 인증, session binding, replay/duplicate rejection, authorization recheck가 필요하다.

## Data Impact
Sequence, timestamp, resume metadata와 bounded retention이 추가된다.

## Validation
Product lock transport, event schema, latency/interruption gates, trace D-005로 검증한다.

## Supersedes
None

## Superseded By
None

