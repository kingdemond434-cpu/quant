"""Self-healing supervisor: keep the dashboard + live executor + liquidation listener alive.

Idempotent -- safe to run every few minutes from Task Scheduler. Decides via a TCP probe (dashboard)
and heartbeat freshness (executor, liquidation listener), so it never double-starts; the executor's
own single-instance lock is the backstop. This replaces the fragile per-job scheduled tasks: ONE
watchdog keeps the always-on processes up, and those processes own data accumulation + research.

    python scripts/watchdog.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_IS_WIN = os.name == "nt"
# PLATFORM FIX (2026-07-23): this watchdog was written for Windows Task Scheduler.
# On the Linux VPS the Scripts/pythonw.exe path does not exist AND creationflags
# raises ValueError, so _spawn() crashed on its FIRST call -- killing the watchdog
# on 07-11 and leaving the daily research cycle unscheduled (forward clocks frozen)
# and run_alerts un-ticked (pager silent) for 11.5 days.
_PYW = (_ROOT / ".venv" / "Scripts" / "pythonw.exe") if _IS_WIN \
    else (_ROOT / ".venv" / "bin" / "python")
_PY = (_ROOT / ".venv" / "Scripts" / "python.exe") if _IS_WIN \
    else (_ROOT / ".venv" / "bin" / "python")
_HB = _ROOT / "data" / "executor_heartbeat"
_CC_HB = _ROOT / "data" / "cashcarry_exec_heartbeat"
_LIQ_HB = _ROOT / "data" / "liquidation_heartbeat"
_TUN_HB = _ROOT / "data" / "tunnel_heartbeat"
_DM_HB = _ROOT / "data" / "deadman_heartbeat"
_DETACHED = 0x00000008 | 0x08000000          # DETACHED_PROCESS | CREATE_NO_WINDOW


def _port_up(port: int) -> bool:
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _fresh(p: Path, max_sec: float) -> bool:
    try:
        return (time.time() - p.stat().st_mtime) < max_sec
    except OSError:
        return False


_UNITS = {                                   # script -> the systemd unit that owns it on the VPS
    "scripts/run_cashcarry_executor.py": "quant-cashcarry.service",
    "scripts/run_deadman_switch.py": "quant-deadman.service",
    "scripts/liquidation_listener.py": "quant-liquidations.service",
    "scripts/serve_dashboard.py": "quant-dashboard.service",
}


def _systemd_owns(script: str) -> bool:
    """True when systemd already has a LIVE process for this script's unit.

    DUAL SUPERVISION IS THE ORPHAN FACTORY (2026-07-26). This watchdog is laptop-era: it Popen's
    daemons directly with start_new_session, so anything it starts is owned by cron, not by the
    unit that also supervises it. On 2026-07-26 that produced an executor orphaned at 12:48 which
    held the single-instance lock for 8h; every systemd spawn exited on that lock, and with
    Restart=always the unit respawned against it 5,354 times. Worse, the orphan kept running
    PRE-FIX code, so the funding-measurement fix committed that evening was inert in the process
    that actually owned the book -- a committed fix that never shipped.

    So: when systemd has a live main process, never Popen a second one. When it does not, the
    Popen backstop still fires -- an orphan is recoverable, a dead ruin rail is not, and this box
    denies `systemctl start` to the quant user, so deferring is the only lever available here.
    """
    unit = _UNITS.get(script)
    if not unit:
        return False                          # no unit (laptop / new script) -> watchdog owns it
    try:
        pid = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", unit],
                             capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False                          # cannot tell -> fall through to the backstop
    return bool(pid) and pid != "0" and Path(f"/proc/{pid}").exists()


def _spawn(args: list[str], label: str) -> None:
    if args and _systemd_owns(args[0]):
        print(f"watchdog: {label} is systemd-owned and live -- NOT spawning a duplicate "
              f"(a second instance would orphan the book; the unit's Restart= owns recovery)")
        return
    _kw = {"creationflags": _DETACHED} if _IS_WIN else {"start_new_session": True}
    subprocess.Popen([str(_PYW), *args], cwd=str(_ROOT),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **_kw)
    print(f"watchdog: (re)started {label}")


def _reap_deadman() -> None:
    """Marker-driven reaper for zombie dead-man instances (2026-07-11 incident: an old-code
    S4U-spawned instance is invisible/unkillable from a user session, but THIS watchdog runs
    inside that same S4U session and can kill it). Touch data/.reap_deadman to arm; the marker
    clears only when at least one process was actually reaped."""
    marker = _ROOT / "data" / ".reap_deadman"
    if not marker.exists():
        return
    try:
        import contextlib
        import os

        import psutil
        mode = marker.read_text("utf-8").strip()
        keep = {os.getpid()}
        with contextlib.suppress(Exception):
            keep |= {p.pid for p in psutil.Process(os.getpid()).parents()}
        n = 0
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.info["pid"] in keep:
                    continue
                name = (p.info["name"] or "").lower()
                if not name.startswith("python"):
                    continue
                cmd = " ".join(p.info["cmdline"] or [])
                # mode "all": a zombie whose cmdline is unreadable cross-session can hide from
                # the targeted match -- kill EVERY supervised python and let this watchdog
                # resurrect the flock (all daemons are restart-safe by design; 07-11 incident)
                if mode == "all" or "run_deadman_switch" in cmd:
                    p.kill()
                    n += 1
            except Exception:
                continue
        if n:
            marker.unlink()
            print(f"watchdog: reaped {n} python process(es) (mode={mode or 'deadman'})")
    except Exception as e:
        print(f"watchdog: reap failed {e!r}")


def main() -> None:
    acted: list[str] = []
    # FREEZE (VPS-migration cutover 2026-07-12): data/FREEZE present -> reap ALL supervised
    # python from inside this S4U session (the only session with kill rights over S4U daemons)
    # and EXIT before any respawn. This is how the laptop desk is cleanly retired without a
    # double-book against the VPS. Remove data/FREEZE + re-enable the task to un-retire.
    if (_ROOT / "data" / "FREEZE").exists():
        import contextlib
        import os

        import psutil
        keep = {os.getpid()}
        with contextlib.suppress(Exception):
            keep |= {p.pid for p in psutil.Process(os.getpid()).parents()}
        n = 0
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.info["pid"] in keep or not (p.info["name"] or "").lower().startswith("python"):
                    continue
                cmd = " ".join(p.info["cmdline"] or [])
                if "watchdog" in cmd:                       # never reap a watchdog sibling
                    continue
                p.kill()
                n += 1
            except Exception:
                continue
        print(f"watchdog: FROZEN -- reaped {n} desk process(es), no respawn")
        return
    _reap_deadman()
    if not _port_up(8080):
        _spawn(["scripts/serve_dashboard.py", "--port", "8080"], "dashboard")
        acted.append("dashboard")
    if not _fresh(_CC_HB, 240):
        # PRIMARY book = cash-and-carry EXECUTED (long spot + short perp, delta-neutral funding
        # harvest). 60s heartbeat + single-instance lock -> no double book. The structural survivor.
        # MAX-before-diminishing deployment of the delta-neutral book (bounded risk, NOT leverage):
        # capital ~= 80% of spot capacity (~$5.6k legs+USDT), over top-10 funding names so the
        # extra capital deploys into NEW carries WITHOUT churning the held ones (hysteresis). Leaves
        # ~$1.1k USDT buffer for reconcile/slippage; futures margin far from binding. >10 names or a
        # forced resize = diminishing (lower funding names / churn fees).
        # hold-top 3000 = hold while funding stays POSITIVE (a rate cut like top-60 slices through
        # the venue's huge same-rate tie groups -> lottery membership -> 159 closes in week one,
        # fee drag ~= the entire funding harvest). Funding pays 8-hourly; sub-8h churn is pure cost.
        _spawn(["scripts/run_cashcarry_executor.py", "--live", "--top", "10", "--hold-top", "3000",
                "--capital", "4500", "--interval", "600"], "cashcarry-executor")
        acted.append("cashcarry-exec")
    if not _fresh(_DM_HB, 300):
        # DEAD-MAN'S SWITCH: isolated ruin rail (no LLM, no configs, no libs imports) --
        # 5 consecutive minutes of combined equity < 65% of high-water -> kill file +
        # flatten everything + page. TIER-3 never-touch; see scripts/run_deadman_switch.py.
        _spawn(["scripts/run_deadman_switch.py"], "deadman-switch")
        acted.append("deadman")
    # perp L/S book is now SHADOW only (run_crypto_shadow in the flywheel); its executor is retired.
    if not _fresh(_LIQ_HB, 600):
        _spawn(["scripts/liquidation_listener.py"], "liquidation-listener")
        acted.append("liquidations")
    if not _fresh(_TUN_HB, 120):
        # ngrok if configured (permanent-ish), else cloudflared quick-tunnel
        tun = "scripts/run_ngrok.py" if (_ROOT / "data" / "secrets" / "ngrok.json").exists() \
            else "scripts/run_tunnel.py"
        _spawn([tun], "public-tunnel")
        acted.append("tunnel")
    # recompute dynamic leverage (cheap) so executor + dashboard use fresh growth-optimal sizing,
    # then refresh the molded headline feed (reads JSON + one futures call).
    py = str(_PY)
    subprocess.run([py, "scripts/run_leverage_opt.py"], cwd=str(_ROOT), timeout=60,
                   capture_output=True, check=False)
    subprocess.run([py, "scripts/run_live_combined.py"], cwd=str(_ROOT), timeout=60,
                   capture_output=True, check=False)
    # data-pipeline health check: refresh web/health.json each watchdog tick so the dashboard
    # surfaces archive staleness and executor liveness without a separate scheduled task.
    subprocess.run([py, "scripts/data_health.py"], cwd=str(_ROOT), timeout=30,
                   capture_output=True, check=False)
    # PAGER: push CRITICAL alerts (dead heartbeat / stuck kill / root-cause / growth defect) to the
    # principal's phone via ntfy -- deduped 6h, never noisy, never blocks the tick.
    subprocess.run([py, "scripts/run_alerts.py"], cwd=str(_ROOT), timeout=30,
                   capture_output=True, check=False)
    # DAILY CRO research cycle: once per 24h, spawned DETACHED (heavy -- must not block the tick).
    # Inherits the watchdog's S4U schedule, so it runs whether logged on or not. No separate task.
    cro_marker = _ROOT / "data" / ".last_cro_cycle"
    if not _fresh(cro_marker, 86400):
        _spawn(["scripts/daily_research_cycle.py"], "cro-daily-cycle")
        cro_marker.write_text(str(time.time()), "utf-8")
        acted.append("cro-daily")
    # permanent Netlify link: THROTTLED to every 30 min (free tier meters deploys -> don't burn it).
    netlify_marker = _ROOT / "data" / ".last_netlify_publish"
    if (_ROOT / "data" / "secrets" / "netlify.json").exists() and not _fresh(netlify_marker, 1800):
        subprocess.run([str(_PY),
                        "scripts/publish_netlify.py"], cwd=str(_ROOT), timeout=120,
                       capture_output=True, check=False)
        netlify_marker.write_text(str(time.time()), "utf-8")
        acted.append("netlify")
    print("watchdog: " + (", ".join(acted) + " started" if acted else "all healthy"))


if __name__ == "__main__":
    main()
