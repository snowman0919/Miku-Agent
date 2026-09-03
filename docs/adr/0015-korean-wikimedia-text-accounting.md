# ADR-0015: Korean Wikimedia Text Accounting and Private Training Scope

## Status
accepted

## Date
2026-09-03

## Context

Korean foundation의 100M token gate에는 고정 tokenizer, source 권리, attribution, 중복 제거와
품질 검사가 필요하다. 가변 `latest` URL이나 공백 단위 추정치는 dataset identity와 token 수를
재현하지 못한다. Wikimedia text를 수정·공유할 때는 CC BY-SA attribution과 share-alike 조건도
보존해야 한다.

## Decision

VoiceChat이 실제로 해석한 LLM backbone인
`nvidia/NVIDIA-Nemotron-Nano-9B-v2@6533e8de2c68e4536bf7c411d7a3ce5734111476`의
`tokenizer.json` SHA-256을 token gate에 고정한다. 공식 날짜별 Korean Wikipedia dump와 공식
checksum이 일치한 bytes만 처리한다. Main namespace의 non-redirect page를 UTF-8/NFC로 정제하고,
문서 SHA-256 exact dedup, 문장 token-trigram partitioned-MinHash와 Jaccard 0.90 near-dedup,
한국어 문자 비율, boilerplate와 PII pattern filter를 통과한 token만 센다.

CC BY-SA text는 private internal training에만 `licensed`와 `training_allowed=true`로 등록한다.
각 row에 page title, page URL, exact revision URL, license URL과 modified 표시를 보존한다. 정제
corpus 또는 그 downstream artifact를 외부에 공유하는 것은 별도 compliance review 전까지
허용하지 않는다. 이는 모델 output의 법적 성격에 관한 일반 결론이 아니라 이 private repository의
fail-closed 운영 범위다.

Wikimedia Korean dump 전체를 하나의 derivative family로 묶어 frozen `train` split에 배정한다.
고정 policy를 통과한 각 row에는 batch size 1 evaluator review evidence를 기록한다. Token 수는
human review 수로 표시하지 않는다.

## Alternatives Considered

- 공백 token 수: base model 입력량과 일치하지 않고 tokenizer 변경을 감지하지 못한다.
- 가변 `latest` dump: 같은 명령이 다른 bytes를 받을 수 있다.
- source-level random row split: 같은 article family의 train/eval 누출을 만든다.
- Attribution 없는 clean text: 공유 시 license 의무를 재구성할 수 없다.

## Consequences

Tokenizer나 quality policy가 바뀌면 corpus를 다시 계산하고 새 identity를 만든다. PII filter는 명시된
pattern만 다루며 모든 민감정보 제거를 보증하지 않는다. Public corpus, model, adapter 배포는 이
결정으로 허가되지 않는다.

## Security Impact

Raw dump, tokenizer, clean bundle, registry와 snapshot은 Git 밖의 private storage에만 둔다.
Checksum, current rights, accepted source review와 frozen train split이 하나라도 없으면 import가 실패한다.

## Data Impact

Accepted text row는 canonical bundle의 정제 text와 attribution provenance에 결속된다. Raw wikitext는
content-addressed source object로 보존하고 SQLite에는 정제 text를 한 번만 저장한다.

## Validation

실제 공식 dump 1,000-page slice와 고정 tokenizer로 checksum, dedup, PII, language, token, review,
idempotent import와 export gate를 검증한다. 전체 dump 결과는 dataset report와 snapshot receipt에
기록한다.

## Supersedes
None

## Superseded By
None
