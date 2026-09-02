#!/usr/bin/env python3
"""Experimental BF16 function-calling probe using the pinned vendor flow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speech-source", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--api-response-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {"schema_version": 1, "mode": "bf16-cast", "result": "failed"}
    started = time.perf_counter()
    try:
        sys.path.insert(0, str(args.speech_source.resolve()))
        script = args.speech_source / "examples/speechlm2/offline_voicechat_fc_infer.py"
        spec = importlib.util.spec_from_file_location("vendor_fc", script)
        vendor_fc = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(vendor_fc)
        import torch
        from nemo.collections.speechlm2.inference.utils.offline_voicechat import (
            encode_system_prompt, load_hf_config, load_wav_16k_mono,
            render_fc_system_prompt, run_fc_offline_inference, save_fc_offline_outputs,
        )
        from nemo.collections.speechlm2.models.nemotron_voicechat import NemotronVoiceChat

        load_started = time.perf_counter()
        model = NemotronVoiceChat(load_hf_config(args.checkpoint))
        model = model.to(device="cuda", dtype=torch.bfloat16).eval()
        torch.cuda.synchronize()
        receipt["load_seconds"] = time.perf_counter() - load_started
        with args.api_response_json.open(encoding="utf-8") as handle:
            api_response = json.load(handle)
        system_prompt = render_fc_system_prompt(vendor_fc.DEFAULT_TEMPLATE, vendor_fc.DEFAULT_SYSTEM_MESSAGE, vendor_fc.DEFAULT_TOOLS)
        wav_1d, input_signal, input_signal_lens = load_wav_16k_mono(args.wav, device="cuda")
        prompt_tokens, prompt_token_lens = encode_system_prompt(model, system_prompt, device="cuda")
        torch.cuda.reset_peak_memory_stats()
        inference_started = time.perf_counter()
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            result, fc_output, call_step, response_step, resp_token_ids = run_fc_offline_inference(
                model,
                input_signal=input_signal,
                input_signal_lens=input_signal_lens,
                prompt_tokens=prompt_tokens,
                prompt_token_lens=prompt_token_lens,
                api_response=api_response,
                device="cuda",
            )
        torch.cuda.synchronize()
        inference_seconds = time.perf_counter() - inference_started
        paths = save_fc_offline_outputs(
            result, wav_1d, args.output_dir, fc_output, system_prompt, args.wav,
            sample_id="sample_fc", call_step=call_step, response_step=response_step,
            resp_token_len=len(resp_token_ids),
        )
        receipt.update({
            "result": "success",
            "inference_seconds": inference_seconds,
            "generated_text": result.get("text", [""])[0],
            "function_output": fc_output,
            "call_step": int(call_step) if call_step is not None else None,
            "response_step": int(response_step) if response_step is not None else None,
            "response_token_count": len(resp_token_ids),
            "output_artifact_ids": {key: Path(value).name for key, value in paths.items()},
            "cuda_max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
            "cuda_max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
        })
    except BaseException as exc:
        receipt.update({"exception_type": type(exc).__name__, "exception": str(exc), "traceback": traceback.format_exc()})
    receipt["duration_seconds"] = time.perf_counter() - started
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "traceback"}, indent=2, default=str))
    return 0 if receipt["result"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
