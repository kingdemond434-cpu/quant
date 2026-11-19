"""Run ngrok for the dashboard (:8080) + publish the URL. IDEMPOTENT single session, no thrash.

ngrok FREE allows only ONE simultaneous session, so this never runs two agents:
  * if a tunnel is ALREADY serving (local 4040 API returns a url), it does NOT launch a second --
    it just refreshes the heartbeat and returns (a peer agent is healthy);
  * otherwise it kills any stray ngrok.exe (clean the session), launches exactly ONE agent, and
    holds the heartbeat while it lives. It does NOT loop-relaunch internally (that was the bug that
    piled up agents and thrashed the session -> ERR_NGROK_3200). When ngrok dies, this exits and the
    watchdog respawns it (gated on heartbeat freshness), so there is always exactly one agent.

With a static/persistent account domain the URL never rotates.

    python scripts/run_ngrok.py
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_NGROK = Path("tools/ngrok.exe")
_SECRETS = Path("data/secrets/ngrok.json")
_TUN = Path("web/tunnel.json")
_HB = Path("data/tunnel_heartbeat")
_HB_TICK = 30


def _public_url() -> str | None:
    try:
        raw = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5).read()
        for t in json.loads(raw).get("tunnels", []):
            u = t.get("public_url", "")
            if u.startswith("https"):
                return str(u)
    except Exception:
        return None
    return None


def _kill_stray_ngrok() -> None:
    """Kill every ngrok.exe -- free tier allows ONE session; strays thrash it offline."""
    with contextlib.suppress(Exception):
        subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], capture_output=True, check=False)
    time.sleep(2)


def _beat() -> None:
    _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")


def _publish(url: str) -> None:
    _TUN.write_text(json.dumps({"url": url, "updated": datetime.now(tz=UTC).isoformat()}), "utf-8")


def main() -> None:
    # IDEMPOTENT: a healthy tunnel already up -> refresh heartbeat + URL, launch no 2nd agent
    # (covers a directly-started ngrok too -- we just monitor it and take over only if it dies).
    up = _public_url()
    if up:
        _publish(up)
        _beat()
        print(f"tunnel already up ({up}) -- monitoring, no second agent")
        return

    _kill_stray_ngrok()                                    # ensure a single clean session
    creds = json.loads(_SECRETS.read_text("utf-8")) if _SECRETS.exists() else {}
    args = [str(_NGROK), "http", "8080", "--log=stdout"]
    if creds.get("domain"):
        args.append("--url=" + str(creds["domain"]))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(20):                                    # wait up to ~60s for the URL
        _beat()
        time.sleep(3)
        url = _public_url()
        if url:
            _publish(url)
            print(f"ngrok live: {url}")
            break

    while proc.poll() is None:                    # hold heartbeat while alive; NO relaunch
        _beat()
        time.sleep(_HB_TICK)
    print("ngrok exited -- watchdog will respawn")   # exit -> watchdog respawns one agent


if __name__ == "__main__":
    main()
