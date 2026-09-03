from __future__ import annotations

from pathlib import Path

import pytest

from miku_foundry.config import FoundryPaths, initialize_layout
from miku_foundry.ingest import register_source
from miku_foundry.registry import Registry
from miku_foundry.review import add_review


@pytest.fixture
def foundry(tmp_path: Path) -> tuple[FoundryPaths, Registry]:
    paths = FoundryPaths(tmp_path / "foundry")
    initialize_layout(paths)
    registry = Registry(paths.registry)
    registry.initialize()
    return paths, registry


def source(registry: Registry, *, family: str = "family-a", quality: str = "passed",
           review: str = "reviewed", training: str = "quarantine") -> str:
    return register_source(registry, source_id=None, source_type="speech", title="fixture", origin="test-fixture",
                           acquisition_method="test generation", language="ko-KR", character_id="miku",
                           derivative_family=family, quality_status=quality, review_status=review,
                           training_status=training,
                           corpus_class="accepted_corpus" if training == "accepted" else "quarantine_real_corpus")


def accept_source_review(registry: Registry, source_id: str, *, expected_revision: int = 0) -> None:
    add_review(
        registry, "source", source_id, "accept", "operator", "source checked",
        expected_revision=expected_revision,
        evidence={"actor_type": "evaluator", "batch_size": 1, "media_reviewed_ms": 0},
    )
