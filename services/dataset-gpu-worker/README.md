# Dataset GPU Worker

이 component는 canonical Dataset Foundry와 분리된 삭제 가능한 staged worker다.
canonical registry, rights decision, training acceptance, split과 dataset version을
읽거나 쓰지 않는다. Transport는 filesystem package이며 task type은 allowlist다.

## 실행

Python 3.11+와 `jsonschema`가 있는 격리 환경에서 package를 설치한다.

```bash
python -m pip install -e services/dataset-gpu-worker
export MIKU_WORKER_ROOT=/local/nvme/miku-data-worker
miku-worker doctor
miku-worker inspect /path/to/job-package
miku-worker submit /path/to/job-package
miku-worker run --job <job-id>
miku-worker verify <job-id>
```

`MIKU_WORKER_ROOT`는 canonical storage가 아니며 `jobs`, `objects`, `models`,
`environments`, `metrics`, `logs`, `tmp`만 포함한다. `run --watch-inbox`는 현재
inbox snapshot을 한 번 drain하므로 user session scheduler가 반복 호출해야 한다.

## 구현 상태

- protocol/core: schema, input hash, fingerprint, atomic rename, output manifest,
  structured error, OS GPU lock, stale recovery, cache verification 구현
- reference transform: PCM16 WAV `audio_quality`, `prosody_extract` 구현
- model transform: allowlist와 failure boundary만 구현; pinned backend 미설치 시
  `MODEL_ACCESS_FAILED`
- canonical decision: 출력에서 `accepted_for_training`, `training_status`,
  `rights_status`, `eval_split`을 재귀적으로 거부

Reference transform의 quality와 voicing 값은 `NOT CALIBRATED` proxy이며 canonical
accept/reject 근거가 아니다.

