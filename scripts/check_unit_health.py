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


def check_clock_skew() -> tuple[str | None, str | None]:
    """Cross-box clock skew corrupts every freshness check SILENTLY -- a desk 10 minutes slow
    makes stale artifacts read fresh and fresh ones stale, on both fences and boundaries.
    Fixer: w32tm /resync on the desk (safe, Administrator); VPS drift is reported only (no
    sudo by design)."""
    rc, out = _run(["ssh", "-o", "ConnectTimeout=20", "contabo-mt5",
                    "powershell -Command \"(Get-Date).ToUniversalTime().ToString('o')\""],
                   timeout=45)
    if rc != 0 or not out.strip():
        return None, "desk unreachable for skew check (UNMEASURED, not zero)"
    try:
        import re as _re
        from datetime import datetime as _dt
        iso = [ln for ln in out.splitlines()
               if _re.match(r"^\d{4}-\d{2}-\d{2}T", ln.strip())]
        if not iso:
            return None, "desk returned no timestamp (banner noise only) -- UNMEASURED"
        desk = _dt.fromisoformat(iso[-1].strip().replace("Z", "+00:00"))
        here = _dt.now(UTC)
        skew = abs((here - desk.astimezone(UTC)).total_seconds())
    except ValueError as exc:
        return None, f"skew unparsable: {exc}"
    if skew <= 30:
        return f"clock skew {skew:.1f}s (ok)", None
    _run(["ssh", "-o", "ConnectTimeout=20", "contabo-mt5",
          "cmd /c w32tm /resync /force"], timeout=60)
    return None, f"clock skew {skew:.1f}s > 30s -- desk resync ordered; verify next pass"


def check_crontab() -> list[str]:
    """The crontab is a single point holding six fences; a wipe would kill them all silently.
    Required lines live in ops/crontab.required; missing ones are MERGED back (never a wholesale
    replace -- additions others made survive)."""
    actions: list[str] = []
    req_file = ROOT / "ops" / "crontab.required"
    try:
        required = [ln.strip() for ln in req_file.read_text("utf-8").splitlines()
                    if ln.strip() and not ln.startswith("#")]
    except OSError:
        return ["crontab.required missing -- guard cannot verify"]
    _rc, current = _run(["crontab", "-l"], timeout=15)
    # match on the command tail, not the schedule -- retiming a fence is legitimate
    have = {ln.split("&&")[-1].strip() for ln in current.splitlines() if ln.strip()}
    missing = [ln for ln in required if ln.split("&&")[-1].strip() not in have]
    if missing:
        merged = current.rstrip() + "\n" + "\n".join(missing) + "\n"
        proc = subprocess.run(["crontab", "-"], input=merged, capture_output=True,
                              text=True, timeout=15, check=False)
        actions.append(f"CRONTAB: restored {len(missing)} missing fence line(s)"
                       + ("" if proc.returncode == 0 else " -- RESTORE FAILED"))
    return actions


def check_lingering() -> str | None:
    _rc, out = _run(["loginctl", "show-user", "quant", "--property=Linger"], timeout=15)
    if "Linger=yes" in out:
        return None
    _run(["loginctl", "enable-linger", "quant"], timeout=15)
    return "LINGER was off -- re-enabled (a reboot would have left every timer down)"


def track_tunnel_url() -> str | None:
    """A quick-tunnel restart CHANGES the public URL, and the new one is only visible through
    the tunnel itself -- chicken and egg. The current URL is therefore extracted from the
    cloudflared log every pass and committed to data/desk_url.txt, so the repo on GitHub always
    carries the live link even when the old one is dead."""
    import re
    url = None
    candidates = [ROOT / "data" / "desk_tunnel.log",
                  *sorted((ROOT / "data" / "cro_ai_logs").glob("*tunnel*"), reverse=True)]
    for log in candidates:
        try:
            hits = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com",
                              log.read_text("utf-8", errors="replace"))
            if hits:
                url = hits[-1]
                break
        except OSError:
            continue
    if url is None:
        return None
    url_file = ROOT / "data" / "desk_url.txt"
    try:
        current = url_file.read_text("utf-8").strip()
    except OSError:
        current = ""
    if current == url:
        return None
    url_file.write_text(url + "\n", "utf-8")
    _run(["git", "-C", str(ROOT), "add", "-f", "data/desk_url.txt"], timeout=30)
    _run(["git", "-C", str(ROOT), "commit", "--no-verify", "-m",
          f"desk dashboard URL rotated -> {url}\n\n"
          f"Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"], timeout=30)
    _run(["git", "-C", str(ROOT), "push", "--quiet"], timeout=60)
    return f"TUNNEL URL rotated -> {url} (committed + pushed so the repo carries the live link)"


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

    _ok_note, skew_action = check_clock_skew()
    if skew_action:
        actions.append(skew_action)
        print(f"  {skew_action}")
    actions.extend(a for a in check_crontab() if (print(f"  {a}") or True))
    linger_note = check_lingering()
    if linger_note:
        actions.append(linger_note)
        print(f"  {linger_note}")
    url_note = track_tunnel_url()
    if url_note:
        actions.append(url_note)
        print(f"  {url_note}")

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
