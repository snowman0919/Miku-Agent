# V0.2.0 GPU worker environment

이 환경은 V0.1.0 VoiceChat 환경과 분리한다. 모델 weight, cache, raw media와 pilot
output은 Git에 추가하지 않는다. `run_reference_pilot.py`는 허용된 synthetic PCM
tone을 임시 디렉터리에 만들고 종료 시 삭제한다.

`flake.lock`과 `uv.lock`은 실제 RTX 5090 node에서 resolve한다. Core lock은 protocol
test 도구만 포함한다. GPU model dependency가 충돌하면 `environments/` 아래 task
family별 lock으로 분리하며 VoiceChat environment는 재사용하거나 수정하지 않는다.

Reference protocol pilot:

```bash
/path/to/python run_reference_pilot.py --count-per-task 50 --code-commit <commit>
```

이 pilot은 worker integrity와 PCM feature path를 검증할 뿐 GPU capability benchmark가
아니다.

GPU candidate runner는 `benchmark_{separation,asr,alignment,speaker}.py`다. 모두
generated fixture, local immutable model snapshot과 repository 밖 output 경로를 사용한다.
정확한 실행 결과와 제한은 `reports/v0.2.0-5090-worker.md`에 기록한다.
