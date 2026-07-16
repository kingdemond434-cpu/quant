"""Public tunnel: expose the local dashboard at a free https://<random>.trycloudflare.com URL.

This makes the link work for ANYONE you send it to (not just devices on your Wi-Fi). Runs the
portable cloudflared (no account, no admin), parses the assigned URL, and writes it to
web/tunnel.json so the dashboard header shows the current public link. ONLY read-only performance
data is served (web/ has no API keys/secrets). A heartbeat thread keeps liveness fresh so the
watchdog won't needlessly restart it (a restart changes the random URL). To stop sharing publicly:
kill cloudflared. The quick-tunnel URL changes on restart -- always read the current one from
web/tunnel.json or the dashboard.

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
_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _write(url: str | None, status: str) -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "url": url, "status": status}, indent=2), "utf-8")


def _beat(proc: subprocess.Popen[str]) -> None:
    _HB.parent.mkdir(parents=True, exist_ok=True)
    while proc.poll() is None:
        _HB.write_text(str(time.time()), "utf-8")
        time.sleep(15)


def _run_once() -> None:
    proc = subprocess.Popen(
        [str(_CF), "tunnel", "--url", "http://localhost:8080", "--no-autoupdate"],
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
