# RTX 5090 Dataset GPU Worker

## 책임 분리

Worker는 technical score, evidence와 candidate classification만 만든다. Canonical
source registry, rights decision, human review result, training acceptance, split,
dataset version과 release는 3080 Dataset Foundry 소유다. Worker code에는 canonical
DB client나 arbitrary command field가 없다.

## Storage

`MIKU_WORKER_ROOT`는 local disposable storage로 지정한다. 기존 V0.1.0 VoiceChat
environment/model cache와 다른 경로여야 한다. 권장 상태 구조는 component README의
구조와 같으며 model cache와 output cache를 분리한다.

실제 worker는 SSH host `miku`의 `/home/kilexep/miku-data-worker`에 만들었다. 이 경로는
ext4 `/dev/sdd`의 disposable storage이며 확인 시 약 862 GiB가 비어 있었다. GPU는
RTX 5090 32,607 MiB이고 기존 V0.1.0 VoiceChat 환경과 model cache는 읽기 확인만 했으며
수정하지 않았다.

Core는 Nix/uv lock, 모델 작업은 별도 audio uv lock을 사용한다. 모델 weight와 pilot
media/결과는 worker root 또는 사용자 cache에만 있고 Git에는 없다.

## 3080 integration requirement

3080 측 importer는 다음을 구현해야 한다.

1. job package 생성 전에 source/rights record를 bind하고 immutable input hash를 계산한다.
2. worker transfer 뒤 output manifest와 각 output hash를 독립 검증한다.
3. `result.status=completed`와 schema validation을 모두 확인한다.
4. technical score를 canonical acceptance와 분리해 human/automated policy를 적용한다.
5. imported result에 transform fingerprint, worker environment와 original job ID를 보존한다.

3080 DB schema와 importer location은 이 branch에서 추측하거나 수정하지 않는다.
