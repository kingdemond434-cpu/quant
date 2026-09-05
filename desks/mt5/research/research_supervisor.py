"""research_supervisor: permanent self-healing watchdog for the MT5 research desk.

Restarts any research process that died before writing its DONE marker, forever,
until the work actually completes. Runs as a persistent loop; a scheduled task
(BootTrigger + 5-min tick) guarantees one instance is always alive.

Backoff: if a target dies within 180s of a restart, it is quarantined for 30 min
(prevents infinite restart storms on a crashing script; the crash log in
logs/<name>_super.log always shows why).

Disable permanently: create data/SUPERVISOR_OFF
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

BASE = Path(__file__).resolve().parent.parent

# THE EVENT LAYER'S ONLY REACH INTO THE CLOCK, and it is deliberately a soft one. `macro` can
# ask for the allocator's fast leg to run sooner than its 60s cadence when it measures
# information decaying faster than that. GUARDED because this file is the desk's watchdog: if
# the package is absent, half-installed or raises on import, the supervisor must keep restarting
# everything else exactly as before. A watchdog that dies with its newest dependency is not a
# watchdog.
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
try:
    from macro import interrupt as _macro_interrupt
except Exception:                                                        # noqa: BLE001
    _macro_interrupt = None                                              # type: ignore[assignment]

LOGS = BASE / "logs"
STATE = LOGS / "supervisor_state.json"
LOG = LOGS / "supervisor.log"
if os.name == "nt":
    PYW = Path(sys.executable).parent / "pythonw.exe"
    CHILD_LOGS = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "opencode" / "logs"
else:
    PYW = Path(sys.executable)
    CHILD_LOGS = LOGS / "child"
TARGETS = [
    dict(name="hunt12", args=["-u", "-W", "ignore", "research/run_hunt12.py"],
         marker="reports/DONE_hunt12", match="run_hunt12.py"),
    dict(name="hunt16", args=["-u", "-W", "ignore", "research/run_hunt16.py"],
         marker="reports/DONE_hunt16", match="run_hunt16.py"),
    dict(name="placebo", args=["-u", "-W", "ignore", "research/placebo_test.py",
                               "XAUUSD", "AUDCAD", "AUDJPY"],
         marker="reports/DONE_placebo", match="placebo_test.py"),
    dict(name="hunt17", args=["-u", "-W", "ignore", "research/run_hunt17.py"],
         marker="reports/DONE_hunt17", match="run_hunt17.py"),
    dict(name="fragility", args=["-u", "-W", "ignore", "research/fragility.py"],
         marker="reports/DONE_fragility", match="fragility.py"),
    dict(name="qquant_gates",
         args=["-u", "-W", "ignore", "research/qquant_gates.py", "--workers", "8"],
         marker="reports/DONE_qquant_gates_original10_v2", match="qquant_gates.py"),
    dict(name="regime_oos", args=["-u", "-W", "ignore", "research/regime_discovery.py"],
         marker="reports/DONE_regime_oos", match="regime_discovery.py"),
    dict(name="merge", args=["-u", "-W", "ignore", "research/merge_qquant.py"],
         marker="reports/DONE_merge", match="merge_qquant.py"),
    dict(name="research_loop", args=["-u", "-W", "ignore", "research/research_loop.py"],
         marker="reports/DONE_loop_final", match="research_loop.py"),
    dict(name="hunt19", args=["-u", "-W", "ignore", "research/run_hunt19.py"],
         marker="reports/DONE_hunt19", match="run_hunt19.py"),
    dict(name="hunt20", args=["-u", "-W", "ignore", "research/run_hunt20.py"],
         marker="reports/DONE_hunt20", match="run_hunt20.py"),
    dict(name="hunt21", args=["-u", "-W", "ignore", "research/run_hunt21.py"],
         marker="reports/DONE_hunt21", match="run_hunt21.py"),
    dict(name="hunt22", args=["-u", "-W", "ignore", "research/run_hunt22.py"],
         marker="reports/DONE_hunt22", match="run_hunt22.py"),
    dict(name="hunt23", args=["-u", "-W", "ignore", "research/run_hunt23.py"],
         marker="reports/DONE_hunt23", match="run_hunt23.py"),
    dict(name="macro_desk", args=["-u", "-W", "ignore", "research/macro_desk.py"],
         marker="reports/DONE_macro_never", match="macro_desk.py"),
    # RETIRED 2026-09-05, MT5 universe mandate. `options_desk` priced BTC/ETH options off the
    # Deribit public API and archived the surface as a proprietary dataset. The archive idea was
    # right and the ground was wrong: an implied-vol surface IS a moat, but a crypto-exchange
    # options venue is a universe this desk may not hunt. Rebuild it on MT5 ground -- index and
    # FX implied vol the desk can actually trade against -- rather than restoring this row.
    dict(name="crowding_miner", args=["-u", "-W", "ignore", "research/crowding_miner.py"],
         marker="reports/DONE_crowding_never", match="crowding_miner.py"),
    dict(name="news_desk", args=["-u", "-W", "ignore", "research/news_desk.py"],
         marker="reports/DONE_news_final", match="news_desk.py"),
    # THE WORLD'S CLOCK. Perpetual watcher: reads sources, scores each item's credibility,
    # novelty and unpriced fraction into the event ledger, and -- only where it MEASURES
    # information decaying faster than the allocator's 60s leg -- writes an interrupt request
    # the supervisor honours above. It never decides an allocation; it decides WHEN the
    # allocator gets to think. No marker, like the other perpetual desks.
    dict(name="macro_intel",
         args=["-u", "-W", "ignore", "-m", "macro.run_macro_intel", "--loop"],
         marker="reports/DONE_macro_intel_never", match="macro.run_macro_intel"),
    dict(name="signal_gate", args=["-u", "-W", "ignore",
                                   "research/signal_gate.py", "run_hunt18"],
         marker="reports/DONE_signal_gate_never", match="signal_gate.py"),
    dict(name="universal",
         args=["-u", "-W", "ignore", "research/universal_gate.py"],
         marker="reports/DONE_universal_curve_compendium", match="universal_gate.py"),
    dict(name="meta_desk",
          args=["-u", "-W", "ignore", "research/meta_desk.py"],
          marker="reports/DONE_meta", match="meta_desk.py"),
    dict(name="allocation",
          args=["-u", "-W", "ignore", "research/allocation.py"],
          marker="reports/DONE_allocation", match="allocation.py"),
]

#: THE CAPITAL BRAIN'S CLOCK (2026-09-05). `research/pf_allocator.py` was the sizing authority on
#: paper and ran on nobody's schedule: not this supervisor, not the gateway loop, not the hourly
#: or daily cycle, not a VPS unit. The gateway fails closed on a `pf_allocation.json` older than
#: an hour, so the solved book -- the whole state -> solve -> sizing chain the audit traced --
#: never sized a position; the desk fell back to the derived formula every pass and reported the
#: allocator ARMED. A decision organ with no clock is a claim, not a capability.
#:
#: The cadences: fast re-solves EVERY MINUTE on the cached world population, normal rebuilds
#: evidence and the no-trade filter every 15 min, heavy resamples the worlds and re-measures the
#: growth curve hourly. ONE allocator process at a time; the mode is the most overdue of the
#: three. The gateway consumes the newest book every minute and the no-trade filter, not this
#: clock, decides whether the book is worth trading toward (dE[log W] > turnover + slippage +
#: the uncertainty buffer), so a faster clock makes the book fresher without making it churn.
#:
#: This line used to read "fast ~5 min" and end "the principal's target is capital following the
#: freshest information state every minute; this is the honest solve cadence" -- an accurate
#: admission that the desk was five times slower than its own target. It is no longer five
#: minutes, so the admission is gone rather than left to rot into a false claim.
PERIODIC = [
    {"name": "pf_allocator", "match": "pf_allocator.py",
     "script": "research/pf_allocator.py",
     # EVERY MINUTE (principal, 2026-09-05: "all reactions must be every minute all allocations
     # etc"). The fast leg was 300s, so the desk's quickest possible response to anything -- a
     # macro release, a cross-asset move, an event -- was five minutes, while the gateway was
     # already consuming the newest book every minute. The solve was the bottleneck, not the
     # execution.
     #
     # SAFE BECAUSE OF THE GUARD ABOVE, NOT BECAUSE THE SOLVE IS FAST. `tick_periodic` refuses to
     # launch when an allocator is already running (`is_running(p["match"])`), so a 60s cadence
     # cannot stack solves on an 8GB box. If a fast pass takes 90s the desk gets a solve every
     # ~90s instead of every 300s -- strictly fresher, never concurrent. The clock is a floor on
     # staleness, not a promise about runtime.
     #
     # Only the FAST leg moves. Normal still rebuilds evidence every 15 min and heavy still
     # resamples the world population and re-measures the growth curve hourly, because those are
     # the expensive passes and running them every minute would starve the gauntlet and the
     # brain seats that share this box. Fast re-solves on the CACHED worlds, which is what makes
     # a one-minute cadence affordable at all.
     "cadence_s": {"fast": 60, "normal": 900, "heavy": 3600}},
]


def _allocator_mode(state: dict, now: float, cadence: dict[str, int]) -> str | None:
    """The most overdue mode, heaviest first; None when nothing is due yet."""
    for mode in ("heavy", "normal", "fast"):
        last = float((state.get(f"pf_allocator_{mode}") or {}).get("last_spawn", 0) or 0)
        if now - last >= cadence[mode]:
            return mode
    return None


def tick_periodic(state: dict, now: float, spawn) -> list[str]:
    """Launch every periodic job that is due and not already running. `spawn(name, args)`
    returns a pid; injected so a test can pin the cadence without a process."""
    launched: list[str] = []
    for p in PERIODIC:
        if (BASE / "data" / f"HOLD_{p['name']}").exists():
            continue
        if is_running(p["match"]):
            continue
        mode = _allocator_mode(state, now, p["cadence_s"])
        # ONLY WHERE THE CLOCK SAID NO. An interrupt can make the allocator run sooner; it can
        # never make it run less, never reach the expensive normal or heavy legs, and never get
        # past the `is_running` guard above. One request serves exactly once.
        req = None
        if mode is None and p["name"] == "pf_allocator" and _macro_interrupt is not None:
            try:
                req = _macro_interrupt.pending(
                    now=now,
                    consumed_at=float(state.get("macro_interrupt_consumed_at", 0) or 0))
            except Exception:                                            # noqa: BLE001
                req = None                    # a broken event layer must not stop the clock
            if req is not None:
                mode = "fast"
        if mode is None:
            continue
        args = ["-u", "-W", "ignore", p["script"], "--mode", mode]
        pid = spawn(p["name"], args)
        if pid is None:
            continue
        if req is not None:
            state["macro_interrupt_consumed_at"] = float(req.get("requested_at_epoch", now))
            log(f"supervisor: macro interrupt honoured -- {str(req.get('reason', ''))[:120]}")
        state[f"{p['name']}_{mode}"] = {"last_spawn": now, "pid": pid}
        # a heavy pass carries the normal and fast work, a normal pass the fast work
        if mode == "heavy":
            state["pf_allocator_normal"] = {"last_spawn": now, "pid": pid}
        if mode in ("heavy", "normal"):
            state["pf_allocator_fast"] = {"last_spawn": now, "pid": pid}
        launched.append(f"{p['name']}:{mode}")
    return launched


def log(msg: str) -> None:
    line = f"{datetime.now(UTC).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


CHILD_LOGS = CHILD_LOGS  # resolved above (platform-aware)


def is_running(match: str) -> bool:
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower().startswith("python") \
                    and any(match in (c or "") for c in (p.info["cmdline"] or [])):
                return True
        except Exception:
            continue
    return False


def already_supervised() -> bool:
    me = psutil.Process().pid
    parent = psutil.Process(me).ppid()
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.pid == me:
                continue
            # Windows venv launchers may leave a short-lived parent/child Python pair with the
            # identical command line. They are one invocation, not a second supervisor. Treating
            # the launcher as a peer made every scheduled start exit immediately.
            if p.pid == parent or p.ppid() == me:
                continue
            if not (p.info["name"] or "").lower().startswith("python"):
                continue
            cmd = " ".join(p.info["cmdline"] or [])
            if "research_supervisor.py" in cmd:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    if (BASE / "data" / "SUPERVISOR_OFF").exists():
        log("supervisor: disabled (data/SUPERVISOR_OFF present)")
        return 0
    if already_supervised():
        log("supervisor: another instance alive, exiting")
        return 0

    LOGS.mkdir(exist_ok=True)
    state: dict = {}
    try:
        state = json.loads(STATE.read_text("utf-8"))
    except Exception:
        pass
    log("supervisor: started")
    while True:
        if (BASE / "data" / "SUPERVISOR_OFF").exists():
            log("supervisor: disabled flag appeared, exiting")
            return 0
        now = time.time()
        if now - float(state.get("last_verify", 0) or 0) > 3600:
            try:
                subprocess.run(
                    [str(Path(sys.executable)), "-u", "-W", "ignore",
                     "research/verify_universal_state.py"],
                    cwd=str(BASE), capture_output=True, text=True, timeout=240)
                state["last_verify"] = now
                try:
                    STATE.write_text(json.dumps(state), encoding="utf-8")
                except Exception:
                    pass
            except Exception as e:
                log(f"universal-state verify failed: {e!r}")
        for t in TARGETS:
            if (BASE / "data" / f"HOLD_{t['name']}").exists():
                continue
            if (BASE / "data" / "VPS_AUTHORITY").exists() \
                    and t["name"] in ("universal", "merge", "allocation"):
                continue
            if (BASE / t["marker"]).exists():
                continue
            if is_running(t["match"]):
                continue
            st = state.get(t["name"], {})
            last = float(st.get("last_spawn", 0) or 0)
            if now - last < 180:
                log(f"supervisor: {t['name']} keeps dying, quarantined until "
                    f"{datetime.fromtimestamp(last + 1800, UTC).isoformat()}")
                continue
            try:
                CHILD_LOGS.mkdir(parents=True, exist_ok=True)
                sl = open(CHILD_LOGS / f"{t['name']}_super.log", "ab")
                py = sys.executable if os.name != "nt" else (t.get("python") or PYW)
                kwargs = {"stdout": sl, "stderr": subprocess.STDOUT}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.DETACHED_PROCESS \
                        | subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs["start_new_session"] = True
                proc = subprocess.Popen([str(py)] + t["args"], cwd=str(BASE), **kwargs)
                state[t["name"]] = {"last_spawn": now, "pid": proc.pid}
                STATE.write_text(json.dumps(state), encoding="utf-8")
                log(f"supervisor: respawned {t['name']} pid={proc.pid}")
            except Exception as e:
                log(f"supervisor: FAILED to spawn {t['name']}: {e!r}")
        def _spawn(name: str, args: list[str]):
            try:
                CHILD_LOGS.mkdir(parents=True, exist_ok=True)
                py = sys.executable if os.name != "nt" else PYW
                kwargs: dict = {"stderr": subprocess.STDOUT}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.DETACHED_PROCESS \
                        | subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs["start_new_session"] = True
                # the child inherits its own copy of the log handle; ours closes here
                with open(CHILD_LOGS / f"{name}_super.log", "ab") as sl:
                    proc = subprocess.Popen([str(py), *args], cwd=str(BASE), stdout=sl,
                                            **kwargs)
                log(f"supervisor: launched {name} {' '.join(args[-2:])} pid={proc.pid}")
                return proc.pid
            except Exception as e:
                log(f"supervisor: FAILED to launch {name}: {e!r}")
                return None

        try:
            if tick_periodic(state, now, _spawn):
                STATE.write_text(json.dumps(state), encoding="utf-8")
        except Exception as e:
            log(f"supervisor: periodic tick failed: {e!r}")
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
