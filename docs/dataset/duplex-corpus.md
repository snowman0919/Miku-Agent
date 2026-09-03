# Duplex Corpus

Audio contract가 확정되기 전에도 millisecond event timeline을 구축한다. Normal, backchannel, hesitation, correction, interruption, cancellation, simultaneous speech, silence, tool waiting/completion과 reconnect를 stratify한다.

각 timeline은 language, scenario, relationship mode, latency target, expected/forbidden behavior와 provenance를 가진다. V0.1.0에서 full-duplex latency가 검증되지 않았으므로 현재 skeleton을 passing realtime evidence로 간주하지 않는다.

Synthetic timestamp-backed row는 ordered `time_ms`/`end_ms`, duration·overlap·silence 합계,
scenario별 필수 event, generator hash와 template family가 일치해야 한다. 이 층은 interaction policy
학습에는 사용할 수 있지만 audio-backed 성능 또는 human adjudication으로 표시하지 않는다.
