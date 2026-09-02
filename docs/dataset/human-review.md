# Human Review

`miku-data review serve`는 `127.0.0.1` 전용 queue와 object playback route를 제공한다. Review mutation은 SQLite writer API만 사용하며 Parquet를 수정하지 않는다. 요청은 expected revision을 포함하고 stale write는 409 conflict와 audit event를 남긴다.

Review는 reviewer, timestamp, 이전·새 결정과 이유를 append-only로 보존한다. Pilot UI는 audio queue, metadata와 transcript를 제공한다. Waveform, segment boundary editor와 multi-reviewer adjudication은 user-action queue에 남은 확장 항목이다.
