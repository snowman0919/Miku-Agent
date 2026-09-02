"""Structured worker errors."""

from __future__ import annotations

from dataclasses import dataclass


ERROR_CODES = frozenset(
    {
        "INPUT_HASH_MISMATCH",
        "INPUT_DECODE_FAILED",
        "MODEL_ACCESS_FAILED",
        "MODEL_HASH_MISMATCH",
        "UNSUPPORTED_FORMAT",
        "CUDA_OOM",
        "CUDA_KERNEL_ERROR",
        "OUT_OF_DISK",
        "TIMEOUT",
        "CANCELLED",
        "MODEL_OUTPUT_INVALID",
        "OUTPUT_HASH_FAILED",
        "ENVIRONMENT_MISMATCH",
        "UNKNOWN",
    }
)


@dataclass(slots=True)
class WorkerError(Exception):
    code: str
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            raise ValueError(f"unknown worker error code: {self.code}")
        super().__init__(self.message)

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}

