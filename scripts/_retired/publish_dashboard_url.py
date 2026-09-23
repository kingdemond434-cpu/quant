"""Publish the current dashboard tunnel URL + page the principal when it changes.

The cloudflared quick tunnel (no account, free) prints a https://*.trycloudflare.com URL
that only changes when the tunnel restarts (VPS reboot / crash). This reads it from the
cloudflared logfile, writes web/dashboard_url.json for the dashboard/digest, and pushes a
one-line ntfy notification ONLY when the URL differs from last time -- so the principal
always has the live link on their phone with zero maintenance and no Cloudflare login.
Runs in the refresh cycle. Stable custom domain (dash.quanttt.xyz) supersedes this once set.

    python scripts/publish_dashboard_url.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_LOG = Path("data/cloudflared.log")
_OUT = Path("web/dashboard_url.json")
_NTFY = Path("data/secrets/ntfy.json")
_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _current_url() -> str | None:
    try:
        text = _LOG.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    hits = _URL_RE.findall(text)
    return hits[-1] if hits else None            # last = most recent tunnel


def _page(url: str) -> None:
    try:
        topic = json.loads(_NTFY.read_text("utf-8")).get("topic")
        if not topic:
            return
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=f"Dashboard URL changed -> {url}".encode(),
            headers={"Title": "Quant desk dashboard", "Tags": "bar_chart"},
            method="POST")
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass                                     # notification is best-effort, never blocks


def main() -> None:
    url = _current_url()
    if not url:
        print("dashboard-url: no tunnel URL in log yet")
        return
    prev = None
    if _OUT.exists():
        with __import__("contextlib").suppress(Exception):
            prev = json.loads(_OUT.read_text("utf-8")).get("url")
    _OUT.write_text(json.dumps(
        {"url": url, "updated": datetime.now(tz=UTC).isoformat()}, indent=2), "utf-8")
    if url != prev:
        _page(url)
        print(f"dashboard-url: CHANGED -> {url} (paged)")
    else:
        print(f"dashboard-url: unchanged ({url})")


if __name__ == "__main__":
    main()
