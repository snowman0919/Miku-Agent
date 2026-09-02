# Audio GPU environment

이 lock은 source separation, ASR, alignment, speaker embedding, quality와 prosody
candidate pilot 전용이다. V0.1.0 VoiceChat environment를 import하거나 수정하지 않는다.

```bash
cd experiments/v0.2.0-gpu-worker/environments/audio
nix develop ../.. --command bash -lc 'uv lock && uv sync --frozen'
```

Model weight는 `MIKU_WORKER_ROOT/models` 또는 external cache에만 둔다. Candidate가
선택되기 전에는 이 environment 자체가 default model 결정을 의미하지 않는다.
