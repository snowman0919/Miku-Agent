# V0.1.0 RTX 5090 VoiceChat feasibility environment

이 디렉터리는 실험 환경만 정의한다. 모델 weight, checkpoint, 생성 음성 및
raw telemetry는 Git에 추가하지 않는다.

고정 입력:

- NVIDIA Speech: `097dfe9e2f55baf653b83035868bdc89849f1b47`
- VoiceChat checkpoint revision: `359ada7b1c60851e40ff08065f9b0340244f27e0`
- `model.safetensors` SHA-256: `d553750c29434a6bb524377e17634c6cafdbf621892e643a77f406e51570354b`
- PyTorch: `2.10.0` (CUDA 12.8 wheel)
- Python: `3.12`

환경 생성:

```bash
cd experiments/v0.1.0-rtx5090
nix develop
uv lock
./sync-env.sh
```

`flake.lock`과 `uv.lock` 생성 후에는 `uv lock`을 반복하지 않고
`nix develop --command ./sync-env.sh`로 동일 환경을 복원한다. WSL GPU driver는
host가 제공하는 `/usr/lib/wsl/lib/libcuda.so.1`을 사용하며 Nix flake는 Python,
compiler, FFmpeg와 userspace 도구를 고정한다.

`sync-env.sh`는 NVIDIA의 공식 VoiceChat 지침대로 training-only
`nvidia-resiliency-ext`를 sync 직후 제거하고 RTX 5090 `sm_120`, BF16,
TorchCodec, Mamba 및 causal-conv1d import를 검증한다.
