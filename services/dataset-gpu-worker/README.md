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
- reference transform: PCM16 WAV `audio_quality`, frame별 F0/energy/voicing을 보존하는
  `prosody_extract` 구현
- model transform: source separation, ASR, forced alignment, speaker embedding adapter를
  pinned registry와 job protocol에 연결했다. 한국어 정렬은 MFA 3.4.2와 Korean MFA
  acoustic/dictionary 3.0.0을 사용하며 word/phone interval을 반환한다. Runtime/model이
  없거나 hash가 다르면 `MODEL_ACCESS_FAILED`/`MODEL_HASH_MISMATCH`로 실패한다.
- canonical decision: 출력에서 `accepted_for_training`, `training_status`,
  `rights_status`, `eval_split`을 재귀적으로 거부

Reference transform의 quality와 voicing 값은 `NOT CALIBRATED` proxy이며 canonical
accept/reject 근거가 아니다.
