from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import FoundryPaths
from .registry import Registry
from .review import ReviewConflict, add_review


def serve(paths: FoundryPaths, registry: Registry, port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/review-queue":
                with registry.connect() as connection:
                    rows = [dict(row) for row in connection.execute(
                        "SELECT sample_id,source_id,object_sha256,raw_text,spoken_text,normalized_text,quality_tier,training_status FROM audio_samples ORDER BY sample_id LIMIT 100")]
                self._json(200, rows)
                return
            if path.startswith("/objects/"):
                digest = path.removeprefix("/objects/")
                try:
                    object_path = paths.object_path(digest)
                except ValueError:
                    self._json(400, {"error": "invalid object hash"})
                    return
                if not object_path.is_file():
                    self._json(404, {"error": "not found"})
                    return
                body = object_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/":
                body = b"<!doctype html><meta charset=utf-8><title>Miku Dataset Review</title><h1>Local Dataset Review</h1><p>Use /api/review-queue and POST /api/reviews.</p>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/reviews":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                self._json(400, {"error": "invalid content length"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
                review_id = add_review(registry, payload["entity_type"], payload["entity_id"], payload["decision"],
                                       payload["reviewer"], payload["reason"],
                                       expected_revision=int(payload["expected_revision"]))
            except ReviewConflict as exc:
                self._json(409, {"error": str(exc)})
                return
            except (KeyError, ValueError, TypeError) as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(201, {"review_id": review_id})

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"review UI listening on http://127.0.0.1:{port}")
    server.serve_forever()
