"""Pinned model task adapters. Heavy dependencies are imported only in the audio environment."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from ..errors import WorkerError


def _context(parameters: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    model_path = parameters.pop("_model_path", None)
    binding = parameters.pop("_model_binding", None)
    if not isinstance(model_path, str) or not isinstance(binding, dict):
        raise WorkerError("MODEL_HASH_MISMATCH", "validated model context is missing")
    return Path(model_path), binding


def run_separation(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    model_root, binding = _context(parameters)
    try:
        import torch
        from demucs.apply import apply_model
        from demucs.audio import AudioFile, save_audio
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise WorkerError("MODEL_ACCESS_FAILED", f"separation environment unavailable: {exc}") from exc
    os.environ["TORCH_HOME"] = str(model_root)
    model = get_model(binding["model_id"]).to("cuda").eval()
    mixture = AudioFile(str(path)).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    reference = mixture.mean(0)
    scale = reference.std()
    if scale.item() == 0:
        scale = torch.ones_like(scale)
    normalized = (mixture - reference.mean()) / scale
    with torch.inference_mode():
        sources = apply_model(
            model, normalized[None], device="cuda", shifts=1, split=True,
            overlap=float(parameters.get("overlap", 0.25)), progress=False,
        )[0]
    sources = sources * scale + reference.mean()
    stems = dict(zip(model.sources, sources))
    if "vocals" not in stems:
        raise WorkerError("MODEL_OUTPUT_INVALID", "separation model returned no vocals stem")
    output_dir = Path(parameters.pop("_output_dir"))
    vocals = output_dir / "vocals.wav"
    residual = output_dir / "no_vocals.wav"
    save_audio(stems["vocals"], vocals, samplerate=model.samplerate, clip="rescale")
    save_audio(sum(value for name, value in stems.items() if name != "vocals"), residual,
               samplerate=model.samplerate, clip="rescale")
    return {
        "model_binding": binding,
        "duration_seconds": mixture.shape[-1] / model.samplerate,
        "_artifacts": [
            {"path": vocals, "logical_role": "vocals", "media_type": "audio/wav",
             "sample_rate": model.samplerate},
            {"path": residual, "logical_role": "residual", "media_type": "audio/wav",
             "sample_rate": model.samplerate},
        ],
    }


def run_asr(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    model_path, binding = _context(parameters)
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    except ImportError as exc:
        raise WorkerError("MODEL_ACCESS_FAILED", f"ASR environment unavailable: {exc}") from exc
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_path, dtype=torch.float16, local_files_only=True
    ).to("cuda").eval()
    recognizer = pipeline(
        "automatic-speech-recognition", model=model, tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor, device=0, torch_dtype=torch.float16,
    )
    result = recognizer(
        str(path), return_timestamps=True,
        generate_kwargs={"language": parameters.get("language", "ko"), "task": "transcribe"},
    )
    return {
        "model_binding": binding,
        "hypothesis": result["text"],
        "timestamps": result.get("chunks", []),
        "canonical_transcript": False,
    }


def run_alignment(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    model_path, binding = _context(parameters)
    transcript = parameters.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise WorkerError("MODEL_OUTPUT_INVALID", "forced alignment requires a transcript")
    if parameters.get("technical_pilot_only") is not True:
        raise WorkerError("MODEL_ACCESS_FAILED", "MMS alignment is blocked outside technical pilots")
    try:
        import librosa
        import torch
        import torchaudio
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    except ImportError as exc:
        raise WorkerError("MODEL_ACCESS_FAILED", f"alignment environment unavailable: {exc}") from exc
    samples, _ = librosa.load(path, sr=16000, mono=True)
    processor = Wav2Vec2Processor.from_pretrained(model_path, local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(
        model_path, dtype=torch.float16, local_files_only=True
    )
    processor.tokenizer.set_target_lang("kor")
    model.load_adapter("kor", adapter_kwargs={"cache_dir": str(model_path), "local_files_only": True})
    model = model.to("cuda").eval()
    token_ids = processor.tokenizer(transcript, add_special_tokens=False).input_ids
    values = processor(samples, sampling_rate=16000, return_tensors="pt")
    with torch.inference_mode():
        emission = model(values.input_values.to("cuda", dtype=torch.float16)).logits.log_softmax(-1)
        aligned, scores = torchaudio.functional.forced_align(
            emission, torch.tensor([token_ids], device="cuda"),
            blank=processor.tokenizer.pad_token_id,
        )
    spans = torchaudio.functional.merge_tokens(
        aligned[0].cpu(), scores[0].cpu(), blank=processor.tokenizer.pad_token_id
    )
    tokens = processor.tokenizer.convert_ids_to_tokens(token_ids)
    frame_seconds = (len(samples) / 16000) / emission.shape[1]
    intervals = [
        {
            "token": tokens[index],
            "start_seconds": span.start * frame_seconds,
            "end_seconds": span.end * frame_seconds,
            "confidence": math.exp(span.score),
        }
        for index, span in enumerate(spans)
    ]
    return {
        "model_binding": binding,
        "transcript": transcript,
        "token_intervals": intervals,
        "phoneme_timing": False,
        "license_gate": "BLOCKED_NONCOMMERCIAL",
    }


def run_speaker_embedding(path: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    model_path, binding = _context(parameters)
    try:
        import librosa
        import torch
        import torch.nn.functional as functional
        import torchaudio
        if not hasattr(torchaudio, "list_audio_backends"):
            torchaudio.list_audio_backends = lambda: []
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError as exc:
        raise WorkerError("MODEL_ACCESS_FAILED", f"speaker environment unavailable: {exc}") from exc
    samples, _ = librosa.load(path, sr=16000, mono=True)
    model = EncoderClassifier.from_hparams(
        source=str(model_path), savedir=None, run_opts={"device": "cuda"}
    )
    with torch.inference_mode():
        value = model.encode_batch(torch.tensor(samples, device="cuda").unsqueeze(0)).squeeze()
    embedding = functional.normalize(value, dim=0).cpu().tolist()
    return {
        "model_binding": binding,
        "embedding": embedding,
        "embedding_dimension": len(embedding),
        "normalization": "l2",
        "calibration_status": "NOT CALIBRATED",
    }
