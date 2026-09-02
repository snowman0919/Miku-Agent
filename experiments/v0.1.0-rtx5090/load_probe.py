#!/usr/bin/env python3
"""Measure VoiceChat model loading without committing model artifacts.

This probe deliberately keeps the vendor FP32 path separate from the BF16
feasibility path. It writes a JSON receipt even when loading raises an error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--speech-source", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--mode", choices=("vendor-fp32", "bf16-default", "bf16-cast"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wav")
    parser.add_argument("--inference-output-dir")
    parser.add_argument(
        "--system-prompt",
        default=(
            "You are an AI voice assistant developed by NVIDIA. "
            "Your name is NVIDIA Voice Chat. "
            "Answer in a spoken, conversational style rather than a written one. "
            "Do not repeat the same sentence over and over again. "
            "Start the conversation by greeting the user."
        ),
    )
    parser.add_argument("--sample-interval", type=float, default=0.25)
    return parser.parse_args()


def proc_status() -> dict[str, int]:
    values: dict[str, int] = {}
    with open("/proc/self/status", encoding="utf-8") as handle:
        for line in handle:
            key, _, value = line.partition(":")
            if key in {"VmRSS", "VmHWM", "VmSize", "VmPeak"}:
                values[key + "_kib"] = int(value.strip().split()[0])
    return values


def system_memory() -> dict[str, int]:
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, _, value = line.partition(":")
            if key in wanted:
                values[key + "_kib"] = int(value.strip().split()[0])
    return values


def gpu_sample() -> dict[str, object]:
    command = [
        "/usr/lib/wsl/lib/nvidia-smi",
        "--query-gpu=timestamp,name,uuid,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        fields = subprocess.check_output(command, text=True, timeout=2).strip().split(", ")
        return {
            "timestamp": fields[0],
            "name": fields[1],
            "uuid": fields[2],
            "memory_used_mib": float(fields[3]),
            "memory_total_mib": float(fields[4]),
            "utilization_percent": float(fields[5]),
            "temperature_c": float(fields[6]),
            "power_w": float(fields[7]),
        }
    except Exception as exc:  # telemetry must never mask the model result
        return {"error": repr(exc)}


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started_wall = time.time()
    started_mono = time.perf_counter()
    samples: list[dict[str, object]] = []
    stop = threading.Event()

    def sample_loop() -> None:
        while not stop.is_set():
            samples.append(
                {
                    "elapsed_seconds": time.perf_counter() - started_mono,
                    "process": proc_status(),
                    "system": system_memory(),
                    "gpu": gpu_sample(),
                }
            )
            stop.wait(args.sample_interval)

    sampler = threading.Thread(target=sample_loop, name="telemetry", daemon=True)
    sampler.start()
    receipt: dict[str, object] = {
        "schema_version": 1,
        "mode": args.mode,
        "speech_source": str(Path(args.speech_source).resolve()),
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "hostname": os.uname().nodename,
        "started_unix_seconds": started_wall,
    }
    exit_code = 0

    try:
        sys.path.insert(0, str(Path(args.speech_source).resolve()))
        import torch

        from nemo.collections.speechlm2.inference.utils.offline_voicechat import (
            build_model,
            encode_system_prompt,
            load_wav_16k_mono,
            load_hf_config,
            run_offline_inference,
            save_offline_outputs,
        )
        from nemo.collections.speechlm2.models.nemotron_voicechat import NemotronVoiceChat

        receipt["torch"] = {
            "version": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "bf16_supported": torch.cuda.is_bf16_supported(),
        }
        torch.cuda.reset_peak_memory_stats()
        load_started = time.perf_counter()
        if args.mode == "vendor-fp32":
            model = build_model(args.checkpoint, device="cuda")
        elif args.mode == "bf16-default":
            previous_dtype = torch.get_default_dtype()
            try:
                torch.set_default_dtype(torch.bfloat16)
                model = NemotronVoiceChat(load_hf_config(args.checkpoint))
            finally:
                torch.set_default_dtype(previous_dtype)
            model = model.to("cuda").eval()
        else:
            model = NemotronVoiceChat(load_hf_config(args.checkpoint))
            model = model.to(device="cuda", dtype=torch.bfloat16).eval()
        torch.cuda.synchronize()
        receipt["load_seconds"] = time.perf_counter() - load_started

        dtype_counts: Counter[str] = Counter()
        dtype_bytes: Counter[str] = Counter()
        parameter_count = 0
        for parameter in model.parameters():
            name = str(parameter.dtype)
            dtype_counts[name] += parameter.numel()
            dtype_bytes[name] += parameter.numel() * parameter.element_size()
            parameter_count += parameter.numel()
        receipt["result"] = "loaded"
        receipt["parameter_count"] = parameter_count
        receipt["parameter_elements_by_dtype"] = dict(dtype_counts)
        receipt["parameter_bytes_by_dtype"] = dict(dtype_bytes)
        receipt["cuda_memory_allocated_bytes"] = torch.cuda.memory_allocated()
        receipt["cuda_max_memory_allocated_bytes"] = torch.cuda.max_memory_allocated()
        receipt["cuda_memory_reserved_bytes"] = torch.cuda.memory_reserved()
        receipt["cuda_max_memory_reserved_bytes"] = torch.cuda.max_memory_reserved()
        if args.wav:
            if not args.inference_output_dir:
                raise ValueError("--inference-output-dir is required with --wav")
            wav_1d, input_signal, input_signal_lens = load_wav_16k_mono(args.wav, device="cuda")
            prompt_tokens, prompt_token_lens = encode_system_prompt(model, args.system_prompt, device="cuda")
            torch.cuda.reset_peak_memory_stats()
            inference_started = time.perf_counter()
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=args.mode == "bf16-cast"):
                result = run_offline_inference(
                    model,
                    input_signal=input_signal,
                    input_signal_lens=input_signal_lens,
                    prompt_tokens=prompt_tokens,
                    prompt_token_lens=prompt_token_lens,
                )
            torch.cuda.synchronize()
            inference_seconds = time.perf_counter() - inference_started
            paths = save_offline_outputs(result, wav_1d, args.inference_output_dir, args.wav)
            output_samples = int(result["audio_len"][0].item()) if result.get("audio_len") is not None else 0
            input_seconds = wav_1d.shape[0] / 16000
            output_seconds = output_samples / 22050
            receipt["inference"] = {
                "input_wav": str(Path(args.wav).resolve()),
                "input_audio_seconds": input_seconds,
                "output_audio_seconds": output_seconds,
                "wall_seconds": inference_seconds,
                "rtf_vs_input": inference_seconds / input_seconds if input_seconds else None,
                "rtf_vs_output": inference_seconds / output_seconds if output_seconds else None,
                "text": result.get("text", [""])[0],
                "output_paths": paths,
                "cuda_max_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
                "cuda_max_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
            }
        del model
        torch.cuda.empty_cache()
    except BaseException as exc:
        exit_code = 1
        receipt["result"] = "failed"
        receipt["exception_type"] = type(exc).__name__
        receipt["exception"] = str(exc)
        receipt["traceback"] = traceback.format_exc()
    finally:
        stop.set()
        sampler.join(timeout=max(2.0, args.sample_interval * 2))
        samples.append(
            {
                "elapsed_seconds": time.perf_counter() - started_mono,
                "process": proc_status(),
                "system": system_memory(),
                "gpu": gpu_sample(),
            }
        )
        receipt["duration_seconds"] = time.perf_counter() - started_mono
        receipt["process_final"] = proc_status()
        receipt["telemetry"] = samples
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in receipt.items() if key != "telemetry"}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
