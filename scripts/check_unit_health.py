"""THE WATCHER OF THE WATCHERS -- failed organs restart themselves, and the dashboard's own
serving chain is watched by something that does not depend on it.

WHY (2026-08-27). quant-gap-wirer -- the repair organ every fence calls -- was OOM-killed at
09:01 and sat in `failed` for hours while fences kept requesting repairs that never came. Sixty
timers, and not one watched whether their SERVICES were alive: the meta-layer was the single
unwatched thing. Likewise the dashboard: the pulse rides web/research_pulse.json THROUGH
quant-desk-web + the cloudflared tunnel, so if either dies, the page that says "everything is
fine" simply stops loading -- self-referential blindness no fence could see.

WHAT IT HEALS (research layer only):
  * any failed quant-* user service -> reset-failed + restart, journaled;
  * the dashboard chain -> local HTTP probe of :8788; on failure restart quant-desk-web, then
    quant-desk-tunnel (order matters: the tunnel points at the web server);
  * a stale .git/index.lock (>10 min, no live git) -> removed, because a dead lock silently
    breaks every fence commit after it.
WHAT IT NEVER TOUCHES: the money path. Deadman, gateway and anything matching the crypto
retirement list are excluded by name -- a failed money-path unit is REPORTED loud and left for
a human, because auto-restarting live-order machinery is how accounts die.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "unit_health.json"

#: Never auto-restarted, whatever state they are in. Reported instead.
NEVER_TOUCH = ("deadman", "gateway", "memecoin", "bybit", "cashcarry", "recorder-bybit")


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, str(exc)


def failed_units() -> list[str]:
    _rc, out = _run(["systemctl", "--user", "list-units", "--type=service",
                     "--state=failed", "--no-legend", "--plain"])
    units = []
    for line in out.splitlines():
        name = line.split()[0] if line.split() else ""
        if name.startswith("quant-") and name.endswith(".service"):
            units.append(name)
    return units


def probe_dashboard() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8788/research_pulse.json",
                                    timeout=10) as r:
            return r.status == 200
    except OSError:
        return False


def clear_stale_git_lock() -> str | None:
    lock = ROOT / ".git" / "index.lock"
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime > 600:
            _rc, out = _run(["pgrep", "-c", "-x", "git"], timeout=10)
            if out.strip() in ("", "0"):
                lock.unlink()
                return "removed stale .git/index.lock (>10m old, no git process)"
    except OSError:
        pass
    return None


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    actions: list[str] = []
    untouchable: list[str] = []

    for unit in failed_units():
        if any(k in unit for k in NEVER_TOUCH):
            untouchable.append(unit)
            print(f"  FAILED-MONEYPATH {unit}: reported, NEVER auto-restarted")
            continue
        _run(["systemctl", "--user", "reset-failed", unit])
        rc, out = _run(["systemctl", "--user", "restart", unit], timeout=120)
        actions.append(f"{'RESTARTED' if rc == 0 else 'RESTART FAILED'} {unit}"
                       + ("" if rc == 0 else f": {out[:120]}"))
        print(f"  {actions[-1]}")

    dash_ok = probe_dashboard()
    if not dash_ok:
        for unit in ("quant-desk-web.service", "quant-desk-tunnel.service"):
            _run(["systemctl", "--user", "restart", unit], timeout=120)
        time.sleep(5)
        dash_ok = probe_dashboard()
        actions.append(f"dashboard chain restarted -> {'UP' if dash_ok else 'STILL DOWN'}")
        print(f"  {actions[-1]}")

    lock_note = clear_stale_git_lock()
    if lock_note:
        actions.append(lock_note)
        print(f"  {lock_note}")

    OUT.write_text(json.dumps({
        "checked_at": now, "dashboard_up": dash_ok,
        "failed_moneypath_units": untouchable, "actions": actions,
    }, indent=1), "utf-8")
    if not actions and dash_ok and not untouchable:
        print(f"unit health: all organs alive, dashboard serving ({now})")
    return 1 if (untouchable or not dash_ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
