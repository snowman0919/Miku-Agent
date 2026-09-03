from __future__ import annotations

import json
import re
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from .config import FoundryPaths
from .registry import Registry
from .review import ReviewConflict, add_review, gold_requires_double_review
from .review_app import html


ENTITY_TABLES = {
    "audio": ("audio_samples", "sample_id"),
    "persona": ("persona_samples", "sample_id"),
}


def _loads(value: str | None) -> object | None:
    return json.loads(value) if value else None


def _review_queue(registry: Registry, entity_type: str) -> list[dict[str, object]]:
    if entity_type not in ENTITY_TABLES:
        raise ValueError("unsupported queue entity type")
    table, id_column = ENTITY_TABLES[entity_type]
    label = "a.raw_text" if entity_type == "audio" else "p.prompt"
    alias = "a" if entity_type == "audio" else "p"
    with registry.connect() as connection:
        rows = connection.execute(
            f"""SELECT {alias}.{id_column} entity_id,{label} title,{alias}.quality_tier,
                       {alias}.training_status,
                       COALESCE((SELECT revision FROM reviews r WHERE r.entity_type=?
                                 AND r.entity_id={alias}.{id_column} ORDER BY revision DESC LIMIT 1),0) revision,
                       (SELECT decision FROM reviews r WHERE r.entity_type=?
                        AND r.entity_id={alias}.{id_column} ORDER BY revision DESC LIMIT 1) latest_decision
                FROM {table} {alias}
                ORDER BY CASE WHEN latest_decision IS NULL THEN 0 ELSE 1 END,{alias}.{id_column} LIMIT 200""",
            (entity_type, entity_type),
        )
        return [dict(row) | {"entity_type": entity_type} for row in rows]


def _review_history(connection: sqlite3.Connection, entity_type: str, entity_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        """SELECT r.*,e.actor_type,e.media_reviewed_ms,e.read_complete,e.batch_size,e.evidence_json
           FROM reviews r LEFT JOIN review_evidence e USING(review_id)
           WHERE r.entity_type=? AND r.entity_id=? ORDER BY r.revision""",
        (entity_type, entity_id),
    )
    result = []
    for row in rows:
        value = dict(row)
        value["evidence"] = _loads(value.pop("evidence_json"))
        result.append(value)
    return result


def _technical_evidence(
    paths: FoundryPaths, connection: sqlite3.Connection, object_sha256: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = connection.execute(
        """SELECT DISTINCT so.sha256,so.role,so.original_name,o.media_type,o.size_bytes
           FROM lineage_edges l JOIN source_objects so ON so.sha256=l.child_sha256
           JOIN objects o ON o.sha256=so.sha256
           WHERE l.parent_sha256=? ORDER BY so.role,so.sha256""",
        (object_sha256,),
    )
    evidence, derived = [], []
    for row in rows:
        value = dict(row)
        derived.append(value)
        if row["role"] != "worker:technical_scores" or row["size_bytes"] > 1024 * 1024:
            continue
        try:
            payload = json.loads(paths.object_path(row["sha256"]).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        evidence.append({"sha256": row["sha256"], "payload": payload})
    return evidence, derived


def _review_item(
    paths: FoundryPaths, registry: Registry, entity_type: str, entity_id: str
) -> dict[str, object]:
    if entity_type not in ENTITY_TABLES:
        raise ValueError("unsupported review entity type")
    table, id_column = ENTITY_TABLES[entity_type]
    with registry.connect() as connection:
        row = connection.execute(f"SELECT * FROM {table} WHERE {id_column}=?", (entity_id,)).fetchone()
        if row is None:
            raise KeyError(entity_id)
        source = connection.execute("SELECT * FROM sources WHERE source_id=?", (row["source_id"],)).fetchone()
        rights = registry.current_rights(connection, row["source_id"])
        reviews = _review_history(connection, entity_type, entity_id)
        value = dict(row)
        value.update({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "title": row["raw_text"] if entity_type == "audio" else row["prompt"],
            "source": dict(source),
            "rights": dict(rights) if rights else None,
            "reviews": reviews,
            "revision": reviews[-1]["revision"] if reviews else 0,
            "double_review_required": str(row["quality_tier"]).lower() == "gold"
            and gold_requires_double_review(entity_id),
        })
        if entity_type == "audio":
            evidence, derived = _technical_evidence(paths, connection, row["object_sha256"])
            metrics = connection.execute(
                "SELECT * FROM audio_metrics WHERE object_sha256=?", (row["parent_object_sha256"],)
            ).fetchone()
            value.update({
                "playback_sha256": row["clip_object_sha256"] or row["object_sha256"],
                "metrics": dict(metrics) if metrics else None,
                "technical_evidence": evidence,
                "derived_objects": derived,
            })
        else:
            value["dimensions"] = _loads(row["dimensions_json"])
            value["provenance"] = _loads(row["provenance_json"])
        return value


def create_server(paths: FoundryPaths, registry: Registry, port: int = 8765) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(18)
    page = html(token, nonce)

    class Handler(BaseHTTPRequestHandler):
        def _headers(self, content_type: str, length: int, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", f"default-src 'self'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; media-src 'self'; connect-src 'self'")
            self.end_headers()

        def _json(self, status: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
            self._headers("application/json; charset=utf-8", len(body), status)
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if secrets.compare_digest(self.headers.get("X-Review-Token", ""), token):
                return True
            self._json(403, {"error": "review token required"})
            return False

        def _object(self, digest: str) -> None:
            try:
                object_path = paths.object_path(digest)
            except ValueError:
                self._json(400, {"error": "invalid object hash"})
                return
            if not object_path.is_file():
                self._json(404, {"error": "not found"})
                return
            with registry.connect() as connection:
                row = connection.execute("SELECT media_type,size_bytes FROM objects WHERE sha256=?", (digest,)).fetchone()
            if row is None:
                self._json(404, {"error": "unregistered object"})
                return
            start, end, status = 0, row["size_bytes"] - 1, 200
            requested = self.headers.get("Range")
            if requested:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                if not match or (not match.group(1) and not match.group(2)):
                    self._json(416, {"error": "invalid range"})
                    return
                if match.group(1):
                    start = int(match.group(1))
                    end = int(match.group(2)) if match.group(2) else end
                else:
                    start = max(0, row["size_bytes"] - int(match.group(2)))
                end = min(end, row["size_bytes"] - 1)
                if start > end:
                    self._json(416, {"error": "range outside object"})
                    return
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", row["media_type"] or "application/octet-stream")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{row['size_bytes']}")
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with object_path.open("rb") as source:
                source.seek(start)
                self.wfile.write(source.read(length))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path == "/":
                self._headers("text/html; charset=utf-8", len(page))
                self.wfile.write(page)
                return
            if path.startswith("/objects/"):
                self._object(path.removeprefix("/objects/"))
                return
            if not self._authorized():
                return
            try:
                if path == "/api/review-queue":
                    entity_type = parse_qs(parsed.query).get("entity_type", ["audio"])[0]
                    self._json(200, _review_queue(registry, entity_type))
                    return
                match = re.fullmatch(r"/api/review-items/(audio|persona)/([^/]+)", path)
                if match:
                    self._json(200, _review_item(paths, registry, match.group(1), match.group(2)))
                    return
                self._json(404, {"error": "not found"})
            except KeyError:
                self._json(404, {"error": "review item not found"})
            except (ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            if not self._authorized():
                return
            if urlparse(self.path).path != "/api/reviews":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 131072:
                    raise ValueError("invalid content length")
                payload = json.loads(self.rfile.read(length))
                review_id = add_review(
                    registry, payload["entity_type"], payload["entity_id"], payload["decision"],
                    payload["reviewer"], payload["reason"], expected_revision=payload["expected_revision"],
                    evidence=payload.get("evidence"), edits=payload.get("edits"),
                )
                self._json(201, {"review_id": review_id})
            except ReviewConflict as exc:
                self._json(409, {"error": str(exc)})
            except PermissionError as exc:
                self._json(403, {"error": str(exc)})
            except KeyError as exc:
                self._json(404, {"error": f"missing or unknown field: {exc}"})
            except (json.JSONDecodeError, sqlite3.IntegrityError, ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.review_token = token  # type: ignore[attr-defined]
    return server


def serve(paths: FoundryPaths, registry: Registry, port: int = 8765) -> None:
    server = create_server(paths, registry, port)
    print(f"review UI listening on http://127.0.0.1:{server.server_port}")
    server.serve_forever()
