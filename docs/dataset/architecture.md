# Dataset Foundry Architecture

RTX 3080은 canonical Git, SHA-256 object store와 SQLite WAL registry를 소유한다. 원본과 derived bytes는 `objects/sha256/<prefix>/<digest>`에 별도 object로 저장한다. SQLite는 source, 권리, transform lineage, review revision, split과 job state의 유일한 mutable source of truth다. DuckDB는 SQLite의 일관된 read 결과를 Parquet로 투영할 뿐 canonical writer가 아니다.

Filesystem과 SQLite 사이에는 단일 ACID commit이 없으므로 ingest intent를 먼저 기록한다. Staging copy 중 hash·size를 계산하고 fsync한 뒤 canonical path에 atomic promotion하고, registry transaction으로 object/reference/audit를 기록한다. 중단 상태는 `doctor`가 pending intent와 orphan을 reconciliation한다.

Dataset identity는 entity ID 순으로 정렬한 UTF-8/LF canonical JSONL의 SHA-256이다. 시간, local path와 Parquet compression은 identity record에서 제외한다. Duration과 score는 integer millisecond/ppm으로 저장한다.
