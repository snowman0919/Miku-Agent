from __future__ import annotations

from pathlib import Path

import pytest

from conftest import source
from miku_foundry.store import ObjectStore


def test_identical_content_is_one_object_with_two_references(foundry, tmp_path: Path):
    paths, registry = foundry
    first = source(registry, family="one")
    second = source(registry, family="two")
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"immutable payload")
    b.write_bytes(b"immutable payload")
    store = ObjectStore(paths, registry)
    assert store.ingest(a, first) == store.ingest(b, second)
    with registry.connect() as connection:
        assert connection.execute("SELECT count(*) FROM objects").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM source_objects").fetchone()[0] == 2


def test_sensitive_layout_permissions_are_private(foundry):
    paths, _ = foundry
    for directory in (paths.root, paths.root / "objects", paths.root / "registry", paths.root / "snapshots"):
        assert directory.stat().st_mode & 0o777 == 0o700
    assert paths.registry.stat().st_mode & 0o777 == 0o600


def test_corruption_is_detected_and_not_relabelled(foundry, tmp_path: Path):
    paths, registry = foundry
    source_id = source(registry)
    incoming = tmp_path / "payload.bin"
    incoming.write_bytes(b"original")
    store = ObjectStore(paths, registry)
    digest = store.ingest(incoming, source_id)
    target = paths.object_path(digest)
    target.chmod(0o600)
    target.write_bytes(b"corrupt")
    failures = store.verify()
    assert failures == [{"sha256": digest, "actual": store.hash_file(target)[0],
                         "size_bytes": 7, "error": "hash_mismatch"}]
    with registry.connect() as connection:
        assert connection.execute("SELECT sha256 FROM objects").fetchone()[0] == digest


def test_failed_source_reference_transaction_does_not_create_reference(foundry, tmp_path: Path):
    paths, registry = foundry
    incoming = tmp_path / "payload.bin"
    incoming.write_bytes(b"payload")
    with pytest.raises(Exception):
        ObjectStore(paths, registry).ingest(incoming, "missing-source")
    with registry.connect() as connection:
        assert connection.execute("SELECT count(*) FROM source_objects").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM objects").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM pending_ingests").fetchone()[0] == 1
    recovered = ObjectStore(paths, registry).reconcile()
    assert recovered["removed_orphans"] == 1
