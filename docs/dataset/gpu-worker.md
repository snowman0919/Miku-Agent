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

현재 확인한 host `mathcat`은 RTX 3080 10GB이고 root filesystem 여유가 9.6GB뿐이다.
따라서 이 host를 RTX 5090 worker root로 사용하거나 GPU model을 내려받지 않았다.
Ollama GPU workload도 자동 종료하지 않았다.

## 3080 integration requirement

3080 측 importer는 다음을 구현해야 한다.

1. job package 생성 전에 source/rights record를 bind하고 immutable input hash를 계산한다.
2. worker transfer 뒤 output manifest와 각 output hash를 독립 검증한다.
3. `result.status=completed`와 schema validation을 모두 확인한다.
4. technical score를 canonical acceptance와 분리해 human/automated policy를 적용한다.
5. imported result에 transform fingerprint, worker environment와 original job ID를 보존한다.

3080 DB schema와 importer location은 이 branch에서 추측하거나 수정하지 않는다.

