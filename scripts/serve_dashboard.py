"""Persistent dashboard server -- always-on static server for web/ so localhost stays reachable.

A plain ``python -m http.server`` dies when the terminal closes (the "can't reach localhost" error).
This is a threaded, no-cache static server bound to a fixed port, meant to run as a background /
scheduled task so the dashboards (index/research/factory + the *.json the JS fetches) are available
24/7 and always show fresh data. Read-only; serves the web/ directory only.

    python scripts/serve_dashboard.py --port 8080
"""

from __future__ import annotations

import argparse
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_WEB = Path(__file__).resolve().parent.parent / "web"


def _lan_ip() -> str:
    """Best-effort LAN IP so the phone URL can be printed (no traffic actually sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return str(ip)
    except OSError:
        return "127.0.0.1"


class _Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:                      # always serve fresh JSON, never stale cache
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *args: object) -> None:      # quiet
        return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")  # noqa: S104 -- deliberate LAN bind; read-only, and the HOST FIREWALL is the control (gap register: exposure surface)           # bind LAN so the phone can reach it
    args = ap.parse_args()
    _WEB.mkdir(parents=True, exist_ok=True)
    handler = partial(_Handler, directory=str(_WEB))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"dashboard serving {_WEB} on {args.host}:{args.port}\n"
          f"  this PC : http://127.0.0.1:{args.port}/\n"
          f"  phone   : http://{_lan_ip()}:{args.port}/   (same Wi-Fi)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
