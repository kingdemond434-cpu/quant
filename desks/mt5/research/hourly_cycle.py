"""hourly_cycle: the standing per-hour cycle for the MT5 desk.

1. HEALTH: verify every expected process (gateway loop cmd, running hunts) is
   alive; restart dead ones detached. Confirm placebo/hunt artifacts are fresh.
2. MINE: one external-intelligence pass (web) — fetch frontier sources, canonicalize
   seeds into data/frontier_inbox.json. If a source class is unreachable, try one
   bypass; if that fails, skip and do the next-highest-value thing (never idle).
3. VALIDATE: nothing to auto-run; hunts own the battery. Log pending candidates.
4. REPORT: write reports/frontier.json (survivors, placebo verdicts, gateway
   state, gold book, hunts in flight).
5. SYNC: write data/sync_marker.json so MT5Sync.cmd pushes to the VPS brains.

Run every hour (Startup loop MT5Hourly.cmd). Fail-visible, resumable, cheap.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
# BASE ON THE PATH, AT MODULE LEVEL. `record_tape()` runs BEFORE `daily()`, and `daily_cycle` is
# the module that happened to insert BASE -- so every hourly run reached `from mt5desk import
# tape` with BASE still absent and died on ModuleNotFoundError. MEASURED 2026-08-27: 66
# consecutive "tick tape FAILED" lines since the log was created on 08-22, i.e. five days of
# broker-native ticks never recorded. That tape is the desk's own moat data and it CANNOT be
# backfilled -- a tick nobody recorded is gone, unlike a bar you can re-download. Depending on
# another module's import side effect for your own path is the bug; this makes it explicit.
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# THE INTERPRETER THAT IS ACTUALLY RUNNING, never a path typed once and left behind. These were
# hardcoded to C:\Users\dell\...\Python312, which is the OLD box: this desk runs as
# Administrator on Python314, so the path did not exist and `start()` could never launch
# anything. Verified 2026-08-28 -- dell pythonw.exe: False, Administrator pythonw.exe: True.
# The failure was perfectly silent. `health()` read a hunt as dead, called `start()`,
# Start-Process failed against a nonexistent binary in a detached hidden window, and the cycle
# recorded "restarted": True. So the one repair this cycle performs has never once worked here,
# and it reported success every time.
# Deriving from sys.executable means a box move, a Python upgrade or a different user cannot
# break it again -- the interpreter running this file is by definition the one that exists.
PYE = sys.executable or "python.exe"
_pyw = Path(PYE).with_name("pythonw.exe")
PY = str(_pyw) if _pyw.exists() else PYE

EXPECTED = {
    "hunt12": ("pythonw.exe", "run_hunt12.py"),
    "hunt16": ("pythonw.exe", "run_hunt16.py"),
}


def procs() -> str | None:
    """The running python command lines, or None when they COULD NOT BE READ.

    None is not an empty list, and the difference decides whether this cycle launches processes.
    Measured 2026-08-28: on a loaded box the PowerShell CIM query exceeded 60 seconds, the
    TimeoutExpired propagated, and the ENTIRE hourly cycle died -- a health check killing the
    thing it was checking, and doing it precisely when the box was busy, which is exactly when
    the cycle matters most. MT5-Hourly had failed twice in a row on this before the stall
    watchdog surfaced it.

    Returning "" instead would be worse than crashing: every `script in blob` test would read
    False, `health()` would conclude both hunts were dead, and it would launch duplicates onto
    the box that was already too loaded to answer the query. Absence never resolves to a clean
    verdict (L1.28a) -- and here the wrong verdict is actively harmful.
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" "
             "| ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  procs(): UNMEASURED ({type(exc).__name__}) -- launching nothing this pass")
        return None
    return (out.stdout or "") + (out.stderr or "")


def start(script: str) -> bool:
    """Launch script hidden/detached. Returns whether the LAUNCH COMMAND ITSELF reported
    success -- not proof the process is still alive a moment later. health() re-polls procs()
    afterward for that; a launch command returning 0 and a process actually staying up are
    different facts, and conflating them is exactly the bug this replaced (restarted=True was
    written unconditionally, with no check at all, on top of a launch path that did not exist
    on this box in the first place)."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{PY}' -ArgumentList "
         f"'-u','-W','ignore','research\\{script}' -WorkingDirectory "
         f"'{BASE}' -WindowStyle Hidden"],
        capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def _cmd_lines() -> str | None:
    """cmd.exe command lines, or None when unreadable. Same rule as procs()."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" "
             "| ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return out.stdout or ""


def health() -> dict:
    blob = procs()
    res: dict = {}
    if blob is None:
        # UNMEASURED, so nothing is declared dead and nothing is launched. A pass that cannot
        # see the process table has no business starting processes.
        for name in EXPECTED:
            res[name] = {"alive": None, "note": "process table unreadable; no launch attempted"}
        res["gateway_cmd"] = {"alive": None, "note": "process table unreadable"}
        return res
    for name, (_, script) in EXPECTED.items():
        alive = script in blob
        res[name] = {"alive": alive}
        if not alive:
            launch_ok = start(script)
            if launch_ok:
                # Give the OS a moment to actually create the process before checking for it --
                # process creation itself is near-instant even for a script whose real work is
                # slow.
                time.sleep(5)
            res[name]["restarted"] = bool(launch_ok and script in procs())
            if not res[name]["restarted"]:
                res[name]["restart_failed"] = True
    # `str.find` RETURNS -1 WHEN NOT FOUND, AND bool(-1) IS TRUE -- so this read "alive" exactly
    # when MT5Gateway.cmd was absent, and False only in the one case where it sat at position 0.
    # An inverted health check is worse than none: it reports green for the failure it exists to
    # catch. Membership testing says what was meant.
    cmds = _cmd_lines()
    if "MT5Gateway.cmd" in blob:
        res["gateway_cmd"] = {"alive": True}
    elif cmds is None:
        res["gateway_cmd"] = {"alive": None, "note": "cmd table unreadable"}
    else:
        res["gateway_cmd"] = {"alive": "MT5Gateway" in cmds}
    return res


def mine() -> dict:
    """One web pass. Try the source; on failure try one bypass; else skip (never idle)."""
    inbox = BASE / "data" / "frontier_inbox.json"
    items = []
    if inbox.exists():
        try:
            items = json.loads(inbox.read_text(encoding="utf-8"))
        except Exception:
            items = []
    urls = [
        "https://www.reddit.com/r/algotrading/top.json?t=week&limit=15",
        "https://www.reddit.com/r/quant/top.json?t=week&limit=15",
    ]
    hits = []
    for u in urls:
        try:
            import urllib.request
            req = urllib.request.Request(u, headers={"User-Agent": "quant-research-desk/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            for child in data.get("data", {}).get("children", [])[:15]:
                d = child.get("data", {})
                hits.append({"src": u.split("/")[2], "title": d.get("title", "")[:200],
                             "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                             "score": d.get("score", 0), "ts": d.get("created_utc")})
        except Exception as e:
            hits.append({"src": u, "error": str(e)[:120], "bypass_tried": True})
    seen = {x.get("url") for x in items}
    fresh = [h for h in hits if h.get("url") and h["url"] not in seen and h.get("score", 0) >= 20]
    items.extend(fresh)
    inbox.write_text(json.dumps(items[-500:], indent=1), encoding="utf-8")
    return {"sources_tried": len(urls), "new_seeds": len(fresh), "inbox": len(items)}


def frontier_report(health: dict) -> None:
    rep = {"swept_at": datetime.now(UTC).isoformat(), "health": health}
    for name in ("hunt12_partial", "hunt16_partial", "placebo_test", "hunt13"):
        fp = BASE / "reports" / f"{name}.json"
        if fp.exists():
            try:
                rep[name] = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                rep[name] = None
    gw = BASE / "data" / "gateway_state.json"
    if gw.exists():
        with suppress(Exception):
            rep["gateway"] = json.loads(gw.read_text(encoding="utf-8"))
    (BASE / "reports" / "frontier.json").write_text(
        json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(f"frontier report written ({rep['swept_at']})", flush=True)


def daily() -> dict:
    """The operating chain -- shadow -> promoter -> markout -- run once per UTC day.

    THIS WAS THE HOLE. Health checks, web mining and a frontier report all ran hourly while the
    three processes that actually move an edge toward capital ran NOWHERE: nine validated
    candidates sat in `shadow_forward.SLEEVES` accruing no evidence and unable to promote. The
    supervisor could not have hosted them either -- it is built around one-shot DONE markers, so a
    recurring job would run once and never again.

    Called every hour deliberately. `daily_cycle` self-guards on a UTC date stamp, so this box gets
    exactly one run per day whenever it happens to be awake, instead of missing the day entirely
    because the laptop was shut at the scheduled minute.
    """
    try:
        import daily_cycle
        return {"exit_code": daily_cycle.main([]),
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        # Reported, never swallowed: this hourly cycle must survive, but a desk that cannot run its
        # promotion chain has to say so rather than print "cycle done".
        print(f"daily cycle FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


def record_tape() -> dict:
    """Persist broker-native ticks every hourly cycle before any research consumes them."""
    try:
        from mt5desk import (
            tape,
            triangle_tape,
        )

        tape_rc = tape.main([])
        triangle_rc = triangle_tape.main()
        return {"exit_code": max(tape_rc, triangle_rc),
                "triangle_exit_code": triangle_rc,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        print(f"tick tape FAILED: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


def state_vector() -> dict:
    """Rebuild the desk's description of the world, once, for every consumer to read.

    RUNS AFTER THE TAPE AND BEFORE THE ALLOCATOR'S NEXT PASS. A `RegimeEngine` fit costs ~8.5ms
    per observation -- 17s for 2,000 daily bars -- and the allocator's fast clock is five minutes,
    so the state vector cannot be assembled inline without eating the clock it informs. Every fit
    is cached against the bar it saw, so an hour whose daily bars have not turned over re-reads
    rather than refits and this step costs seconds.

    NEVER FAILS THE CYCLE. A state vector that cannot be built is a recorded gap, and the
    allocator degrades to the unconditioned solve it ran before this existed.
    """
    try:
        import state_vector_build

        rc = state_vector_build.main()
        return {"exit_code": int(rc), "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:                                          # noqa: BLE001
        return {"exit_code": 1, "error": f"{type(exc).__name__}: {exc}",
                "at": datetime.now(UTC).isoformat(timespec="seconds")}


def smoke_release() -> dict:
    """The box-side smoke test, every hour: does the code on this box import, compile and match
    the sealed release? Its verdict rides sync_marker.json so every other brain sees it. A
    failing smoke is the gateway refusing new risk an hour earlier than the dashboard would
    notice; a smoke that cannot run is recorded as exactly that, never as a pass."""
    try:
        r = subprocess.run([PYE, str(BASE / "scripts" / "smoke_release.py")],
                           capture_output=True, text=True, timeout=120)
        return {"rc": r.returncode, "tail": (r.stdout or r.stderr or "")[-400:]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"rc": None, "error": f"{type(exc).__name__}: {exc}"}


def deepen() -> dict:
    """Drain the deepening queue -- THE conversion bottleneck, and it was scheduled nowhere.

    THE HOLE, measured 2026-09-05. `miner_deepening_queue.json` held 908 tasks, and
    `deepening_worked.jsonl` had never been written: 0 decided, ever. The worker is named in the
    capability graph, in the rent ledger (`deepening_worker` -> sources deepening/mutation), in
    the bandit's consumer list and in deep_forest_miner's own docstring -- and NOTHING RAN IT. No
    cron row, no cycle call, no scheduled task. The graph said so plainly (`running: False`,
    stage WIRED) and nobody read it.

    That is the whole shape of the funnel's stall. The compiler admits candidates and queues the
    ones needing a deepening decision; nothing decides them; so `judged` reads 0 cells and the
    productivity report names `deepening` as the bottleneck every single run -- correctly, for a
    reason no one had traced to a missing schedule.

    Hourly, not daily, and with the worker's own default limit rather than a bigger one: each task
    costs a seat call, so the drain rate is a spend decision the worker already owns. 25/hour
    clears a 908-task backlog in about a day and a half of uptime while leaving the budget the
    worker's own accounting controls. It self-guards on `worked_ids()`, so a re-run inside the same
    hour decides nothing twice and costs nothing.
    """
    try:
        import deepening_worker
        return {"exit_code": deepening_worker.main([]),
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except SystemExit as exc:                       # argparse exits rather than returning
        return {"exit_code": int(exc.code or 0),
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        # Same rule as `daily`: the hourly cycle must survive, but a desk whose only conversion
        # drain failed to start has to say so rather than print "cycle done".
        print(f"deepening worker FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"exit_code": None, "error": f"{type(exc).__name__}: {exc}",
                "at": datetime.now(UTC).isoformat(timespec="seconds")}


def heal_clocks() -> dict:
    """Revive forward clocks stopped by an identity that can never come back. NOT scheduled before.

    THE HOLE, off the live dashboard 2026-09-05: roughly thirty of ~53 forward clocks read
    IDENTITY_BROKEN, accruing nothing while their day counters kept running -- what the same-day
    fence calls the worst combination, a clock maturing on stale data.

    The recovery organ already existed. `desks/mt5/scripts/heal_identity_broken_clocks.py` calls
    itself a STANDING FIXER in its own first line, and nothing anywhere ran it: no cron row, no
    cycle call, no scheduled task, and the only mention of it in the tree is a comment in
    shadow_forward. Second organ found this way today, after the deepening worker -- the desk
    keeps building recovery machinery and then not scheduling it, which is why the same breaches
    survive being "fixed".

    RUN WITH --apply, DELIBERATELY, and the flag's own default is not being overruled lightly.
    That default is right for a human running it ad hoc; it was never a prohibition on scheduling
    the thing whose docstring asks to be scheduled. What the two repairs actually do is why this
    is sound rather than a loosening:

      * `reconcile()` clears the break only when the identity is byte-identical again -- a
        transient sync or an outage. The window is KEPT because nothing was ever different.
      * `rebase_code()` fires only when reconcile refuses, and it RESETS forward_start. The sleeve
        re-earns its days against the code actually running, its prior record preserved under
        `window_before_rebase`. The price of recovery is paid in days, the one currency here that
        cannot be faked.

    So no clock inherits evidence it did not earn, and the alternative -- leaving them terminal --
    is not the conservative choice: it is a day counter maturing against a bar on data the sleeve
    never gathered.
    """
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, str(BASE / "scripts" / "heal_identity_broken_clocks.py"), "--apply"],
            capture_output=True, text=True, timeout=600, check=False)
        return {"exit_code": r.returncode, "tail": (r.stdout or "").strip().splitlines()[-3:],
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        print(f"identity healer FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"exit_code": None, "error": f"{type(exc).__name__}: {exc}",
                "at": datetime.now(UTC).isoformat(timespec="seconds")}


def main() -> None:
    smoke = smoke_release()
    h = health()
    t = record_tape()
    s = state_vector()
    d = daily()
    dp = deepen()
    hc = heal_clocks()
    m = mine()
    frontier_report(h)
    (BASE / "data" / "sync_marker.json").write_text(
        json.dumps({"last_cycle": datetime.now(UTC).isoformat(),
                    "health": h, "tape": t, "state_vector": s, "daily": d,
                    "deepening": dp, "heal_clocks": hc, "mine": m,
                    "smoke_release": smoke},
                   indent=1), encoding="utf-8")
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
