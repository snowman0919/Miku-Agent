from __future__ import annotations

import json
from collections.abc import Mapping


PERSONA_DIMENSIONS = {
    "purity", "liveliness", "warmth", "optimism", "curiosity", "creativity",
    "playfulness", "supportiveness", "independence", "digital_identity", "friendship", "helpfulness",
}


def _ppm(value: object, *, signed: bool = False) -> bool:
    lower = -1000000 if signed else 0
    return isinstance(value, int) and not isinstance(value, bool) and lower <= value <= 1000000


def assert_corpus_row_eligible(corpus: str, row: Mapping[str, object]) -> None:
    if corpus == "persona":
        if row["hard_violation"]:
            raise PermissionError("persona hard violation blocks training")
        dimensions = json.loads(str(row["dimensions_json"]))
        if set(dimensions) != PERSONA_DIMENSIONS:
            raise PermissionError("persona annotations do not cover all dimensions")
        for value in dimensions.values():
            if (not isinstance(value, dict) or not _ppm(value.get("score"), signed=True)
                    or not _ppm(value.get("confidence_ppm"))
                    or not isinstance(value.get("evaluator_id"), str) or not value["evaluator_id"]
                    or not isinstance(value.get("evaluator_revision"), str) or not value["evaluator_revision"]
                    or not (value.get("evidence_span") or value.get("reason_code"))
                    or (value.get("human_override") is not None
                        and not _ppm(value.get("human_override"), signed=True))):
                raise PermissionError("persona annotations lack valid evidence")
    elif corpus == "agentic" and row["execution_backed"]:
        if (row["verification_status"] != "execution_backed"
                or not row["execution_receipt_sha256"]
                or not row["environment_binding_json"]
                or not row["test_receipt_json"]):
            raise PermissionError("execution-backed trajectory lacks receipts")
