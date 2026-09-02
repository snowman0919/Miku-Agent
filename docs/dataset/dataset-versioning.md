# Dataset Versioning

Product `V0.2.0`과 dataset `miku-data-d0.1.0`, `miku-tts-d0.1.0`, `miku-persona-d0.1.0`, `miku-agentic-d0.1.0`, `miku-duplex-d0.1.0`을 분리한다. Release에는 schema/policy/evaluator version, source/sample count, physical/effective duration, rights/quality/language/split 분포, lineage root와 snapshot hash를 기록한다.

Canonical manifest의 root SHA-256이 dataset identity이고 Parquet hash도 별도 기록한다. 현재 pilot snapshot은 private local evidence이며 product release/tag가 아니다.
