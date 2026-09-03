# Data Governance

## Scope and rights

본 프로젝트는 개인 연구용이며 private repository는 저작권·상표·음원·모델의 사용 허가를 자동 보장하지 않는다. 모든 source는 origin, acquisition method, provenance, hash와 `owned`, `licensed`, `permitted`, `unknown`, `restricted`, `rejected` rights status를 갖는다. Registry 상태는 `accepted`, `quarantine`, `rejected`다.

`unknown` 또는 `restricted` source/sample은 accepted training set에 들어갈 수 없다. Cleared status와 별도로
`training_allowed=true`가 명시되어야 하며 자유문 `allowed_use`의 문자열 일치는 허가로 간주하지 않는다.
권리 근거가 불충분하면 quarantine을 유지한다. Raw media, processed audio, dataset, weight는 Git에 넣지
않고 V0.2.0에서 access-controlled object storage와 immutable registry 방향을 검증한다.

## Audio quality

Raw duration과 effective speech hours를 구분한다. Effective duration은 speech-likeness, quality, alignment confidence와 review disposition을 반영하며 최소 목표는 30 effective speech hours다. Singing과 speech corpus를 분리한다.

Source-separated singing에는 선율 기반 음소 길이, 긴 모음, 노래 pitch contour, 반주·reverb 잔류, separation artifact, 대화와 다른 호흡이 있으므로 speech duration·monotonic alignment의 주 자료로 쓰지 않는다. Speaker identity와 합성적 음색 등 제한된 auxiliary objective에만 사용한다.

## Verification and split

STT transcript는 독립 engine 교차 검증과 human review를 거쳐 raw/spoken/normalized text를 분리한다. Train/validation/test는 sample 단위가 아니라 source와 파생 계보 단위로 분리해 leakage를 막는다. 모든 변환은 parent hash와 tool/version을 provenance로 남긴다.
