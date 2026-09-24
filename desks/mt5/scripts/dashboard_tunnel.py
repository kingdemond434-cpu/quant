"""Keep the box's dashboard reachable, and PUBLISH WHERE IT IS.

The trading box already builds a complete `web/desk_state.json` -- graph, attributed_deals,
processes, clocks, 24 blocks against the VPS's 16 -- and serves it on 127.0.0.1:8899, which is
reachable over RDP and nowhere else. The public dashboard at dash.quanttt.xyz is served by a VPS
running a build from before 2026-09-08, so it is missing three of those blocks and 404s on
refresh_status.json. Repairing the VPS needs access this desk does not have; exposing the box's
own dashboard needs one process.

THE PROBLEM THIS SOLVES IS NOT THE TUNNEL, IT IS THE ADDRESS. A cloudflared QUICK tunnel needs no
account, no token and no login -- which is why it can run unattended -- but it is handed a random
`*.trycloudflare.com` hostname that CHANGES ON EVERY RESTART. A tunnel that comes back after a
reboot at an address nobody knows is not a dashboard, it is a dashboard-shaped secret.

So this wrapper starts the tunnel, reads the hostname out of cloudflared's own output, and writes
it where both a person and the desk can find it:

    desks/mt5/reports/DASHBOARD_URL.json    the current URL, when it was claimed, and the target
    web/dashboard_url.txt                   the bare URL, so the dashboard page can link itself

It then supervises: if cloudflared dies the hostname is dead, so the wrapper restarts it and
republishes rather than leaving a stale URL on disk claiming to work.

IT IS NOT AUTHENTICATED AND THAT IS STATED, NOT ASSUMED. Anyone with the link sees equity,
positions and sleeve names. That is the same exposure dash.quanttt.xyz already carries -- it
answers plain HTTP with no credential -- so this adds a second door of the same kind rather than
a new kind of door. If that is not wanted, the honest fix is a named tunnel behind Cloudflare
Access, which needs the principal's Cloudflare login and is a different job.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent

CLOUDFLARED = ROOT / "tools" / "cloudflared.exe"
TARGET = "http://127.0.0.1:8899"
OUT = DESK / "reports" / "DASHBOARD_URL.json"
PLAIN = ROOT / "web" / "dashboard_url.txt"
LOG = DESK / "logs" / "cloudflared.log"

#: cloudflared announces the hostname once, on stderr, within a few seconds of starting.
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

#: How long to wait for that announcement before treating the start as failed. Generous: the
#: binary is 55MB and a cold start on a busy box has been seen to take 20s.
ANNOUNCE_TIMEOUT_S = 90

#: Seconds between liveness checks once it is up.
POLL_S = 30


def _publish(url: str | None, why: str) -> None:
    """Write where the dashboard is, or say plainly that it is nowhere.

    A URL is published ONLY while its tunnel is alive. Leaving the last known good address on
    disk after the process died is worse than publishing nothing: a reader follows it, gets a
    connection error, and cannot tell a dead tunnel from a dead box.
    """
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "url": url,
        "target": TARGET,
        "status": "UP" if url else "DOWN",
        "why": why,
        "authenticated": False,
        "note": ("quick tunnel: no account and no token, so the hostname is RANDOM and changes on "
                 "every restart -- which is why it is published here rather than remembered"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    PLAIN.parent.mkdir(parents=True, exist_ok=True)
    PLAIN.write_text((url or ""), encoding="utf-8")


def _start() -> tuple[subprocess.Popen | None, str | None]:
    if not CLOUDFLARED.exists():
        return None, None
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = LOG.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--url", TARGET],
        stdout=fh, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.time() + ANNOUNCE_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(2)
        if proc.poll() is not None:
            return None, None
        try:
            m = URL_RE.search(LOG.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            m = None
        if m:
            return proc, m.group(0)
    return proc, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="start, publish the URL and exit rather than supervising")
    args = ap.parse_args(argv)

    if not CLOUDFLARED.exists():
        _publish(None, f"cloudflared is not installed at {CLOUDFLARED}")
        print(f"cloudflared missing at {CLOUDFLARED}")
        return 1

    proc, url = _start()
    if url is None:
        _publish(None, "cloudflared started but announced no hostname within "
                       f"{ANNOUNCE_TIMEOUT_S}s -- see {LOG.name}")
        print("no hostname announced")
        return 1
    _publish(url, "tunnel up")
    print(f"dashboard: {url}  ->  {TARGET}")
    if args.once:
        return 0

    try:
        while True:
            time.sleep(POLL_S)
            if proc is None or proc.poll() is not None:
                # THE HOSTNAME DIES WITH THE PROCESS. Restarting gets a NEW one, so the published
                # address must be replaced in the same breath -- and marked DOWN in between, so a
                # reader never follows an address that stopped existing.
                _publish(None, "cloudflared exited; restarting")
                proc, url = _start()
                if url:
                    _publish(url, "tunnel restarted with a new hostname")
                    print(f"dashboard moved: {url}")
                else:
                    _publish(None, "restart failed to announce a hostname")
    except KeyboardInterrupt:
        _publish(None, "supervisor interrupted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
