"""Public tunnel: expose the local dashboard at a free https://<random>.trycloudflare.com URL.

This makes the link work for ANYONE you send it to (not just devices on your Wi-Fi). Runs the
portable cloudflared (no account, no admin), parses the assigned URL, and writes it to
web/tunnel.json, web/dashboard_url.txt and desks/mt5/reports/DASHBOARD_URL.json.

WHAT IS BEHIND THIS TUNNEL IS NOT PUBLIC DATA. The page shows live equity, open positions and
P&L, so the origin must be the ``--require-token`` server on 8080 and never the ungated
``http.server`` on 8899: a tunnel reaches its origin over 127.0.0.1, which is exactly the address
serve_dashboard's loopback exemption used to trust. Pointing a tunnel at an ungated origin
published the live account to anyone holding the hostname (measured 2026-09-24: 16 orphaned
tunnels were doing precisely that, and ``/desk_state.json`` answered 200 with 1.1 MB of it).

A heartbeat thread keeps liveness fresh so the watchdog won't needlessly restart it (a restart
changes the random URL). To stop sharing publicly: kill cloudflared. The quick-tunnel URL changes
on restart -- always read the current one from the artifacts above, never from memory.

    python scripts/run_tunnel.py
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CF = _ROOT / "tools" / "cloudflared.exe"
_OUT = _ROOT / "web" / "tunnel.json"
_HB = _ROOT / "data" / "tunnel_heartbeat"
#: The same address, written where a PERSON and a future session look for it. web/tunnel.json is
#: served from behind the token gate, so it answers "where is the dashboard" only to someone who
#: is already through the door. These two are the out-of-band copies.
_PLAIN = _ROOT / "web" / "dashboard_url.txt"
_REPORT = _ROOT / "desks" / "mt5" / "reports" / "DASHBOARD_URL.json"
_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

#: The origin this tunnel fronts. It is the --require-token server, NOT the ungated
#: `http.server` on 8899 -- see the banner in scripts/serve_dashboard.py.
_TARGET = "http://localhost:8080"


def _write(url: str | None, status: str) -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "url": url, "status": status}, indent=2), "utf-8")
    # A URL is published ONLY while its tunnel is alive: a dead hostname left on disk reads as a
    # working address and a reader cannot tell it from a dead box. The TOKEN is never written
    # here -- only the host -- so these files stay safe to read, quote and commit.
    _PLAIN.write_text(url or "", "utf-8")
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps({
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "url": url,
        "target": _TARGET,
        "status": "UP" if url else "DOWN",
        "why": status,
        "authenticated": True,
        "auth": "token required on every request, loopback included (--require-token)",
        "note": ("quick tunnel: no Cloudflare account, so the hostname is RANDOM and changes "
                 "whenever cloudflared restarts -- which is why it is published here rather "
                 "than remembered. Append ?k=<key from data/secrets/dashboard_token.txt> once "
                 "per device; the server then sets a one-year cookie."),
    }, indent=1), "utf-8")


def _beat(proc: subprocess.Popen[str]) -> None:
    _HB.parent.mkdir(parents=True, exist_ok=True)
    while proc.poll() is None:
        _HB.write_text(str(time.time()), "utf-8")
        time.sleep(15)


def _run_once() -> None:
    proc = subprocess.Popen(
        [str(_CF), "tunnel", "--url", _TARGET, "--no-autoupdate"],
        cwd=str(_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    threading.Thread(target=_beat, args=(proc,), daemon=True).start()
    url: str | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        m = _URL_RE.search(line)
        if m and not url:
            url = m.group(0)
            _write(url, "up")
            print("PUBLIC URL:", url, flush=True)
    proc.wait()


def main() -> None:
    if not _CF.exists():
        raise SystemExit("cloudflared not found at tools/cloudflared.exe")
    while True:                              # self-heal: quick-tunnels drop; relaunch on exit
        _write(None, "starting")
        try:
            _run_once()
        except Exception as e:
            print(f"tunnel error: {e!r}"[:120], flush=True)
        _write(None, "reconnecting")
        time.sleep(5)


if __name__ == "__main__":
    main()
