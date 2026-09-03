# Dataset Foundry

V0.2.0의 local-only, rights-aware data control plane이다. RTX 3080이 canonical node이며 실제 media, SQLite registry와 Parquet snapshot은 Git 밖의 `MIKU_DATA_ROOT`에 둔다.

```bash
export MIKU_DATA_ROOT=/dedicated/private/path
uv sync --project services/dataset-foundry --extra dev
uv run --project services/dataset-foundry miku-data init --dry-run
uv run --project services/dataset-foundry miku-data init
uv run --project services/dataset-foundry miku-data doctor
uv run --project services/dataset-foundry miku-data review serve
```

모든 write CLI는 `--dry-run`을 제공한다. Heavy audio 명령은 pinned worker manifest를 job queue에 넣으며 core process가 model dependency를 import하지 않는다. `review serve`는 `127.0.0.1`에만 bind한다. `pilot`은 infrastructure 검증용 synthetic tone/text를 quarantine으로 생성하며 training data나 target voice evidence가 아니다.

Review application은 audio waveform/playback/segment/transcript, technical evidence, rights,
persona annotation과 append-only history를 한 항목씩 검수한다. Accept review와 training promotion은
분리되어 있으며 `miku-data promote-sample --entity-type ... --entity-id ... --actor ...`가 source rights,
review evidence와 corpus quality를 다시 검사한다.

`miku-data import-agentic-receipt RECEIPT --actor ACTOR`는 schema-valid command/test/environment receipt를
canonical object로 먼저 보존한다. Source-bound receipt object가 없으면 SQLite trigger가
`execution_backed` trajectory 생성을 거부한다.

`miku-data import-duplex-bundle BUNDLE --actor ACTOR`는 schema와 timestamp/policy provenance를
행마다 검증하고 원본 JSONL을 canonical object로 보존한다. Synthetic timestamp evidence는 audio나
human adjudication으로 표시하지 않는다.

한국어 Wikimedia dump는 공식 SHA-1과 고정된 base-model tokenizer를 입력으로 정제한 뒤 별도
단계에서 승격한다. 정제 bundle은 문서 exact dedup, 문장 token-trigram MinHash/Jaccard dedup,
한국어 비율, UTF-8, boilerplate와 제한된 PII pattern을 기록한다. Source를 `licensed`, reviewed,
frozen `train` family로 먼저 확정하지 않으면 import는 실패한다.

```bash
miku-data prepare-wikimedia-text DUMP.xml.bz2 --output CLEAN.jsonl.gz \
  --tokenizer TOKENIZER.json --tokenizer-id REPOSITORY@REVISION \
  --expected-sha1 SHA1 --dump-date YYYYMMDD --processor-revision GIT_COMMIT
miku-data import-text-bundle CLEAN.jsonl.gz.manifest.json --source-id UUID --actor REVIEWER
```

Accepted row는 정제 text를 `normalized_text`에 한 번만 저장하고 원본 wikitext와 정제 bundle은
content-addressed object로 보존한다. 각 row의 attribution에는 page title, revision URL, license와
수정 여부를 기록한다.

현재 V0.1.0의 input 16 kHz와 output 22.05 kHz 관측값은 provenance로만 다룬다. CONDITIONAL feasibility 때문에 final training/streaming representation이나 production VoiceChat 성공을 가정하지 않는다.
