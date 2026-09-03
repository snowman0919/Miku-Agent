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

Bundle은 20,000행, exact unique 20,000, 예상 66.234283시간이다. 실제 render는 0시간,
human review 0행, accepted 0행이다. Release minimum 30 effective hours를 만족하려면 reject와
중복을 감안해 최소 30시간보다 많이 render해야 하며, 이 bundle의 예상치는 충분하지만 보장값이 아니다.

## Other Intake

- Singing, licensed Korean STT, persona source representation과 agentic execution task는 각각
  `$MIKU_DATA_ROOT/intake/{singing-aux,korean-stt,persona-sources,agentic-sources}` README에 따라 제출한다.
- Rights evidence가 없으면 technical processing만 quarantine에서 수행한다.
- Target transcript/alignment, speaker consistency, quality tier와 Gold persona는 human review가 필요하다.

이 입력 전까지 target speech effective hours, human-reviewed persona, execution-backed agentic와
accepted duplex 핵심 수치는 0이다.
