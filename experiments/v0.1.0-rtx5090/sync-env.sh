#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${IN_NIX_SHELL:-}" ]]; then
  echo "error: enter this directory with 'nix develop' first" >&2
  exit 2
fi

uv sync --locked

# NVIDIA's pinned VoiceChat instructions remove this training-only package:
# NeMo pins 0.5.0 while Megatron's import-time check requires >=0.6.0.
uv pip uninstall --python .venv/bin/python nvidia-resiliency-ext || true

LD_LIBRARY_PATH="/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}" \
  .venv/bin/python - <<'PY'
import torch
import torchcodec
from transformers.utils.import_utils import (
    is_causal_conv1d_available,
    is_mamba_2_ssm_available,
)

assert torch.__version__.startswith("2.10.0+")
assert torch.cuda.is_available()
assert torch.cuda.get_device_capability(0) == (12, 0)
assert torch.cuda.is_bf16_supported()
assert is_mamba_2_ssm_available()
assert is_causal_conv1d_available()
print(
    torch.__version__,
    torch.version.cuda,
    torch.cuda.get_device_name(0),
    torch.cuda.get_device_capability(0),
)
PY
