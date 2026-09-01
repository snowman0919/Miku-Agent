# Realtime Protocol

## Transport lock

- `/ws/audio`: Binary WebSocket audio frame
- `/ws/events`: JSON WebSocket agent event
- normal external API: HTTPS
- internal service RPC: gRPC
- WebRTC: V1 제외

두 WebSocket은 독립 연결이며 동일 authenticated session ID와 trace context로 상관관계를 맺는다.

## Audio frame

고정 endian의 versioned header는 protocol version, stream ID, sequence number, presentation timestamp, codec, sample rate, channel count, flags, payload length를 가진다. Parser는 length와 enum을 payload 처리 전에 검증한다.

## Session semantics

Heartbeat timeout은 half-open connection을 종료한다. Client는 last acknowledged sequence와 short-lived, session-bound resume token으로 만료 전 resume을 요청한다. Server는 replay window 밖 sequence와 duplicate frame을 거부한다. Session expiry 후에는 새 인증으로 시작한다.

Interruption command는 current output stream을 식별하고 server synthesis·queue를 중단한다. Output cancellation은 마지막 허용 sequence를 반환해 client buffer를 폐기한다. Slow consumer에는 bounded queue, progress coalescing, explicit backpressure status를 사용하며 audio를 무한 buffer하지 않는다. Jitter buffer는 presentation timestamp 기준으로 제한된 reorder를 허용하고 late/drop 통계를 남긴다.

## Codec benchmark

V0.1.0에서 PCM16 reference와 low-delay Opus를 packet duration 후보별로 비교한다. End-to-end TTFA, interruption, packet loss recovery, CPU, bandwidth, Korean intelligibility, reconnect continuity를 동일 trace로 측정하기 전에는 codec과 packet duration을 확정하지 않는다.

