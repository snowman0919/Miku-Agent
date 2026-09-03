# Rights Audit

- Rights records: owned 23, licensed 0, permitted 0, unknown 1, restricted 0, rejected 0.
- Explicit training scope: `training_allowed=true` 2, false/default 22.
- Unknown 1건은 speech render 계획용 candidate source이며 `candidate-render-planning-only`다.
- Training accepted sources/samples: 2/2,001. Agentic 1건과 timestamp-backed Duplex 2,000건이다.
- Unknown 또는 restricted training accepted: 0.
- Evaluation 6 source는 private evaluation only, fixture 15 source는 pipeline validation 용도다.

Owned local generation evidence는 Miku/SVS engine output 학습 조건이나 외부 corpus license를
대신하지 않는다. `allowed_use` 설명에 training 문자열이 있어도 명시적 `training_allowed=true`를
대신하지 않는다. 실제 source는 source별 rights evidence와 요구되는 human/evaluator review 전까지 quarantine이다.
