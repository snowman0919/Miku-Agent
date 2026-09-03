# Rights Audit

- Current source rights: owned 23, licensed 1, permitted 0, unknown 1, restricted 0, rejected 0.
- Append-only rights records: owned 23, licensed 4, unknown 1. Licensed 4건은 Korean Wikipedia source의 provenance revision history다.
- Explicit training scope: `training_allowed=true` 3, false/default 22 sources.
- Unknown 1건은 speech render 계획용 candidate source이며 `candidate-render-planning-only`다.
- Training accepted sources/samples: 3/80,115. Agentic 3, timestamp-backed Duplex 2,000,
  CC BY-SA Korean Wikipedia text 78,112다.
- Unknown 또는 restricted training accepted: 0.
- Evaluation 6 source는 private evaluation only, fixture 15 source는 pipeline validation 용도다.

Korean Wikipedia corpus는 private internal training에만 허용했다. CC BY-SA attribution과
share-alike 의무 때문에 별도 compliance 검토 전에는 corpus, model, adapter 또는 파생물을
공개 배포하지 않는다. Owned local generation evidence도 Miku/SVS engine output 학습 조건이나
외부 corpus license를 대신하지 않는다. `allowed_use`의 training 문자열은 명시적
`training_allowed=true`를 대신하지 않는다.
