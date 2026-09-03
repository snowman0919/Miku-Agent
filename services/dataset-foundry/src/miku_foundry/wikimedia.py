from __future__ import annotations

import bz2
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import mwparserfromhell
from tokenizers import Tokenizer

from .config import FoundryPaths
from .eligibility import assert_corpus_row_eligible
from .registry import Registry
from .store import ObjectStore


POLICY = {
    "id": "wikimedia-ko-text-v1",
    "language": "ko",
    "minimum_hangul_letter_ratio_ppm": 300000,
    "minimum_document_characters": 200,
    "minimum_document_tokens": 40,
    "document_dedup": "sha256(nfc+collapsed-whitespace)",
    "sentence_dedup": "token-trigram-partitioned-minhash+jaccard>=0.90",
    "pii": "drop sentence matching email, Korean resident number, phone, or IPv4",
    "boilerplate": "strip wikitext and trailing references/external-links sections",
}
POLICY_JSON = json.dumps(POLICY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
POLICY_SHA256 = hashlib.sha256(POLICY_JSON.encode()).hexdigest()
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
TRAILING_SECTION_RE = re.compile(
    r"(?mi)^==+\s*(?:참고\s*문헌|참고\s*자료|외부\s*링크|같이\s*보기|각주|주해|출처)\s*==+.*\Z",
    re.DOTALL,
)
BOILERPLATE_LINE_RE = re.compile(
    r"^(?:분류:|파일:|섬네일|위키미디어 공용|이 글은 .*토막글입니다)", re.IGNORECASE
)
PII_RE = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{6}-[1-4]\d{6}\b|"
    r"(?<!\d)(?:\+?82[- .]?)?0?1[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b)"
)


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def _dedup_normalize(value: str) -> str:
    value = re.sub(r"\d+", "0", _normalize(value).lower())
    return " ".join(TOKEN_RE.findall(value))


def _shingles(value: str) -> set[tuple[str, str, str]]:
    tokens = TOKEN_RE.findall(value)
    return set(zip(tokens, tokens[1:], tokens[2:]))


def _signature(shingles: set[tuple[str, str, str]]) -> tuple[int, int, int, int] | None:
    if len(shingles) < 4:
        return None
    values = [2**30] * 4
    for shingle in shingles:
        digest = zlib.crc32("\0".join(shingle).encode())
        bucket, value = digest >> 30, digest & (2**30 - 1)
        values[bucket] = min(values[bucket], value)
    return tuple(-1 if value == 2**30 else value for value in values)  # type: ignore[return-value]


class _Deduper:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.executescript(
            """CREATE TABLE documents(hash TEXT PRIMARY KEY);
               CREATE TABLE sentences(exact_hash TEXT PRIMARY KEY, normalized TEXT NOT NULL,
                                      h0 INTEGER, h1 INTEGER, h2 INTEGER, h3 INTEGER);
               CREATE INDEX sentence_h0 ON sentences(h0);
               CREATE INDEX sentence_h1 ON sentences(h1);
               CREATE INDEX sentence_h2 ON sentences(h2);
               CREATE INDEX sentence_h3 ON sentences(h3);"""
        )

    def close(self) -> None:
        self.connection.close()

    def begin_document(self, document_hash: str) -> bool:
        self.connection.execute("SAVEPOINT document")
        try:
            self.connection.execute("INSERT INTO documents VALUES (?)", (document_hash,))
            return True
        except sqlite3.IntegrityError:
            self.connection.execute("ROLLBACK TO document")
            self.connection.execute("RELEASE document")
            return False

    def reject_document(self) -> None:
        self.connection.execute("ROLLBACK TO document")
        self.connection.execute("RELEASE document")

    def accept_document(self) -> None:
        self.connection.execute("RELEASE document")

    def accept_sentence(self, sentence: str) -> tuple[bool, str | None]:
        normalized = _dedup_normalize(sentence)
        exact_hash = hashlib.sha256(normalized.encode()).hexdigest()
        if self.connection.execute(
            "SELECT 1 FROM sentences WHERE exact_hash=?", (exact_hash,)
        ).fetchone():
            return False, "exact"
        shingles = _shingles(normalized)
        signature = _signature(shingles)
        if signature:
            queries, parameters = [], []
            for index, value in enumerate(signature):
                if value >= 0:
                    queries.append(f"SELECT rowid rid,normalized FROM sentences WHERE h{index}=?")
                    parameters.append(value)
            if len(queries) >= 2:
                sql = (
                    "SELECT normalized FROM (" + " UNION ALL ".join(queries)
                    + ") GROUP BY rid HAVING count(*)>=2"
                )
                for row in self.connection.execute(sql, parameters):
                    other = _shingles(row[0])
                    if other and len(shingles & other) / len(shingles | other) >= 0.90:
                        return False, "near"
        bands = signature or (-1, -1, -1, -1)
        self.connection.execute(
            "INSERT INTO sentences VALUES (?,?,?,?,?,?)",
            (exact_hash, normalized, *bands),
        )
        return True, None


def _hangul_ratio_ppm(value: str) -> int:
    letters = sum(unicodedata.category(char).startswith("L") for char in value)
    hangul = sum("\uac00" <= char <= "\ud7a3" or "\u1100" <= char <= "\u11ff" for char in value)
    return hangul * 1_000_000 // letters if letters else 0


def _plain_text(wikitext: str) -> str:
    wikitext = TRAILING_SECTION_RE.sub("", wikitext)
    stripped = mwparserfromhell.parse(wikitext).strip_code(normalize=True, collapse=True) or ""
    return "\n".join(
        line for line in (_normalize(line) for line in stripped.splitlines())
        if line and not BOILERPLATE_LINE_RE.match(line)
    )


def _clean_document(plain: str, deduper: _Deduper) -> tuple[str, dict[str, int]]:
    stats = {"pii_sentences_removed": 0, "exact_sentences_removed": 0, "near_sentences_removed": 0}
    kept = []
    for sentence in SENTENCE_RE.split(plain):
        sentence = _normalize(sentence)
        if len(sentence) < 20:
            continue
        if PII_RE.search(sentence):
            stats["pii_sentences_removed"] += 1
            continue
        accepted, reason = deduper.accept_sentence(sentence)
        if accepted:
            kept.append(sentence)
        elif reason:
            stats[f"{reason}_sentences_removed"] += 1
    return "\n".join(kept), stats


def prepare_wikimedia_text(
    dump_path: Path,
    output_path: Path,
    tokenizer_path: Path,
    *,
    expected_sha1: str,
    dump_date: str,
    tokenizer_id: str,
    max_pages: int | None = None,
) -> dict[str, object]:
    dump_path = dump_path.resolve(strict=True)
    tokenizer_path = tokenizer_path.resolve(strict=True)
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max pages must be positive")
    if output_path.exists() or output_path.with_suffix(output_path.suffix + ".manifest.json").exists():
        raise FileExistsError(output_path)
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha1) or _hash_file(dump_path, "sha1") != expected_sha1:
        raise ValueError("Wikimedia dump SHA-1 mismatch")
    if not re.fullmatch(r"\d{8}", dump_date) or not tokenizer_id.strip():
        raise ValueError("dump date and tokenizer identity are required")
    tokenizer_sha256 = _hash_file(tokenizer_path)
    dump_sha256 = _hash_file(dump_path)
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    dedup_path = temporary.with_suffix(".sqlite3")
    deduper = _Deduper(dedup_path)
    stats = {
        "pages_seen": 0,
        "malformed_pages_skipped": 0,
        "redirects_skipped": 0,
        "short_or_non_korean_skipped": 0,
        "exact_documents_removed": 0,
        "clean_documents_removed": 0,
        "documents_accepted": 0,
        "tokens_accepted": 0,
        "pii_sentences_removed": 0,
        "exact_sentences_removed": 0,
        "near_sentences_removed": 0,
    }
    try:
        with temporary.open("wb") as raw_output, gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, compresslevel=6, mtime=0
        ) as output, bz2.open(dump_path, "rb") as source:
            for _, page in ET.iterparse(source, events=("end",)):
                if not page.tag.endswith("}page"):
                    continue
                namespace = page.findtext("./{*}ns")
                if namespace != "0":
                    page.clear()
                    continue
                stats["pages_seen"] += 1
                if page.find("./{*}redirect") is not None:
                    stats["redirects_skipped"] += 1
                    page.clear()
                    if max_pages and stats["pages_seen"] >= max_pages:
                        break
                    continue
                title = page.findtext("./{*}title") or ""
                page_id = page.findtext("./{*}id") or ""
                revision = page.find("./{*}revision")
                revision_id = revision.findtext("./{*}id") if revision is not None else ""
                timestamp = revision.findtext("./{*}timestamp") if revision is not None else ""
                wikitext = revision.findtext("./{*}text") if revision is not None else ""
                if not page_id.isdigit() or not (revision_id or "").isdigit() or not timestamp or wikitext is None:
                    stats["malformed_pages_skipped"] += 1
                    page.clear()
                    if max_pages and stats["pages_seen"] >= max_pages:
                        break
                    continue
                plain = _plain_text(wikitext or "")
                if (len(plain) < POLICY["minimum_document_characters"]
                        or _hangul_ratio_ppm(plain) < POLICY["minimum_hangul_letter_ratio_ppm"]):
                    stats["short_or_non_korean_skipped"] += 1
                    page.clear()
                    if max_pages and stats["pages_seen"] >= max_pages:
                        break
                    continue
                raw_hash = hashlib.sha256(_normalize(plain).encode()).hexdigest()
                if not deduper.begin_document(raw_hash):
                    stats["exact_documents_removed"] += 1
                    page.clear()
                    if max_pages and stats["pages_seen"] >= max_pages:
                        break
                    continue
                cleaned, removed = _clean_document(plain, deduper)
                token_count = len(tokenizer.encode(cleaned, add_special_tokens=False).ids) if cleaned else 0
                if (len(cleaned) < POLICY["minimum_document_characters"]
                        or token_count < POLICY["minimum_document_tokens"]
                        or _hangul_ratio_ppm(cleaned) < POLICY["minimum_hangul_letter_ratio_ppm"]):
                    deduper.reject_document()
                    stats["clean_documents_removed"] += 1
                    page.clear()
                    if max_pages and stats["pages_seen"] >= max_pages:
                        break
                    continue
                deduper.accept_document()
                for key, value in removed.items():
                    stats[key] += value
                document_sha256 = hashlib.sha256(cleaned.encode()).hexdigest()
                page_url = f"https://ko.wikipedia.org/?curid={page_id}"
                sample_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{page_url}\0{revision_id}\0{document_sha256}"))
                provenance = {
                    "attribution": {
                        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                        "modified": True,
                        "revision_url": f"https://ko.wikipedia.org/w/index.php?oldid={revision_id}",
                        "title": title,
                    },
                    "document_sha256": document_sha256,
                    "dump_date": dump_date,
                    "dump_sha1": expected_sha1,
                    "dump_sha256": dump_sha256,
                    "license": "CC-BY-SA-4.0",
                    "policy_sha256": POLICY_SHA256,
                    "quality_gates": {
                        "boilerplate": "passed",
                        "document_dedup": "passed",
                        "encoding": "UTF-8",
                        "language": "ko",
                        "pii": "passed",
                        "sentence_near_dedup": "passed",
                    },
                    "source_page_id": int(page_id),
                    "source_page_title": title,
                    "source_page_url": page_url,
                    "source_revision_id": int(revision_id),
                    "source_revision_timestamp": timestamp,
                    "token_count": token_count,
                    "tokenizer_id": tokenizer_id,
                    "tokenizer_sha256": tokenizer_sha256,
                }
                row = {
                    "coverage_tags": ["korean_foundation", "wikipedia", "licensed"],
                    "provenance": provenance,
                    "sample_id": sample_id,
                    "text": cleaned,
                }
                output.write((_canonical(row) + "\n").encode())
                stats["documents_accepted"] += 1
                stats["tokens_accepted"] += token_count
                page.clear()
                if stats["documents_accepted"] % 1000 == 0:
                    deduper.connection.commit()
                if max_pages and stats["pages_seen"] >= max_pages:
                    break
            output.flush()
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        bundle_sha256 = _hash_file(temporary)
        manifest = {
            "bundle": output_path.name,
            "bundle_sha256": bundle_sha256,
            "dump_date": dump_date,
            "dump_sha1": expected_sha1,
            "dump_sha256": dump_sha256,
            "format": "miku-wikimedia-text-bundle-v1",
            "policy": POLICY,
            "policy_sha256": POLICY_SHA256,
            "stats": stats,
            "tokenizer_id": tokenizer_id,
            "tokenizer_sha256": tokenizer_sha256,
        }
        os.replace(temporary, output_path)
        manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path)
        return manifest
    finally:
        deduper.close()
        temporary.unlink(missing_ok=True)
        dedup_path.unlink(missing_ok=True)


def import_text_bundle(
    paths: FoundryPaths,
    registry: Registry,
    manifest_path: Path,
    source_id: str,
    *,
    actor: str,
    dry_run: bool = False,
) -> dict[str, object]:
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("format") != "miku-wikimedia-text-bundle-v1"
            or manifest.get("policy") != POLICY or manifest.get("policy_sha256") != POLICY_SHA256):
        raise ValueError("unsupported or altered Wikimedia text policy")
    bundle_name = manifest.get("bundle")
    if not isinstance(bundle_name, str) or Path(bundle_name).name != bundle_name:
        raise ValueError("bundle must be adjacent to its manifest")
    bundle = manifest_path.parent / bundle_name
    if _hash_file(bundle) != manifest.get("bundle_sha256"):
        raise ValueError("Wikimedia text bundle SHA-256 mismatch")
    expected_count = manifest["stats"]["documents_accepted"]
    expected_tokens = manifest["stats"]["tokens_accepted"]
    with registry.connect() as connection:
        registry.assert_exportable(connection, source_id)
        source = connection.execute("SELECT derivative_family FROM sources WHERE source_id=?", (source_id,)).fetchone()
        bindings = {(row["sha256"], row["role"]) for row in connection.execute(
            "SELECT sha256,role FROM source_objects WHERE source_id=?", (source_id,)
        )}
        if ((manifest.get("dump_sha256"), "text:raw_dump") not in bindings
                or (manifest.get("tokenizer_sha256"), "text:tokenizer") not in bindings):
            raise PermissionError("source lacks its exact raw dump or tokenizer object")
        split = connection.execute(
            "SELECT split,frozen FROM split_assignments WHERE group_id=? AND policy_version='source-split-v1'",
            (source["derivative_family"],),
        ).fetchone()
        if not split or split["split"] != "train" or not split["frozen"]:
            raise PermissionError("Wikimedia derivative family requires a frozen train split")
        existing = connection.execute("SELECT count(*) FROM text_samples WHERE source_id=?", (source_id,)).fetchone()[0]
        binding = connection.execute(
            "SELECT 1 FROM source_objects WHERE source_id=? AND sha256=? AND role='text:cleaned_bundle'",
            (source_id, manifest["bundle_sha256"]),
        ).fetchone()
        if existing:
            if existing == expected_count and binding:
                return {"count": existing, "idempotent": True, "tokens": expected_tokens}
            raise RuntimeError("source already has a different text import")
    created_at = registry.now()
    evidence = _canonical({
        "actor_type": "evaluator",
        "batch_size": 1,
        "media_reviewed_ms": 0,
        "policy_sha256": POLICY_SHA256,
        "read_complete": False,
    })
    tokenizer = Tokenizer.from_file(str(paths.object_path(manifest["tokenizer_sha256"])))

    def records(*, verify_tokens: bool):
        seen: set[str] = set()
        with gzip.open(bundle, "rt", encoding="utf-8") as stream:
            for line in stream:
                value = json.loads(line)
                sample_id, text, provenance = value["sample_id"], value["text"], value["provenance"]
                if (sample_id in seen or not isinstance(text, str) or not text
                        or value.get("coverage_tags") != ["korean_foundation", "wikipedia", "licensed"]
                        or provenance.get("policy_sha256") != POLICY_SHA256
                        or provenance.get("quality_gates") != {
                            "boilerplate": "passed", "document_dedup": "passed", "encoding": "UTF-8",
                            "language": "ko", "pii": "passed", "sentence_near_dedup": "passed",
                        } or not isinstance(provenance.get("token_count"), int)
                        or provenance["token_count"] < POLICY["minimum_document_tokens"]
                        or provenance.get("dump_sha256") != manifest.get("dump_sha256")
                        or provenance.get("tokenizer_sha256") != manifest.get("tokenizer_sha256")
                        or provenance.get("document_sha256") != hashlib.sha256(text.encode()).hexdigest()
                        or PII_RE.search(text)
                        or (verify_tokens and len(tokenizer.encode(text, add_special_tokens=False).ids)
                            != provenance["token_count"])):
                    raise ValueError("invalid or duplicate Wikimedia text row")
                seen.add(sample_id)
                review_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"miku-review\0{sample_id}\0{POLICY_SHA256}"))
                text_row = (sample_id, source_id, "korean_foundation", "", "", text, "ko-KR",
                            _canonical(value["coverage_tags"]), _canonical(provenance), "accepted")
                assert_corpus_row_eligible("text", {"provenance_json": text_row[8]})
                yield (
                    text_row,
                    (review_id, "text", sample_id, 1, POLICY["id"], None, "accept",
                     "deterministic source, rights, quality and dedup gates passed", created_at),
                    (review_id, "evaluator", 0, 0, 1, evidence, created_at),
                    provenance["token_count"],
                )

    actual_count = actual_tokens = 0
    for _, _, _, token_count in records(verify_tokens=True):
        actual_count += 1
        actual_tokens += token_count
    if actual_count != expected_count or actual_tokens != expected_tokens:
        raise ValueError("Wikimedia text bundle totals differ from its manifest")
    if dry_run:
        return {"count": actual_count, "idempotent": False, "tokens": actual_tokens, "dry_run": True}
    bundle_sha256 = ObjectStore(paths, registry).ingest(
        bundle, source_id, role="text:cleaned_bundle", media_type="application/gzip"
    )
    with registry.transaction() as connection:
        registry.assert_exportable(connection, source_id)
        if connection.execute("SELECT count(*) FROM text_samples WHERE source_id=?", (source_id,)).fetchone()[0]:
            raise RuntimeError("source acquired text rows during import")
        batch = []
        for record in records(verify_tokens=False):
            batch.append(record)
            if len(batch) == 1000:
                connection.executemany("INSERT INTO text_samples VALUES (?,?,?,?,?,?,?,?,?,?)", [item[0] for item in batch])
                connection.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", [item[1] for item in batch])
                connection.executemany("INSERT INTO review_evidence VALUES (?,?,?,?,?,?,?)", [item[2] for item in batch])
                batch.clear()
        if batch:
            connection.executemany("INSERT INTO text_samples VALUES (?,?,?,?,?,?,?,?,?,?)", [item[0] for item in batch])
            connection.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", [item[1] for item in batch])
            connection.executemany("INSERT INTO review_evidence VALUES (?,?,?,?,?,?,?)", [item[2] for item in batch])
        registry.audit(connection, "text_bundle.training_promoted", actor, "source", source_id,
                       {"bundle_sha256": bundle_sha256, "count": actual_count, "tokens": actual_tokens,
                        "policy_sha256": POLICY_SHA256})
    return {"bundle_sha256": bundle_sha256, "count": actual_count, "idempotent": False,
            "tokens": actual_tokens}
