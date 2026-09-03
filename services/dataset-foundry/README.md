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

현재 V0.1.0의 input 16 kHz와 output 22.05 kHz 관측값은 provenance로만 다룬다. CONDITIONAL feasibility 때문에 final training/streaming representation이나 production VoiceChat 성공을 가정하지 않는다.
