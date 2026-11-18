"""Persistent dashboard server -- always-on static server for web/ so localhost stays reachable.

A plain ``python -m http.server`` dies when the terminal closes (the "can't reach localhost" error).
This is a threaded, no-cache static server bound to a fixed port, meant to run as a background /
scheduled task so the dashboards (index/research/factory + the *.json the JS fetches) are available
24/7 and always show fresh data. Read-only; serves the web/ directory only. A request never runs anything: the page's data is
rebuilt on the box's own clock (MT5-DeskState), not by whoever asks.

    python scripts/serve_dashboard.py --port 8080
"""

from __future__ import annotations

import argparse
import hmac
import os
import secrets
import socket
import subprocess
import sys
from contextlib import suppress
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from typing import BinaryIO
from urllib.parse import parse_qs, unquote, urlsplit

_WEB = Path(__file__).resolve().parent.parent / "web"
#: The dashboard shows live equity, P&L and open positions. By the principal's 2026-11-18 decision
#: the box serves it with --no-auth on its fixed address (read-only, allowlisted files only); the
#: token below applies only when the server is started without --no-auth. Generated once, 0600, never printed by any tool (CLAUDE.md:
#: data/secrets/** never leaves the box) -- read it on the box when you need to enrol a device.
_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "secrets" / "dashboard_token.txt"


def _token() -> str:
    """Read the shared token, minting one on first run. Never logged, never printed."""
    try:
        existing = _TOKEN_FILE.read_text("utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    fresh = secrets.token_urlsafe(32)
    _TOKEN_FILE.write_text(fresh, "utf-8")
    # chmod is a no-op on some Windows volumes and must never abort the mint.
    with suppress(OSError):
        os.chmod(_TOKEN_FILE, 0o600)
    return fresh


_LOGIN_PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>QUANT DESK</title><style>
html,body{height:100%;margin:0;background:#030309;color:#ecebf5;font:15px/1.5 ui-sans-serif,system-ui;
 display:grid;place-items:center}
form{border:1px solid rgba(140,120,255,.16);border-radius:20px;padding:30px 28px;background:rgba(13,13,22,.6);
 backdrop-filter:blur(14px);box-shadow:0 20px 60px #000a;text-align:center;min-width:280px}
b{letter-spacing:.34em;font-size:14px;display:block;margin-bottom:4px}i{color:#a78bfa;font-style:normal}
p{color:#7b7f96;font-size:11px;letter-spacing:.14em;text-transform:uppercase;margin:6px 0 20px}
input{width:100%;padding:12px 14px;border-radius:11px;border:1px solid rgba(140,120,255,.22);
 background:#08080f;color:#ecebf5;font:13px ui-monospace,monospace;outline:0}
input:focus{border-color:#a78bfa;box-shadow:0 0 0 3px rgba(167,139,250,.15)}
button{margin-top:12px;width:100%;padding:12px;border-radius:11px;border:0;cursor:pointer;font-weight:700;
 letter-spacing:.1em;background:linear-gradient(100deg,#a78bfa,#00ff9c);color:#05060a}
</style><form method=GET action="/desk.html"><b>QUANT<i>DESK</i></b><p>access key required</p>
<input name=k type=password autocomplete=current-password autofocus placeholder="paste key">
<button>Unlock</button></form>"""


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


# ONLY THESE FILES ARE SERVED (Audit HOLD 2026-11-18). web/ on the box holds organ files that have
# never been published; with no token, "everything under web/" is a leak, so the surface is an
# allowlist: the pages and the two data files they fetch. Anything else, and every directory
# listing, is a 404.
PUBLIC_FILES = frozenset(
    {
        "index.html",
        "desk.html",
        "desk_pro.html",
        "research.html",
        "dashboard.html",
        "desk_state.json",
        "equity_history.jsonl",
    }
)


def _public_name(raw_path: str) -> str | None:
    """The allowlisted file name a request path maps to, or None. Never touches the disk."""
    path = unquote(urlsplit(raw_path).path)
    name = path.lstrip("/")
    return name if name in PUBLIC_FILES else None


class _Handler(SimpleHTTPRequestHandler):
    token = ""

    def send_head(self) -> BinaryIO | None:
        if unquote(urlsplit(self.path).path) == "/":
            # The bare address opens the page: a redirect to an allowlisted name, nothing read.
            self.send_response(302)
            self.send_header("Location", "/desk.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        name = _public_name(self.path)
        if name is None:
            self.send_error(404, "Not found")
            return None
        self.path = "/" + name
        return super().send_head()

    def list_directory(self, path: str | os.PathLike[str]) -> BinaryIO | None:  # type: ignore[override]
        self.send_error(404, "Not found")
        return None

    require_token = False

    def _authorised(self) -> bool:
        """Loopback is trusted UNLESS --require-token; everything else needs the token.

        THE HOLE THIS CLOSES. A Cloudflare tunnel connects to its origin over 127.0.0.1, so every
        request from the public internet arrives here with a LOOPBACK client address. Trusting
        loopback would have published live equity, P&L and open positions to anyone who knew the
        hostname -- with the token bypassed for exactly the traffic it exists to protect. Any
        deployment reachable from outside MUST pass --require-token, which drops the exemption.

        Three carriers because three devices: a header for scripts, a query string so a phone can
        be enrolled from a single pasted link, and a cookie so it stays enrolled afterwards.
        Compared with hmac.compare_digest -- a token check that leaks timing is not a check.
        """
        if not self.token:
            return True  # no token configured -> loopback-only deployments
        # Loopback is the whole 127.0.0.0/8 block plus ::1 -- not just the one literal. A
        # hardcoded ["127.0.0.1"] both misses 127.0.1.1 (what this box's hostname resolves to)
        # and reads as stricter than it is.
        if not self.require_token:
            try:
                if ip_address(self.client_address[0]).is_loopback:
                    return True
            except (ValueError, IndexError):
                pass
        supplied = ""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            supplied = auth[7:].strip()
        if not supplied:
            q = parse_qs(urlsplit(self.path).query)
            supplied = (q.get("k") or [""])[0]
        if not supplied:
            for part in (self.headers.get("Cookie") or "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == "dk":
                    supplied = value
                    break
        return bool(supplied) and hmac.compare_digest(supplied, self.token)

    def do_GET(self) -> None:
        if not self._authorised():
            body = _LOGIN_PAGE.encode("utf-8")
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # A device that authenticated by link keeps its enrolment in a cookie, so the phone is
        # not re-pasting a 43-character key on every glance.
        q = parse_qs(urlsplit(self.path).query)
        if (q.get("k") or [""])[0] and self.token:
            self._set_cookie = True
        super().do_GET()

    def end_headers(self) -> None:  # always serve fresh JSON, never stale cache
        self.send_header("Cache-Control", "no-store, max-age=0")
        # NOT "*" any more: with a token in play, a wildcard CORS header invites any page the
        # browser visits to read this desk's equity through an authenticated cookie.
        self.send_header("Access-Control-Allow-Origin", "null")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # The page is served WITHOUT a key by principal decision (2026-08-26). The tunnel
        # hostname is random and unguessable, which is the only protection left, so at minimum
        # keep crawlers from turning that obscurity into a search result.
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        if getattr(self, "_set_cookie", False):
            self.send_header(
                "Set-Cookie", f"dk={self.token}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Lax"
            )
            self._set_cookie = False
        super().end_headers()

    def log_message(self, *args: object) -> None:  # quiet
        return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0")  # noqa: S104 -- deliberate LAN bind; the TOKEN is the control, the firewall is the second one
    ap.add_argument(
        "--no-auth", action="store_true", help="serve without a token (loopback-only deployments)"
    )
    ap.add_argument(
        "--require-token",
        action="store_true",
        help="require the token even from loopback -- MANDATORY behind a tunnel or "
        "proxy, whose requests reach this origin as 127.0.0.1",
    )
    args = ap.parse_args()
    _Handler.token = "" if args.no_auth else _token()
    _Handler.require_token = bool(args.require_token) and not args.no_auth
    _WEB.mkdir(parents=True, exist_ok=True)
    # Build once before serving so localhost never opens on a missing/stale state file. The daily
    # MT5 cycle refreshes it thereafter; this best-effort call cannot mutate trading state.
    subprocess.run(
        [sys.executable, str(_WEB.parent / "scripts" / "build_zentech_state.py")],
        cwd=str(_WEB.parent),
        check=False,
    )
    handler = partial(_Handler, directory=str(_WEB))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"dashboard serving {_WEB} on {args.host}:{args.port}\n"
        f"  local   : http://127.0.0.1:{args.port}/desk.html\n"
        f"  network : http://{_lan_ip()}:{args.port}/desk.html\n"
        f"  auth    : {'DISABLED (--no-auth)' if args.no_auth else 'token required off-loopback; key in ' + str(_TOKEN_FILE)}"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
