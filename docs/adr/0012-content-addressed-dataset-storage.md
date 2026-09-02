# ADR-0012: Content-Addressed Dataset Storage and Transactional Registry

## Status
accepted

## Date
2026-09-03

## Context

V0.2.0은 raw·derived data를 Git 밖에 보존하면서 중복, 부분 복사, object/metadata 불일치를 방지해야 한다. Filesystem rename과 SQLite commit은 하나의 원자 transaction이 아니므로 crash window를 숨길 수 없다.

## Decision

RTX 3080의 전용 `MIKU_DATA_ROOT`를 canonical data root로 사용한다. Byte identity는 SHA-256이며 `objects/sha256/<prefix>/<digest>`에 immutable하게 저장한다. SQLite WAL은 mutable canonical metadata와 durable ingest intent를 관리하고, Parquet는 분석 snapshot에만 사용한다. Staging copy, hash·fsync, no-clobber promotion, registry transaction과 startup recovery를 명시적 단계로 둔다. Dataset identity는 정렬된 canonical JSONL의 SHA-256이고 Parquet hash는 부가 artifact identity다.

## Alternatives Considered

- 파일명 기반 폴더: rename과 중복으로 identity가 흔들린다.
- DuckDB를 canonical mutable DB로 사용: job/review write transaction 책임이 불명확해진다.
- Git LFS에 media 저장: private repository라도 권리·용량·배포 위험을 만든다.

## Consequences

Object는 덮어쓰지 않고 모든 변환은 새 digest를 만든다. Cross-resource crash는 intent reconciliation로 복구한다. 실제 media·registry·Parquet는 Git에 들어가지 않는다.

## Security Impact

전용 root, 0700 directory와 0600 registry를 사용한다. Object route는 digest만 받으며 임의 path를 받지 않는다.

## Data Impact

원본 bytes, original filename metadata, transform provenance를 분리 보존한다. Snapshot compression이나 row order는 canonical dataset identity를 바꾸지 않는다.

## Validation

부분 ingest 복구, dedup, corruption, FK rollback, deterministic digest와 forbidden artifact test로 검증한다.

## Supersedes
None

## Superseded By
None
