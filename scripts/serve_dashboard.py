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
import subprocess
import sys
import threading
import time
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
    _refresh_lock = threading.Lock()
    _last_refresh = 0.0

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/zentech_state.json":
            # The browser polls every 15 seconds. Rebuild from canonical artifacts before each
            # response (coalescing simultaneous tabs) so a polished view can never cache a stale
            # account snapshot and call it live.
            with self._refresh_lock:
                now = time.monotonic()
                if now - self._last_refresh >= 2.0:
                    subprocess.run(
                        [sys.executable, str(_WEB.parent / "scripts" /
                                              "build_zentech_state.py")],
                        cwd=str(_WEB.parent), check=False, timeout=10,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    type(self)._last_refresh = now
        super().do_GET()

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
    # Build once before serving so localhost never opens on a missing/stale state file. The daily
    # MT5 cycle refreshes it thereafter; this best-effort call cannot mutate trading state.
    subprocess.run([sys.executable, str(_WEB.parent / "scripts" / "build_zentech_state.py")],
                   cwd=str(_WEB.parent), check=False)
    handler = partial(_Handler, directory=str(_WEB))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"dashboard serving {_WEB} on {args.host}:{args.port}\n"
          f"  ZENTECH : http://127.0.0.1:{args.port}/zentech.html\n"
          f"  phone   : http://{_lan_ip()}:{args.port}/zentech.html   (same Wi-Fi)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
