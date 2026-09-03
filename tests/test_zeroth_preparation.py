from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from tools import prepare_zeroth_stt as prepare


def test_selective_archive_extraction_rejects_traversal(tmp_path, monkeypatch):
    archive = tmp_path / "corpus.tar.gz"
    def pack(names):
        with tarfile.open(archive, "w:gz") as stream:
            for name in names:
                item = tarfile.TarInfo(name)
                item.size = 1
                stream.addfile(item, io.BytesIO(b"x"))
        monkeypatch.setattr(prepare, "ARCHIVE_SIZE", archive.stat().st_size)

    pack(["train_data_01/003/194/audio.flac", "zeroth_lexicon"])
    output = tmp_path / "safe"
    prepare.validate_and_extract(archive, output, prepare.sha256(archive))
    assert (output / "train_data_01/003/194/audio.flac").read_bytes() == b"x"
    assert not (output / "zeroth_lexicon").exists()
    pack(["train_data_01/../../../escape"])
    with pytest.raises(ValueError, match="unsafe archive member"):
        prepare.validate_and_extract(archive, tmp_path / "unsafe", prepare.sha256(archive))
    assert not (tmp_path / "escape").exists()


def test_mfa_batch_exposes_pinned_toolchain(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "make_mfa_corpus", lambda *_: tmp_path / "corpus")
    seen = []
    monkeypatch.setattr(prepare.subprocess, "run", lambda command, **kwargs: seen.append((command, kwargs)))
    prepare.align(tmp_path, tmp_path, [{"utterance_id": "one"}], tmp_path, 2)
    command, options = seen[0]
    assert command[0] == str(tmp_path / "environments/mfa-3.4.2/bin/mfa")
    assert options["env"]["PATH"].split(":")[0] == str(Path(command[0]).parent)
    assert options["check"] is True
