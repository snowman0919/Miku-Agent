from __future__ import annotations

import bz2
import json
from pathlib import Path

from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from conftest import accept_source_review
from miku_foundry.export import export_training
from miku_foundry.ingest import register_source
from miku_foundry.rights import promote_training, register_rights
from miku_foundry.split import assign_group
from miku_foundry.store import ObjectStore
from miku_foundry.wikimedia import import_text_bundle, prepare_wikimedia_text


def _article(label: str, *, shared: bool = False, pii: bool = False) -> str:
    common = [
        "한국어 자료의 품질을 확인하는 과정은 정확한 출처 기록과 책임 있는 검토 절차와 투명한 처리 이력을 모두 포함한다.",
        "문서의 구조와 문장 흐름을 세밀하게 살피면 반복 표현과 불필요한 안내 문구를 안정적으로 찾아서 제거할 수 있다.",
        "학습 자료는 권리 상태와 처리 이력을 함께 보존해야 나중에 같은 결과와 판단 근거를 다시 정확하게 검증할 수 있다.",
    ]
    if shared:
        common = [sentence[:-1] + " 또한." for sentence in common]
    unique = [
        f"{label} 연구 기록은 다양한 어휘와 자연스러운 문맥을 제공하며 한국어 표현의 폭을 넓히는 데 도움이 된다.",
        f"{label} 관찰 결과는 역사와 과학과 문화에 관한 설명을 균형 있게 연결하여 독자의 이해를 돕는다.",
        f"{label} 편집 원칙은 사실 관계를 신중하게 확인하고 명확한 문장으로 정보를 전달하는 일을 중요하게 여긴다.",
        f"{label} 분석 과정에서는 문서마다 고유한 주제와 서술 방식을 보존하여 의미 다양성을 유지한다.",
        f"{label} 검증 자료는 공개된 근거와 수정 시점을 남겨 장기적인 재현성과 투명성을 높인다.",
        f"{label} 설명은 독립적인 관점들을 비교하고 핵심 개념 사이의 관계를 충분한 맥락과 함께 제시한다.",
    ]
    sentences = common + unique
    if pii:
        sentences.insert(0, "개인 연락처 test@example.com 정보는 학습 문장에서 반드시 제거되어야 한다.")
    return " ".join(sentences)


def _dump(path: Path) -> str:
    first = _article("첫째")
    pages = [first, first, _article("둘째", shared=True), _article("셋째", pii=True)]
    body = "".join(
        f"<page><title>문서 {index}</title><ns>0</ns><id>{index}</id>"
        f"<revision><id>{100 + index}</id><timestamp>2026-09-01T00:00:00Z</timestamp>"
        f"<text xml:space='preserve'>{text}</text></revision></page>"
        for index, text in enumerate(pages, 1)
    )
    xml = f"<mediawiki xmlns='http://www.mediawiki.org/xml/export-0.11/'>{body}</mediawiki>"
    path.write_bytes(bz2.compress(xml.encode()))
    import hashlib
    return hashlib.sha1(path.read_bytes()).hexdigest()


def test_wikimedia_text_is_integrity_checked_deduplicated_reviewed_and_exportable(foundry, tmp_path: Path):
    paths, registry = foundry
    dump = tmp_path / "kowiki.xml.bz2"
    expected_sha1 = _dump(dump)
    tokenizer_path = tmp_path / "tokenizer.json"
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.save(str(tokenizer_path))
    bundle = tmp_path / "kowiki.jsonl.gz"

    manifest = prepare_wikimedia_text(
        dump, bundle, tokenizer_path, expected_sha1=expected_sha1, dump_date="20260901",
        tokenizer_id="fixture/tokenizer@1", processor_revision="1" * 40,
    )
    assert manifest["stats"]["documents_accepted"] == 3
    assert manifest["stats"]["exact_documents_removed"] == 1
    assert manifest["stats"]["near_sentences_removed"] >= 3
    assert manifest["stats"]["pii_sentences_removed"] == 1

    source_id = register_source(
        registry, source_id=None, source_type="text", title="Korean Wikipedia fixture",
        origin="https://dumps.wikimedia.org/", acquisition_method="verified dump",
        language="ko-KR", character_id="miku", derivative_family="wikimedia-ko-fixture",
        quality_status="passed", review_status="reviewed",
    )
    register_rights(registry, source_id, "licensed", "license", "fixture CC BY-SA evidence", "training",
                    reviewer="operator", actor_type="user", training_allowed=True)
    accept_source_review(registry, source_id)
    promote_training(registry, source_id, actor="operator")
    assign_group(registry, "wikimedia-ko-fixture", split="train", freeze=True)
    store = ObjectStore(paths, registry)
    store.ingest(dump, source_id, role="text:raw_dump", media_type="application/x-bzip2")
    store.ingest(tokenizer_path, source_id, role="text:tokenizer", media_type="application/json")

    imported = import_text_bundle(paths, registry, Path(manifest["manifest_path"]), source_id, actor="operator")
    assert imported["count"] == 3 and imported["tokens"] == manifest["stats"]["tokens_accepted"]
    assert import_text_bundle(paths, registry, Path(manifest["manifest_path"]), source_id,
                              actor="operator")["idempotent"] is True
    exported = export_training(registry, tmp_path / "train.jsonl", split="train", corpus="text")
    assert exported["count"] == 3
    with registry.connect() as connection:
        assert connection.execute(
            "SELECT count(*) FROM reviews WHERE entity_type='text' AND decision='accept'"
        ).fetchone()[0] == 3
        provenance = json.loads(connection.execute(
            "SELECT provenance_json FROM text_samples ORDER BY sample_id LIMIT 1"
        ).fetchone()[0])
    assert provenance["source_page_url"].startswith("https://ko.wikipedia.org/")
