# User Actions Required

## Target Speech — USER_INPUT_REQUIRED

1. 사용하는 Miku/SVS engine의 output 학습·가공 허용 범위를 약관 원문 또는 계약 evidence로 확인한다.
2. `$MIKU_DATA_ROOT/exports/render-bundles/miku-speech-render-d0.2.0-alpha1.jsonl`의
   `utterance_id`, text, preset과 `expected_filename`을 그대로 사용해 speech-like audio를 render한다.
3. Bundle의 expected sample rate는 48,000 Hz다. 이는 intake 후보 설정이며 실제 audio metadata가 authoritative다.
4. 결과를 `$MIKU_DATA_ROOT/intake/target-speech`에 두고 README 형식의
   `intake-manifest.jsonl`에 engine/version/settings, rights evidence와 file SHA-256을 기록한다.
5. 제출 전 `sha256sum <audio-file>`로 각 checksum을 계산하고 bundle digest
   `9839ffe39a962a0221b60c96cfce6852bbcbeb45f1c60621c2d5d0f7cdaab539`와 함께 보존한다.

Bundle은 20,000행, exact unique 20,000, 예상 66.234283시간이다. 그러나 pinned E5 cosine
0.98/0.99 semantic effective unique는 1,536/7,715개뿐이다. 같은 본문에 시간·frame prefix만
바꾼 최대 104행 군집을 확인했으므로 20,000개 전체 render를 권장하지 않는다. 실제 render는
0시간, human review 0행, accepted 0행이며, 먼저 더 다양한 script 본문으로 bundle을 교체해야 한다.

## Other Intake

- Singing, licensed Korean STT, persona source representation과 agentic execution task는 각각
  `$MIKU_DATA_ROOT/intake/{singing-aux,korean-stt,persona-sources,agentic-sources}` README에 따라 제출한다.
- Rights evidence가 없으면 technical processing만 quarantine에서 수행한다.
- Target transcript/alignment, speaker consistency, quality tier와 Gold persona는 human review가 필요하다.
- Intake 후 `miku-data review serve`로 항목별 evidence-backed 판정을 완료하고, 별도
  `promote-sample` 단계에서 training 승격한다.

현재 target speech effective hours, human-reviewed persona와 human-adjudicated duplex는 0이다.
Execution-backed agentic은 local engineering receipt 1건을 accepted로 검증했으며 1,999건이 더 필요하다.
Duplex는 synthetic timestamp-backed raw 2,000건을 accepted로 검증했지만 primary semantic
effective unique는 582개다. Effective audio/timestamp-backed 1,418개와 사람 판정 1,000개가 더 필요하다.
