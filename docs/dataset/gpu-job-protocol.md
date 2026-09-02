# GPU Worker Job Protocol

## 경계

Protocol version 1은 SSH와 rsync/scp로 옮길 수 있는 immutable filesystem package다.
Worker core는 transport를 알지 못하며 remote DB 또는 object store API를 호출하지
않는다. 3080 control plane만 검증된 result를 canonical state로 승격한다.

## 입력 package

각 job directory에는 `job.json`, `input-manifest.json`, `worker-spec.json`,
`source-binding.json`, `inputs/`가 필요하다. JSON Schema는
`schemas/gpu-worker/`에 있다.

- 모든 input은 상대 경로, byte size와 SHA-256로 bind한다.
- absolute path, `..`, package 밖으로 향하는 symlink를 거부한다.
- task type은 schema와 runtime의 같은 allowlist로 제한한다.
- worker spec은 code commit, software environment, determinism과 optional pinned
  model binding을 기록한다.
- `source-binding.json`의 rights 상태는 provenance input이며 worker가 변경하지 않는다.

## Fingerprint와 cache

Canonical JSON은 UTF-8, key sort, insignificant whitespace 제거 형식이다. Fingerprint는
task, transform name/version/parameters, ordered input hashes, code commit, software
environment와 model binding의 SHA-256다. 성공한 completed job만 cache source가 된다.
`--force`는 cache lookup을 생략한다.

## 상태와 결과

Directory rename으로 `inbox -> running -> completed|failed`를 이동한다. Output을
쓰다가 실패한 directory는 completed로 이동하지 않는다. Stale running directory는
`recover`에서 failed로 격리한다.

Completed package에는 `result.json`, `output-manifest.json`, `metrics.json`,
`environment.json`, `outputs/`가 있다. 3080은 transfer 뒤 `miku-worker verify`와
자체 manifest validator로 size와 hash를 다시 확인해야 한다.

## Error와 취소

실패는 `result.json.errors[]`에 stable error code, message, retryable을 기록한다.
Queued job만 즉시 cancel할 수 있다. Running process의 cooperative cancellation과
checkpoint/resume는 아직 구현하지 않았으며 integration 전 추가가 필요하다.

