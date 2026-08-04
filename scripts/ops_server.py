"""Live ops dashboard for the autonomous daemon -- stdlib HTTP only (no FastAPI/Node needed).

Serves a neon page (web/ops.html) + JSON that read the daemon's system-of-record in real time, so
you can watch the queue drain and workers process campaigns live. Read-only.

    python scripts/ops_server.py --port 8090   ->   http://localhost:8090
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from api import adapters

_PAGE = (Path(__file__).resolve().parent.parent / "web" / "ops.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            if self.path.startswith("/api/orchestration"):
                self._send(_json(adapters.orchestration().model_dump()), "application/json")
            elif self.path.startswith("/api/overview"):
                self._send(_json(adapters.overview().model_dump()), "application/json")
            else:
                self._send(_PAGE, "text/html; charset=utf-8")
        except Exception as exc:  # never crash the ops server
            self._send(_json({"error": str(exc)}), "application/json")

    def log_message(self, *_args: Any) -> None:
        return


def _json(obj: Any) -> bytes:
    return json.dumps(obj, default=str).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    server = HTTPServer(("0.0.0.0", args.port), Handler)  # noqa: S104 -- deliberate LAN bind; read-only, and the HOST FIREWALL is the control (gap register: exposure surface)
    print(f"ops dashboard live -> http://localhost:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
