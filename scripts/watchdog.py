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
_WD_LOG = _ROOT / "data" / "watchdog.log"
_WD_LOG_CAP = 8_000_000                      # bytes; nothing else rotates this file
_DETACHED = 0x00000008 | 0x08000000          # DETACHED_PROCESS | CREATE_NO_WINDOW


#: BANNED-UNIVERSE ARMS (GAP REGISTER #150, LAWS §1). The MT5/Fusion mandate of 2026-08-18
#: permanently retires the crypto-exchange universe, but three arms below still re-arm organs that
#: trade or record it -- including `run_cashcarry_executor.py --live --capital 4500`. Measured
#: 2026-08-27: that executor was up with live arguments, held flat ONLY by `data/CASHCARRY_KILL`,
#: while this watchdog stood ready to respawn it every tick if its heartbeat went stale. An
#: actuator that re-arms a banned book is a ruin path, not an inconvenience: it is the one way a
#: retired universe takes capital again without anyone deciding that it should.
#:
#: The desk's sanctioned non-root switches are consulted here because until now the crypto arms
#: consulted NOTHING. `data/RECORDERS_OFF` (set 2026-08-25, permanent under the mandate) idles the
#: recorders; `data/CASHCARRY_KILL` holds the carry book flat. Clearing either is a principal act,
#: and LAWS §1 makes the ban permanent regardless -- so this gate can only ever be opened
#: deliberately, never by a stale heartbeat.
#:
#: NOT GATED, deliberately: the dead-man switch (Tier-3 never-touch, and a ruin rail must arm
#: under every condition including this one), the dashboard, and the CRO daily cycle -- row #150's
#: point is that this watchdog's mandated arms are worth keeping, so they are left untouched.
_RECORDERS_OFF = _ROOT / "data" / "RECORDERS_OFF"
_CC_KILL = _ROOT / "data" / "CASHCARRY_KILL"


def _banned_universe_block() -> str | None:
    """Why the crypto-exchange arms must not fire, or None if nothing blocks them."""
    if _RECORDERS_OFF.exists():
        return "data/RECORDERS_OFF set"
    if _CC_KILL.exists():
        return "data/CASHCARRY_KILL set"
    return None


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
    # run_cashcarry_executor.py and liquidation_listener.py were removed 2026-09-05 (universe
    # mandate) along with their scripts. Their units may still exist on the box; that is an OPS
    # cleanup, and leaving the mapping here would not help -- `_systemd_owns` is only consulted
    # before spawning a script this watchdog still supervises, and it supervises neither now.
    "scripts/run_deadman_switch.py": "quant-deadman.service",
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


def _run_logged(args: list[str], label: str, timeout: float, *, keep_stdout: bool = False) -> None:
    """Run a per-tick helper and KEEP the evidence of how it went.

    Every one of these calls used to be a bare `subprocess.run(..., capture_output=True)` whose
    result was discarded, which cost the desk twice over:

      1. THE OUTPUT WAS THE ONLY WITNESS. `run_alerts.py` catches a failed push and *prints*
         "pager push failed: ..." -- it does not raise and it still exits 0. Capturing that into a
         variable nobody read is precisely how the pager can die silently, which it has done twice
         (quota exhaustion 07-11 -> 07-16, latin-1 header encode 07-19 across a live dead-man
         fire). A discarded stdout is not monitoring, it is a muted alarm.
      2. A TIMEOUT KILLED THE WHOLE TICK. `subprocess.run(timeout=...)` RAISES TimeoutExpired, and
         nothing caught it. One slow leverage-opt therefore aborted main() before the pager, the
         CRO daily cycle and the netlify publish ever ran -- the first helper in the list could
         silently disarm every helper after it. Each is now independently fenced.

    Noise discipline, because a log nobody reads is the same failure one layer along: a clean run
    logs NOTHING unless `keep_stdout` asks for it. Only failures (nonzero exit, timeout, spawn
    error, anything on stderr) are unconditional.
    """
    try:
        r = subprocess.run([str(_PY), *args], cwd=str(_ROOT), timeout=timeout,
                           capture_output=True, text=True, check=False)
        rc, out, err = r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except subprocess.TimeoutExpired as e:
        # e.stdout/.stderr are bytes-or-None here, unlike the text=True success path.
        def _dec(v: object) -> str:
            return v.decode("utf-8", "replace").strip() if isinstance(v, bytes) else str(v or "")
        rc, out, err = None, _dec(e.stdout), f"TIMEOUT after {timeout:.0f}s: {_dec(e.stderr)}"
    except (OSError, subprocess.SubprocessError) as e:
        rc, out, err = None, "", f"{type(e).__name__}: {e}"
    failed = rc != 0 or bool(err)
    if not failed and not (keep_stdout and out):
        return
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    head = f"{stamp} watchdog/{label} rc={'timeout' if rc is None else rc}"
    lines = [f"{head}: {ln}" for ln in (out.splitlines() + err.splitlines())[:20]] or [head]
    _append_log(lines)
    if failed:
        print(f"watchdog: {label} FAILED (rc={rc}) -- see data/watchdog.log")


def _append_log(lines: list[str]) -> None:
    """Append to data/watchdog.log, self-capping so a chatty helper can never fill the disk.

    The file is also cron's stdout target for this script, so both writers land in one place --
    both open O_APPEND, and single-line writes of this size do not interleave.
    """
    try:
        _WD_LOG.parent.mkdir(parents=True, exist_ok=True)
        if _WD_LOG.exists() and _WD_LOG.stat().st_size > _WD_LOG_CAP:
            # Trim by BYTES, not by line count: one helper emitting a single enormous traceback
            # would sail past any "keep the last N lines" rule and the cap would never bind.
            with _WD_LOG.open("rb") as fh:
                fh.seek(-(_WD_LOG_CAP // 2), 2)
                tail = fh.read()
            _WD_LOG.write_bytes(tail.split(b"\n", 1)[-1])   # drop the partial leading line
        with _WD_LOG.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass                                  # logging must never break the tick it is logging


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
    refused: list[str] = []
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
    # `_banned_universe_block()` is still called: it is the fence that REFUSES to start anything
    # trading the retired universe, and tests/scripts/test_watchdog_banned_universe.py pins it.
    # What is gone (2026-09-05) is the cash-carry executor branch it used to gate -- that script
    # was deleted with the universe, so the refusal now has nothing left to refuse here and the
    # block is reported rather than acted on.
    blocked = _banned_universe_block()
    if blocked:
        refused.append(f"crypto-exchange execution ({blocked})")
    if not _fresh(_DM_HB, 300):
        # DEAD-MAN'S SWITCH: isolated ruin rail (no LLM, no configs, no libs imports) --
        # 5 consecutive minutes of combined equity < 65% of high-water -> kill file +
        # flatten everything + page. TIER-3 never-touch; see scripts/run_deadman_switch.py.
        _spawn(["scripts/run_deadman_switch.py"], "deadman-switch")
        acted.append("deadman")
    # THE CARRY EXECUTOR AND THE LIQUIDATION LISTENER ARE NO LONGER SUPERVISED (2026-09-05,
    # universe mandate). Both scripts were deleted with the crypto-exchange desk, and a watchdog
    # that Popen's a missing file does not fail loudly -- it logs a spawn, records the action, and
    # reports a healthy tick having started nothing. That is the "supervisor believes it is
    # supervising" failure this organ exists to prevent, so the branches are removed rather than
    # left to fire against absent scripts. The dead-man switch above is untouched: it is Tier-3
    # and it is the one process that still protects real money.
    if not _fresh(_TUN_HB, 120) and blocked:
        # the crypto dashboard this tunnel published is retired and the cloudflared ingress was
        # emptied; opening a public tunnel to it is an outward-facing act with nothing behind it.
        refused.append(f"public-tunnel ({blocked})")
    elif not _fresh(_TUN_HB, 120):
        # ngrok if configured (permanent-ish), else cloudflared quick-tunnel
        tun = "scripts/run_ngrok.py" if (_ROOT / "data" / "secrets" / "ngrok.json").exists() \
            else "scripts/run_tunnel.py"
        _spawn([tun], "public-tunnel")
        acted.append("tunnel")
    # recompute dynamic leverage (cheap) so executor + dashboard use fresh growth-optimal sizing,
    # then refresh the molded headline feed (reads JSON + one futures call).
    _run_logged(["scripts/run_leverage_opt.py"], "leverage-opt", 60)
    # `run_live_combined.py` (the molded crypto book feed) was deleted 2026-09-05; its tick is
    # gone rather than run against a missing file.
    # data-pipeline health check: refresh web/health.json each watchdog tick so the dashboard
    # surfaces archive staleness and executor liveness without a separate scheduled task.
    _run_logged(["scripts/data_health.py"], "data-health", 30)
    # PAGER: push CRITICAL alerts (dead heartbeat / stuck kill / root-cause / growth defect) to the
    # principal's phone via ntfy -- deduped 6h, never noisy, never blocks the tick.
    # keep_stdout: this one's stdout is the delivery record ("N page(s) sent", "pager push
    # failed: ...") and it is the only place a push failure is ever stated -- see _run_logged.
    _run_logged(["scripts/run_alerts.py"], "alerts", 30, keep_stdout=True)
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
        _run_logged(["scripts/publish_netlify.py"], "netlify", 120)
        netlify_marker.write_text(str(time.time()), "utf-8")
        acted.append("netlify")
    # REFUSALS ARE STATED. A silently-skipped arm and a healthy arm print the same line, and the
    # desk would have no way to tell "the ban is holding" from "the heartbeat happened to be fresh".
    if refused:
        print("watchdog: REFUSED banned-universe arm(s): " + ", ".join(refused))
    print("watchdog: " + (", ".join(acted) + " started" if acted else "all healthy"))


if __name__ == "__main__":
    main()
