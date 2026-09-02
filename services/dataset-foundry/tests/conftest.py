from __future__ import annotations

from pathlib import Path

import pytest

from miku_foundry.config import FoundryPaths, initialize_layout
from miku_foundry.ingest import register_source
from miku_foundry.registry import Registry


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
                           training_status=training)
