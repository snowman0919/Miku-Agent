# Human Review

`miku-data review serve`는 `127.0.0.1` 전용 application, token-protected API와 byte-range object playback route를 제공한다. Review mutation은 SQLite writer API만 사용하며 Parquet를 수정하지 않는다. 요청은 expected revision을 포함하고 stale write는 409 conflict와 audit event를 남긴다.

화면은 waveform/zoom/playback/loop/speed, segment boundary와 raw/spoken/normalized transcript 편집,
ASR/alignment/speaker/quality evidence, rights/provenance, persona dimension/hard violation,
revision history와 keyboard decision을 제공한다. 편집 전후 값과 interaction evidence는 review와 같은
transaction에서 append-only로 보존한다.

Gold accept는 human actor와 한 항목씩의 완주 청취 또는 읽기 확인이 필요하다. Entity hash로 선택한
10% bucket은 서로 다른 두 reviewer를 요구하며 disagreement 뒤에는 명시적 adjudication이 있어야
export할 수 있다. Review accept 자체는 training status를 바꾸지 않는다. `promote-sample`이 source
rights의 explicit training scope, 최신 accepted review와 corpus별 quality invariant를 다시 검사한다.
