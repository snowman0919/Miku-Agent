#!/usr/bin/env python3
"""Exercise the CUDA paths used by VoiceChat on Blackwell."""

from __future__ import annotations

import json
import traceback


def attempt(name, fn, results):
    try:
        value = fn()
        results[name] = {"status": "PASS", "value": str(value)}
    except BaseException as exc:
        results[name] = {"status": "FAIL", "exception_type": type(exc).__name__, "exception": str(exc), "traceback": traceback.format_exc()}


def main() -> int:
    import torch
    import torch.nn.functional as functional

    results = {
        "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "device": torch.cuda.get_device_name(0), "capability": list(torch.cuda.get_device_capability(0)),
    }
    attempt("cuda_allocation", lambda: torch.ones(1024, device="cuda").sum().item(), results)
    for dtype in (torch.bfloat16, torch.float16):
        attempt(f"matmul_{dtype}", lambda dtype=dtype: (torch.randn(512, 512, device="cuda", dtype=dtype) @ torch.randn(512, 512, device="cuda", dtype=dtype)).mean().item(), results)
    attempt("sdpa_bf16", lambda: functional.scaled_dot_product_attention(*[torch.randn(1, 4, 128, 64, device="cuda", dtype=torch.bfloat16) for _ in range(3)]).shape, results)
    attempt("triton", lambda: __import__("triton").__version__, results)
    attempt("causal_conv1d_import", lambda: __import__("causal_conv1d").__version__, results)

    def mamba_forward():
        from mamba_ssm import Mamba2
        module = Mamba2(d_model=64, d_state=64, d_conv=4, expand=2, headdim=32).cuda().to(torch.bfloat16)
        return module(torch.randn(1, 64, 64, device="cuda", dtype=torch.bfloat16)).shape

    attempt("mamba2_bf16_forward", mamba_forward, results)
    for package in ("flash_attn", "transformer_engine", "vllm"):
        attempt(f"{package}_import", lambda package=package: __import__(package).__version__, results)
    print(json.dumps(results, indent=2, sort_keys=True))
    critical = ("cuda_allocation", "matmul_torch.bfloat16", "matmul_torch.float16", "sdpa_bf16", "triton", "causal_conv1d_import", "mamba2_bf16_forward")
    return any(results.get(name, {}).get("status") != "PASS" for name in critical)


if __name__ == "__main__":
    raise SystemExit(main())
