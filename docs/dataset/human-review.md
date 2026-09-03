# Human Review

`miku-data review serve`는 `127.0.0.1` 전용 queue와 object playback route를 제공한다. Review mutation은 SQLite writer API만 사용하며 Parquet를 수정하지 않는다. 요청은 expected revision을 포함하고 stale write는 409 conflict와 audit event를 남긴다.

Review는 reviewer, timestamp, 이전·새 결정과 이유를 append-only로 보존한다. 현재 localhost 화면은 API 안내만 제공한다. Waveform, segment boundary/transcript editor, ASR/alignment 비교와 multi-reviewer adjudication을 갖춘 full application은 구현되지 않았으며 release blocker다.
