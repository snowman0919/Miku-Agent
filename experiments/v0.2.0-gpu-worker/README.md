# V0.2.0 GPU worker environment

이 환경은 V0.1.0 VoiceChat 환경과 분리한다. 모델 weight, cache, raw media와 pilot
output은 Git에 추가하지 않는다. `run_reference_pilot.py`는 허용된 synthetic PCM
tone을 임시 디렉터리에 만들고 종료 시 삭제한다.

현재 checkout에는 `uv.lock`과 `flake.lock`을 만들지 않았다. lock 생성에는 network
resolution이 필요하며 현재 호스트가 요구된 RTX 5090 worker가 아니므로 GPU model
환경을 거짓으로 고정하지 않는다. 실제 RTX 5090 노드에서 후보를 확정한 뒤 lock을
생성하고 hash와 함께 검증해야 한다.

Reference protocol pilot:

```bash
/path/to/python run_reference_pilot.py --count-per-task 50 --code-commit <commit>
```

이 pilot은 worker integrity와 PCM feature path를 검증할 뿐 GPU capability benchmark가
아니다.
