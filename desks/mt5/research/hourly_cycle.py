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
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
#: The REPOSITORY root, two levels above the desk. Legs live under both: the research organs under
#: `desks/mt5/...`, the publication and maintenance scripts under `<repo>/scripts/...`. `_producer`
#: resolves against both and reports a script it finds under neither.
REPO = BASE.parent.parent
# BASE ON THE PATH, AT MODULE LEVEL. `record_tape()` runs BEFORE `daily()`, and `daily_cycle` is
# the module that happened to insert BASE -- so every hourly run reached `from mt5desk import
# tape` with BASE still absent and died on ModuleNotFoundError. MEASURED 2026-08-27: 66
# consecutive "tick tape FAILED" lines since the log was created on 08-22, i.e. five days of
# broker-native ticks never recorded. That tape is the desk's own moat data and it CANNOT be
# backfilled -- a tick nobody recorded is gone, unlike a bar you can re-download. Depending on
# another module's import side effect for your own path is the bug; this makes it explicit.
# REPO ON THE PATH TOO, for the same reason and with a worse symptom. `_costed` imports
# `libs.ops.compute_ledger`, which lives at the REPOSITORY root, not under the desk -- and that
# import was never going to succeed, because only BASE and BASE/research were ever added here.
# MEASURED on the box 2026-09-06: `ModuleNotFoundError: No module named 'libs.ops'` on the first
# costed leg of every run. `_costed` catches it and runs the leg anyway, by design, so nothing
# broke and nothing complained -- the cycle simply recorded no compute, hour after hour, while
# `libs.ops.allocators` went on reporting COMPUTE as the stack's weakest link for want of the
# denominator these very runs were supposed to be producing. A detector starved by the bug it is
# meant to detect reads exactly like a detector with nothing to report.
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
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
    # This chain includes terminal/native numerical work.  Keep it outside the controller for
    # the same reason as state_vector(): on 2026-09-06 it terminated the process after the state
    # refresh had returned, leaving every mining/publication leg below permanently unreachable.
    target = BASE / "research" / "daily_cycle.py"
    timeout_s = max(60, float(os.environ.get("DAILY_CYCLE_HOURLY_BUDGET_SEC", "900")))
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target)],
                           capture_output=True, text=True, cwd=str(BASE),
                           timeout=timeout_s, check=False)
        return {"exit_code": int(r.returncode),
                "status": "OK" if r.returncode == 0 else "FAILED",
                "tail": (r.stdout or r.stderr or "")[-500:],
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": None, "status": "TIMEOUT", "timeout_s": exc.timeout,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except OSError as exc:
        print(f"daily cycle FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"exit_code": None, "status": "FAILED_TO_START",
                "error": f"{type(exc).__name__}: {exc}",
                "at": datetime.now(UTC).isoformat(timespec="seconds")}


def record_tape() -> dict:
    """Persist broker-native ticks every hourly cycle before any research consumes them."""
    # TWO RECORDERS, TWO FATES. These were in one `try` and it hid the thing that matters: on
    # 2026-09-06 `tape.main` recorded 359,107 broker-native ticks and THEN `triangle_tape` raised
    # KeyError, so the whole leg returned `{"error": ...}` and the hour read as "tick tape FAILED"
    # -- for a leg whose irreplaceable half had just succeeded. Ticks cannot be backfilled and
    # triangles can be recomputed from them, so the two must never share a verdict.
    results: dict[str, object] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    codes: list[int] = []
    for label, call in (("tape", lambda: _tape_main()), ("triangle", lambda: _triangle_main())):
        try:
            rc = call()
        except Exception as exc:
            print(f"tick tape {label} FAILED: {type(exc).__name__}: {exc}", flush=True)
            results[f"{label}_error"] = f"{type(exc).__name__}: {exc}"
            codes.append(1)
        else:
            results[f"{label}_exit_code"] = rc
            codes.append(int(rc))
    results["exit_code"] = max(codes) if codes else 1
    return results


def publish_state() -> dict:
    """Publish this box's state to git -- a SECOND, independent path to the dashboard.

    THE DASHBOARD HAD EXACTLY ONE PUBLISHER AND NOBODY WATCHED IT. `sync_shadow_to_git.ps1` is
    scheduled as the Windows task MT5-ShadowSync every 15 minutes, and it is a careful script:
    it checks every exit code, retries a rejected push three times with fetch+merge, and logs
    what it did. None of that helps when the TASK is gone. Measured 2026-09-06: shadow_health.json
    last written 2026-08-26 14:45, gateway_state.json 08-17, account_state.json never delivered --
    eleven days in which this desk ran perfectly, recorded 359,107 ticks in a single hour and
    completed its daily cycle, while the dashboard said "box has not reported for 266.4h".

    A single publisher makes delivery a single point of failure whose symptom is
    indistinguishable from a dead desk, and the desk is the thing people then go and look at.

    So the hourly cycle publishes too. The two paths share no scheduler: this one rides
    MT5Hourly.cmd, the other rides the Windows task scheduler, and either alone keeps the
    dashboard current. Committing the same unchanged files twice is free -- `sync_shadow_to_git`
    stops at "no change since last sync" -- so the redundancy costs a subprocess an hour.

    NOT AN ERROR OFF THE BOX. The VPS runs this cycle too and has no PowerShell and nothing to
    publish; that is reported as a skip, never as a failure, so it cannot become noise that
    trains a reader to ignore this leg.
    """
    script = BASE / "scripts" / "sync_shadow_to_git.ps1"
    if not script.exists():
        return {"skipped": "sync_shadow_to_git.ps1 is absent on this host"}
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return {"skipped": "no PowerShell on this host -- publishing is the trading box's job"}
    try:
        r = subprocess.run([powershell, "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-File", str(script)],
                           capture_output=True, text=True, cwd=str(REPO),
                           timeout=600, check=False)
    except Exception as exc:
        print(f"publish_state FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"{type(exc).__name__}: {exc}"}
    tail = (r.stdout or r.stderr or "").strip().splitlines()[-3:]
    if r.returncode != 0:
        # LOUD, because this is the leg that decides whether anybody can SEE the desk. A silent
        # publisher failure is the one that costs eleven days.
        print(f"publish_state FAILED rc={r.returncode}: {' | '.join(tail)}", flush=True)
    return {"exit_code": r.returncode, "tail": tail,
            "at": datetime.now(UTC).isoformat(timespec="seconds")}


def _tape_main() -> int:
    from mt5desk import tape
    return int(tape.main([]))


def _triangle_main() -> int:
    from mt5desk import triangle_tape
    return int(triangle_tape.main())


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
    # ISOLATED, because this leg fits native numerical models over multiple parquet panels.
    # On 2026-09-06 its process terminated during a fit without raising a Python exception; when
    # it ran in-process that also terminated the hourly controller before mining, validation,
    # publication and the other producers could run.  A failed world-state refresh is a visible
    # degraded input, never permission to turn one optional model into a factory-wide kill switch.
    target = BASE / "research" / "state_vector_build.py"
    timeout_s = max(15, float(os.environ.get("STATE_VECTOR_HOURLY_BUDGET_SEC", "45")))
    try:
        r = subprocess.run(
            [sys.executable, "-u", "-W", "ignore", str(target), "--budget-s",
             str(max(10, timeout_s - 5))],
            capture_output=True, text=True, cwd=str(BASE), timeout=timeout_s, check=False,
        )
        return {
            "exit_code": int(r.returncode),
            "status": "OK" if r.returncode == 0 else "FAILED",
            "tail": (r.stdout or r.stderr or "")[-500:],
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": None, "status": "TIMEOUT", "timeout_s": exc.timeout,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except OSError as exc:
        return {"exit_code": None, "status": "FAILED_TO_START",
                "error": f"{type(exc).__name__}: {exc}",
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


def _bandit_budget(leg: str, base: int) -> tuple[int, dict]:
    """The bandit-scaled budget for a leg, recorded; the base on any failure (never a stall)."""
    try:
        import research_budget
        applied, rec = research_budget.budget_s(leg, base)
        research_budget.record(rec)
        return int(applied), rec
    except Exception as exc:
        return int(base), {"leg": leg, "applied": False, "factor": 1.0,
                           "why": f"research_budget unavailable: {type(exc).__name__}: {exc}"}


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
        # THE BANDIT HAS AUTHORITY HERE (2026-09-16): the drain limit is the worker's default
        # scaled by the bandit's share of the deepening arms (research_budget), recorded.
        _lim, _rec = _bandit_budget("deepen", int(getattr(deepening_worker, "DEFAULT_LIMIT", 25)))
        return {"exit_code": deepening_worker.main(["--limit", str(max(1, _lim))]),
                "limit": int(max(1, _lim)), "bandit_factor": _rec.get("factor"),
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


#: The admission scan's own cadence is the supervisor's hourly heavy pass; twice that is "the
#: supervisor has missed a pass", which is the condition this roster steps in on.
ADMISSION_SCAN_MAX_AGE_S = 2 * 3600.0

#: How long the hypothesis-lane sweep may go unrefreshed before it is swept again. A week of H1
#: bars is ~120 rows against the ~54,000 each symbol carries, so this clock exists to stop the
#: artifact ageing forever, not because the answer moves inside a day.
HUNT12_MAX_AGE_S = 7 * 24 * 3600.0

def _hunt12_state(art: Path | None = None,
                  now: datetime | None = None) -> tuple[bool, str]:
    """Whether the hypothesis-lane sweep needs a pass this hour, and why.

    THE ALLOCATOR'S FIRST INPUT HAD NO CLOCK AT ALL, and that is the whole reason this leg
    exists. `pf_allocator` assembles its evidence through `portfolio_projection`, which refuses
    outright without `reports/hunt12_partial.json`; that report's only scheduler was
    `research_supervisor`, keyed on a ONE-SHOT `reports/DONE_hunt12` marker, on the same worker
    the allocator leg's own comment records as dead or stalled. One-shot means the report is
    produced once ever or never, and `data/PF_ALLOCATOR_ARMED` has been present since 2026-09-04
    against a `reports/pf_allocation.json` that HAS NEVER EXISTED. Measured on a checkout of this
    code 2026-09-10:

        $ python desks/mt5/research/pf_allocator.py --mode normal
        REFUSING to project a portfolio without .../reports/hunt12_partial.json   (exit 1)

    So "the allocator is armed and wired" was true, and every sleeve on the desk still sized off
    `ramped_fraction` -- the authority ramp, a count of closed trades with no estimate of growth
    in it -- because the growth-maximising sizer refused on an input nothing produced.

    FOUR STATES, and three of them run:

        absent        never swept on this box: the condition that has held since 2026-09-04
        incomplete    a resumable sweep part-way through; the next pass advances it
        stale         past HUNT12_MAX_AGE_S, so it is re-swept from scratch
        fresh         complete and inside the age bound -- skipped, and the leg says so

    A leg that reports SKIPPED with a reason is not an idle leg (III.16): the artifact it exists
    to keep current is current, which is the measurement.
    """
    art = art or (BASE / "reports" / "hunt12_partial.json")
    if not art.exists():
        return True, "reports/hunt12_partial.json absent -- the allocator refuses without it"
    try:
        doc = json.loads(art.read_text("utf-8"))
    except (OSError, ValueError):
        return True, "the carried sweep is unreadable"
    if doc.get("complete") is False:
        return True, (f"the sweep has covered {len(doc.get('done') or [])} of "
                      f"{doc.get('n_routed')} hypothesis-lane symbols")
    stamp = doc.get("started_at") or doc.get("at") or doc.get("swept_at")
    try:
        ts = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True, "the carried sweep carries no readable timestamp"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age = ((now or datetime.now(UTC)) - ts).total_seconds()
    if age > HUNT12_MAX_AGE_S:
        return True, (f"the carried sweep is {age / 3600:.0f}h old "
                      f"(max {HUNT12_MAX_AGE_S / 3600:.0f}h)")
    return False, f"complete and {age / 3600:.0f}h old"


def hunt12() -> dict:
    """`run_hunt12`: the hypothesis-lane sweep the growth sizer refuses to solve without.

    ROUTED BY LANE, WHICH IS WHAT LETS IT HOLD A CLOCK AT ALL. The sweep used to walk all 251
    registry symbols; the principal's 2026-09-06 standing order routes single-name equities to
    the event lane, taking it to 145 and the grid from 4,016 cells to 2,320. That is the mandate,
    and it is also the difference between ~20 minutes and a job that cannot fit an hourly budget
    -- which is why it was one-shot in the first place.

    RESUMABLE AND DEADLINED, so a 720-second leg advances the sweep and the next hour finishes it
    rather than restarting it. The partial names its own coverage and `load_h12_survivors`
    refuses an unfinished one, so a part-swept universe can never be loaded as the whole book.
    """
    run, why = _hunt12_state()
    if not run:
        return {"status": "SKIPPED", "why": why, "at": datetime.now(UTC).isoformat()}
    print(f"  hunt12: sweeping -- {why}", flush=True)
    return {**_producer("hunt12", "research/run_hunt12.py",
                        "--deadline-s", str(HUNT12_DEADLINE_S)), "why": why}


def _admission_scan_age_s(art: Path | None = None, now: datetime | None = None) -> float | None:
    """Seconds since the last MEASURED admission scan in reports/pf_allocation.json, or None
    when there is no measured scan to date (absent artifact, unreadable, not MEASURED, or the
    scan is only carried forward from an older measurement -- `carried_from` names the real
    stamp, and it is that stamp which ages)."""
    art = art or (BASE / "reports" / "pf_allocation.json")
    try:
        adm = json.loads(art.read_text("utf-8")).get("admission") or {}
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(adm, dict) or adm.get("status") != "MEASURED":
        return None
    stamp = adm.get("carried_from") or adm.get("measured_utc")
    try:
        ts = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ((now or datetime.now(UTC)) - ts).total_seconds()


def _rostered_but_unpriced(art: Path | None = None, sleeves: Path | None = None) -> list[str]:
    """Names on the roster (data/sleeves.json, LIVE or STANDBY) that the carried admission scan
    never priced -- absent from its published `admission.universe` under every key
    `promoter._join_keys` would try.

    A SCAN THAT NEVER PRICED A ROSTERED SLEEVE IS NOT A SCAN OF THE CURRENT BOOK. Measured
    2026-09-08: until `pf_allocator.scalp_evidence` read the ledger's own field names
    (closed_at/opened_at), no scalp clock was in the priced universe, so every scan on disk
    answered "nothing" about the three PROMOTION_CANDIDATE scalp sleeves -- and `normal` kept
    carrying that scan forward as MEASURED and fresh for as long as it was under two hours old.
    `promoter.capital_verdict` reads a sleeve the universe lacks as UNMEASURED ("nobody looked"),
    which by design neither adds nor removes risk, so a STANDBY row stayed STANDBY on a scan
    that had no opinion about it, while every artifact read healthy. The join is the promoter's
    own (`_join_keys` / `_index`), so this cannot disagree with the reader it serves.

    Returns [] -- the age rule alone decides -- when the roster is empty or unreadable, and when
    the promoter's join cannot be imported (printed, so the gap is not silent).
    """
    sleeves = sleeves or (BASE / "data" / "sleeves.json")
    try:
        rows = [s for s in (json.loads(sleeves.read_text("utf-8")).get("sleeves") or [])
                if isinstance(s, dict)
                and str(s.get("status") or "").upper() in ("LIVE", "STANDBY")]
    except (OSError, ValueError, AttributeError):
        return []
    if not rows:
        return []
    art = art or (BASE / "reports" / "pf_allocation.json")
    try:
        adm = json.loads(art.read_text("utf-8")).get("admission") or {}
        universe = adm.get("universe") if isinstance(adm.get("universe"), dict) else {}
    except (OSError, ValueError, AttributeError):
        universe = {}
    try:
        from promoter import _index, _join_keys
    except Exception as exc:
        print(f"  pf_allocator: cannot read the promoter's join ({type(exc).__name__}: {exc}); "
              f"the scan's age alone decides the mode", flush=True)
        return []
    idx = _index({str(k): v for k, v in universe.items() if isinstance(v, dict)})
    missing: list[str] = []
    for s in rows:
        name = str(s.get("name") or "")
        keys = _join_keys(name, str(s.get("symbol") or ""), str(s.get("family") or ""),
                          str(s.get("selector") or s.get("window") or ""))
        if name and not any(k in idx for k in keys):
            missing.append(name)
    return missing


def _allocator_mode_for_the_hour(art: Path | None = None, now: datetime | None = None,
                                 sleeves: Path | None = None) -> str:
    """`heavy` when the admission scan is missing, stale, or never priced a rostered sleeve;
    else the hourly `normal`."""
    age = _admission_scan_age_s(art, now)
    if age is None or age > ADMISSION_SCAN_MAX_AGE_S:
        return "heavy"
    missing = _rostered_but_unpriced(art, sleeves)
    if missing:
        print(f"  pf_allocator: heavy -- {len(missing)} rostered sleeve(s) absent from the "
              f"carried scan's universe: {missing[:6]}", flush=True)
        return "heavy"
    return "normal"


#: Exit codes a leg uses to REPORT rather than to fail, by leg name. Declared here, beside the
#: place that reads them, because the alternative is every consumer of the ledger inventing its
#: own list. A code absent from a leg's tuple is a genuine failure and is recorded as one.
#:
#: Each entry is a claim about that leg's contract and is checked by reading the leg: `model_skill`
#: documents exit 2 as a verdict in its own docstring; `deep_forest` returns 1 for a pass that
#: mined nothing; `maintain_miners` exits 2 after examining stale artifacts and deciding, which is
#: the work, not a failure to do it.
VERDICT_EXITS: dict[str, tuple[int, ...]] = {
    "model_skill": (2,),
    "deep_forest": (1,),
    "maintain_miners": (2,),
}


#: THE HOURLY CYCLE COULD NOT FINISH IN AN HOUR, AND ITS TAIL NEVER RAN (measured 2026-09-16).
#: One full pass sums the legs' budgets: backtest 36 min, deepen 20, daily 15, and six legs at
#: their 12-minute cap -- 110 to 200 minutes -- under a task limit of 55 minutes. Every pass was
#: killed mid-way, and the legs after the kill point (deepen, forward_reconcile, falsifier_run,
#: credit_assignment, mutation_yield, closed_loop, ...) simply never ran: the daily chain had not
#: completed since 2026-09-13, the generator weights were two days old, and the closed-loop
#: attestation read those absences as false verdicts. The cure is two clocks, one code path:
#:   HOURLY_PLAN=core   -- the cheap governance / forward / publication legs, every hour, ~15 min
#:   HOURLY_PLAN=heavy  -- the research producers, back to back, on a limit that fits them
#:   HOURLY_PLAN=all    -- the historical single pass (default, so nothing changes uninvited)
#: A leg outside the plan is SKIPPED_BY_PLAN: no ledger row, so `opportunity_cost` and the
#: meta-controller's epoch read the truth (it did not run here) rather than a phantom run.
HOURLY_PLAN = str(os.environ.get("HOURLY_PLAN", "all") or "all").strip().lower()
CORE_LEGS: frozenset[str] = frozenset({
    "smoke_release", "health", "release_identity", "input_identity", "burn_in", "record_tape",
    "regime_monitor", "state_vector", "heal_clocks", "wiring_audit", "promoter",
    "forward_reconcile", "closed_loop", "acceptance", "candidate_conservation", "pit_canaries",
    "mutation_yield", "credit_assignment", "publish_survivors", "publish_dashboard",
    "stamp_freshness", "time_joins", "layer_census", "opportunity_cost", "dead_architecture",
    "prosecutor", "scaling_laws", "arena", "session_capital", "session_allocation",
    "allocator_join", "rebalance_trigger", "edge_reliability", "edge_confidence", "capacity",
    "fill_attribution", "execution_resolver", "markout", "swap_rejudge", "queue_compact",
    "requeue_unrunnable", "merge_docket", "miner_conversion", "graveyard_model",
    "research_exchange_score", "model_skill", "research_org", "experiment_design",
    "experiment_cache", "opportunity_gap", "opportunity_forecast", "forecast_contract",
    "alpha_breadth", "alpha_periodic_table", "regime_coverage", "timeframe_coverage",
    "frontier_unknowns", "frontier_report", "frontier_ontology", "counterfactual_world",
    "strategy_paths", "reclaim_disk", "archive_tape", "queue_cycle", "release_authority",
    # THE 2026-09-16 BLUEPRINT ORGANS (phases C/D of the Tier-1 ledger), all cheap readers.
    "axis_registry", "tier1_scorecard", "novelty_gate", "forced_flow_calendar", "breadth_ladder",
    "wiring_ceo", "live_system_state", "hazard_engine", "posterior_alpha", "semantic_memory",
    "model_role_benchmark", "research_departments", "qd_frontier", "value_of_data",
    "research_api_status", "artifact_chain", "residual_queue", "unseen_frontier",
    "source_registry",
})


#: THE DEPARTMENTS (principal 2026-09-16: "Explore = 100% || Exploit = 100% || Transfer = 100% ||
#: Validate = 100% || Intel = 100% || Meta = 100%, each with its own workers, queues and
#: reservation"). One heavy pass ran every research producer in ONE sequential process, so the
#: gauntlet waited for the crawler and the macro brain waited for the backtest -- and a pass
#: summed to three hours. A department plan (HOURLY_PLAN=dept:<name>) runs only its own
#: non-core legs, in the cycle's own order, as its own scheduled task; the departments run
#: CONCURRENTLY, so each is at its full useful throughput every hour and none can starve
#: another. A leg that feeds another in the same pass sits in the same department (search ->
#: compile -> merge_docket -> deepen is one pipeline). Legs named in no department belong to
#: `rest`, which also hosts the auto-clocked organs. The core plan is unchanged.
DEPARTMENTS: tuple[str, ...] = ("data", "intel", "discovery", "validate", "macro", "execution",
                                "forward", "meta", "rest")
LEG_DEPARTMENT: dict[str, str] = {
    # data: bars, tapes, lakes, sources -- the inputs every other department reads
    **dict.fromkeys(("refresh_bars", "tape_features", "lake_promote", "universe_integrity",
                     "source_routes", "source_fixer", "asia_collector", "asia_parser",
                     "asia_plane", "archive_tape", "reclaim_disk", "maintain_miners",
                     "spread_provenance", "microstructure_census", "fusion_cost",
                     "cost_construction", "swap_rejudge", "sge_premium"), "data"),
    # intel: the global intelligence agency -- crawlers, forests, frontier scouts
    **dict.fromkeys(("world_crawler", "deep_forest", "moat_miner", "market_intel", "mine",
                     "exogenous_search", "standing_questions", "frontier", "frontier_report",
                     "frontier_implementer", "hunt12"), "intel"),
    # discovery: the candidate pipeline, in order, plus the evolutionary generators
    **dict.fromkeys(("search", "sweep", "breadth_sweep", "compile_candidates", "merge_docket",
                     "deepen", "alpha_evolution", "alpha_rl", "ml_layer", "ensemble_optimizer",
                     "requeue_unrunnable", "queue_cycle", "queue_compact", "miner_conversion",
                     "recertify_canon", "session_chart_expansion", "experiment_design",
                     "experiment_cache", "probation"), "discovery"),
    # validate: the adversarial evidence lab
    **dict.fromkeys(("external_gauntlet", "backtest", "falsifier_run", "adversaries",
                     "stop_reverse", "orthogonality", "blind_reviewer", "synthetic_regimes",
                     "evaluator_lab"), "validate"),
    # macro: the cross-asset / macro brain
    **dict.fromkeys(("fred_macro", "futures_lead_lag", "causal_graph", "residual_factors",
                     "weak_signals", "edges_macro_fusion_sweep", "strategy_paths",
                     "counterfactual_world", "opportunity_forecast", "forecast_contract",
                     "exposure_decomposition"), "macro"),
    # execution: the execution research command
    **dict.fromkeys(("execution_twin", "entry_timing", "cost_to_edge", "exit_study",
                     "execution_resolver"), "execution"),
    # forward: forward evidence, promotion and the allocator
    **dict.fromkeys(("enrol_clocks", "pf_allocator", "daily", "hunt12_forward"), "forward"),
    # meta: the machine that runs the machine (the heavy part of it)
    **dict.fromkeys(("issue_board", "publish_state", "model_league", "ml_layer_meta"), "meta"),
}


def department_of(name: str) -> str:
    """The department a heavy leg belongs to; `rest` when no department names it."""
    return LEG_DEPARTMENT.get(name, "rest")


def in_plan(name: str, plan: str | None = None) -> bool:
    """Does leg `name` run under `plan`? core = CORE_LEGS only; heavy = every non-core leg;
    dept:<d> = the non-core legs of department d; all = everything.
    An `auto_*` leg is already filtered by its own plan in run_auto_legs and always passes."""
    p = (plan if plan is not None else HOURLY_PLAN)
    if name.startswith("auto_"):
        return True
    if p == "core":
        return name in CORE_LEGS
    if p == "heavy":
        return name not in CORE_LEGS
    if p.startswith("dept:"):
        return name not in CORE_LEGS and department_of(name) == p.split(":", 1)[1]
    return True


AUTO_LEGS_FILE = BASE / "data" / "auto_legs.json"


def _auto_leg(entry: dict) -> dict:
    """Run one auto-clocked organ under its budget; a dict result, never a raise."""
    organ = str(entry.get("organ") or "")
    target = REPO / organ
    if not target.exists():
        return {"exit_code": None, "status": "MISSING", "why": f"{organ} is not in the tree",
                "at": datetime.now(UTC).isoformat()}
    budget = max(15, int(entry.get("budget_s") or 120))
    cwd = BASE if organ.startswith("desks/mt5/") else REPO
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target),
                            *[str(a) for a in (entry.get("argv") or [])]],
                           capture_output=True, text=True, cwd=str(cwd), timeout=budget,
                           check=False)
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "budget_s": budget, "at": datetime.now(UTC).isoformat()}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "timeout_s": budget, "status": "TIMEOUT",
                "at": datetime.now(UTC).isoformat()}


def run_auto_legs(plan: str | None = None, path: Path | None = None) -> dict:
    """THE HOURLY ORGAN WIRER'S OTHER HALF (principal 2026-09-16). `wiring_ceo` writes
    data/auto_legs.json: every safe organ nothing else schedules, with a plan and a budget
    measured by probation. This runs the ones that belong to the current plan as ordinary
    costed legs (`auto_<stem>`), so a build lands on a clock the hour after it is found --
    with the ledger row, the provenance envelope and the failure isolation every named leg
    gets. The clock is data; nobody edits this file to wire an organ."""
    p = plan if plan is not None else HOURLY_PLAN
    src = path or AUTO_LEGS_FILE
    try:
        doc = json.loads(src.read_text(encoding="utf-8-sig"))
        legs = [e for e in (doc.get("legs") or []) if isinstance(e, dict) and e.get("organ")]
    except (OSError, ValueError):
        return {"n": 0, "why": "no auto_legs.json yet: the wiring CEO has not run"}
    # An auto-clocked organ's plan is core or heavy; under department plans the heavy ones
    # belong to `rest` (one department runs them, not nine).
    def _wants(e: dict) -> bool:
        ep = str(e.get("plan") or "heavy")
        if p == "all":
            return True
        if p.startswith("dept:"):
            return ep == "heavy" and p == "dept:rest"
        return ep == p

    chosen = [e for e in legs if _wants(e)]
    out: dict[str, dict] = {}
    for e in chosen:
        name = str(e.get("leg") or ("auto_" + Path(str(e["organ"])).stem))
        out[name] = _costed(name, lambda e=e: _auto_leg(e))
    print(f"auto legs: {len(chosen)} of {len(legs)} clocked organ(s) ran under plan={p}",
          flush=True)
    return {"n": len(chosen), "of": len(legs), "results": out}


_LEG_ARTIFACTS: dict[str, list[Path]] | None = None


def _leg_artifacts(name: str) -> list[Path]:
    """The artifact(s) the Tier-1 ledger says leg `name` writes -- declared outputs for the
    provenance envelope (output_hash). Read once per process; unknown legs declare nothing."""
    global _LEG_ARTIFACTS
    if _LEG_ARTIFACTS is None:
        table: dict[str, list[Path]] = {}
        try:
            doc = json.loads((REPO / "docs" / "research" / "tier1_program.json")
                             .read_text(encoding="utf-8-sig"))
            for it in doc.get("items", []):
                sched = str(it.get("scheduled_by") or "")
                art = str(it.get("artifact") or "")
                if not art or "hourly_cycle:" not in sched:
                    continue
                for tok in sched.split(","):
                    tok = tok.strip()
                    if tok.startswith("hourly_cycle:"):
                        leg = tok.split(":", 1)[1]
                        for root in (REPO, BASE):
                            cand = root / art
                            if cand.exists():
                                table.setdefault(leg, []).append(cand)
                                break
        except (OSError, ValueError):
            table = {}
        _LEG_ARTIFACTS = table
    return list(_LEG_ARTIFACTS.get(name, []))


def _costed(name: str, fn):
    """Run one leg and record what it COST, whatever it returns or raises.

    THE COMPUTE ALLOCATOR'S DENOMINATOR ARRIVES HERE OR NOWHERE. `libs.ops.allocators` reports
    COMPUTE as the stack's weakest link because nothing decides it -- and it cannot be decided by
    writing the ranking formula, because that formula divides by hours and this desk had never
    recorded an hour. This cycle is where most of the desk's compute is actually spent, so costing
    its legs is the cheapest possible way to get a real denominator: no new schedule, no new
    process, one append per leg.

    NEVER FAILS THE LEG. A ledger that can take down the work it measures would be removed within
    a week, correctly. An absent `libs` (this file also runs from the desk root on the box) simply
    means the leg runs uncosted, which is the state it was in before.

    ONE LEG MUST NEVER TAKE THE PASS WITH IT, which is `_producer`'s own stated principle --
    "a crash inside them must not take the cycle's remaining legs with it" -- extended from the
    subprocess legs to every leg. Subprocess legs already had it; in-process legs and, as it
    turned out, errors raised while BUILDING a call did not.

    MEASURED 2026-09-07, and the cost was not theoretical:

        TypeError: _producer() takes from 2 to 3 positional arguments but 4 were given

    escaped `main` at leg `pf_allocator`, so `publish_state`, `issue_board` and the four research
    report producers -- every leg after it -- never ran. The board then froze and reported those
    same reports as STALLED. A fifty-five-leg research cycle that stops dead on one bad call is
    a cycle whose reliability is the product of fifty-five things all going right.

    NOT SILENT, WHICH IS THE WHOLE DIFFERENCE. The failure is printed, recorded in the compute
    ledger with its exception, and returned as the leg's result -- so it lands in
    `sync_marker.json` and reaches the issue board like any other bad leg. What changes is only
    that the OTHER fifty-four legs still get to run.

    KeyboardInterrupt and SystemExit are re-raised: those are someone stopping the pass, not the
    pass failing, and catching them would make the cycle unkillable.
    """
    if not in_plan(name):
        # Not this clock's leg: no ledger row, no verdict -- the other plan owns it.
        return {"status": "SKIPPED_BY_PLAN", "plan": HOURLY_PLAN,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        from libs.ops.compute_ledger import close_run, open_run
    except Exception as exc:
        # LOUD, NOT SILENT (theirs, 2026-09-10). `compute_ledger` says in its own words that a
        # denominator which fails silently is a scaling law nobody can draw; this was the import
        # that could fail without a word.
        print(f"{name} compute ledger UNAVAILABLE: {type(exc).__name__}: {exc}", flush=True)
        open_run = close_run = None                                     # type: ignore[assignment]
    run = open_run(name, kind="hourly_cycle") if open_run else None
    try:
        out = fn()
    except (KeyboardInterrupt, SystemExit):
        # THE SAME FIX WAS MADE TWICE (2026-09-06 on the VPS as "keep hourly factory alive after
        # isolated leg failure", 2026-09-07 here as "stop one leg ending the pass") and the two
        # differed on SystemExit only. The VPS read a leg's SystemExit as its verdict and carried
        # its code; this branch re-raises it, because every in-process leg that can raise it
        # (`deepen`, the searches) already catches it at the call and reports the code itself,
        # so the only SystemExit that reaches here is someone stopping the pass. Merged
        # 2026-09-08 on this branch's rule, which test_hourly_cycle_legs_are_callable pins.
        if close_run and run is not None:
            close_run(run, outcome="interrupted")
        raise
    except BaseException as exc:
        detail = f"{type(exc).__name__}: {exc}"
        if close_run and run is not None:
            close_run(run, outcome=detail[:200])
        print(f"  LEG FAILED {name}: {detail}", flush=True)
        _emit_leg(name, detail[:200])
        return {"error": detail[:300], "status": "LEG_FAILED",
                "at": datetime.now(UTC).isoformat()}
    # A LEG THAT FAILS WITHOUT RAISING WAS RECORDED AS "ok" (theirs, 2026-09-10 -- and it is the
    # defect this desk has paid most for). `_producer` returns a DICT: a non-zero exit, a MISSING
    # script or a timeout come back as data, nothing is raised, and the ledger wrote `ok`.
    # `pf_allocator` exited 1 every hour for six days and every ledger row for it said ok, so the
    # streak that is supposed to separate a blip from an outage counted zero the whole time.
    # `libs.ops.completion` reads exactly this field.
    outcome = "ok"
    if isinstance(out, dict):
        status = str(out.get("status") or "").upper()
        if out.get("error"):
            outcome = f"FAILED: {out['error']}"[:200]
        elif status and status not in {"OK", "SUCCESS", "COMPLETED", "SKIPPED"}:
            outcome = status
        elif out.get("timeout_s") and out.get("exit_code") is None:
            outcome = "TIMEOUT"
        elif out.get("exit_code") not in (None, 0):
            # A VERDICT IS NOT A FAILURE, AND RENDERING THEM THE SAME IS ITS OWN DEFECT (WS-005).
            #
            # Several legs exit non-zero BY DESIGN to report bad news. `model_skill` says so in
            # its own docstring -- "its non-zero exit is a VERDICT, not a cycle failure: it exits
            # 2 while any predictor is unscored or beaten by its baseline ... a measurement organ
            # must never be able to stop the desk by reporting bad news". `deep_forest` exits 1
            # for a pass that mined nothing; `maintain_miners` exits 2 having examined every
            # stale artifact and decided correctly about each.
            #
            # The ledger wrote `exit_code=2` for all of them, identical to a crash. Measured
            # 2026-09-13: a reader counting non-ok rows found "16 legs failing every pass" and
            # went looking for sixteen bugs, when most of those legs were working and reporting.
            # The desk already knows this rule and states it one file over -- "different alarms
            # and they must not render the same way".
            #
            # So the leg declares which of its exit codes are verdicts, and the ledger says
            # `verdict_exit=N` rather than `exit_code=N`. Nothing is hidden: the code is still
            # there, a verdict still ends a leg non-zero, and a code NOT on the declared list is
            # still a failure. What changes is that a reader can tell them apart.
            _code = out["exit_code"]
            outcome = (f"verdict_exit={_code}" if _code in VERDICT_EXITS.get(name, ())
                       else f"exit_code={_code}")
    if close_run and run is not None:
        close_run(run, outcome=outcome, outputs=_leg_artifacts(name))
    _emit_leg(name, outcome)
    return out


def _emit_leg(name: str, outcome: str) -> None:
    """THE EVENT LOG (Tier-1 item I2, 2026-09-09): every leg's end is an event, and the legs
    that mark a domain transition (DATA_UPDATED, GAUNTLET_SWEPT, ALLOCATION_DECIDED, ...)
    emit that transition too, so a consumer can ask what happened since it last looked instead
    of inferring it from the clock. Never fails the leg; an absent `libs` means no event."""
    try:
        from libs.ops.events import leg_events
        leg_events(name, outcome)
    except Exception as exc:
        print(f"  event for {name} not recorded: {type(exc).__name__}: {exc}", flush=True)


#: Wall clock a search leg may spend inside the cycle. The two searches are the desk's own
#: hypothesis SOURCES, so starving them starves the docket -- but a search that overran the hour
#: would push the deepening worker, the miners and the marker out of the pass entirely. Twelve
#: minutes each leaves the 40-minute deepening budget and the remaining legs their time inside the
#: hour, and a search that needs longer is one that should be given its own task on the box.
SEARCH_BUDGET_SEC = 720

#: Where `hunt12` stops itself, one minute inside the budget above. It stops BETWEEN symbols, so
#: the minute is what it needs to write its artifact and exit rather than be SIGKILLed somewhere
#: inside a symbol -- which loses that symbol's work and can land in the middle of a write.
HUNT12_DEADLINE_S = SEARCH_BUDGET_SEC - 60


def _producer(name: str, script: str,
              *args: str | tuple[str, ...] | list[str]) -> dict:
    """Run one hypothesis producer as a subprocess, bounded, and report what happened.

    ARGUMENTS ARE VARIADIC AND TUPLES ARE FLATTENED, because the old single-tuple signature took
    the whole cycle down. Measured on the box 2026-09-07:

        TypeError: _producer() takes from 2 to 3 positional arguments but 4 were given

    from `_producer("pf_allocator", "research/pf_allocator.py", "--mode", "normal")`. That is the
    obvious way to write it, two of the legs here were written that way, and the signature
    accepted only `("--mode", "normal")` as one tuple. `_costed` does not swallow a TypeError
    raised while BUILDING the call -- the exception escapes `main`, so the cycle died at leg
    `pf_allocator` and every leg after it never ran: `publish_state`, `issue_board` and the four
    research reports among them. The issue board froze at 12:37 and reported the reports it never
    got to run as STALLED, which is a defect describing its own symptom.

    Accepting both shapes costs three lines and removes the whole class. A call that reads
    naturally is not a call that should crash a fifty-five-leg cycle.
    """
    flat: list[str] = []
    for a in args:
        if isinstance(a, (tuple, list)):
            flat.extend(str(x) for x in a)
        else:
            flat.append(str(a))
    return _producer_impl(name, script, tuple(flat))


#: Legs whose job is to CLOSE A GAP rather than search, and how long each may take.
#:
#: A search leg is fine to truncate: it samples, and next hour it samples again. An ENROLMENT pass
#: is not, and the difference cost the desk eighty-four forward clocks. `shadow_forward` walks the
#: authorized runs and enrols the ones without a clock; at 720s it was killed partway through the
#: same prefix EVERY hour, so the tail could never be reached -- not once, not eventually. Eighty-
#: four certificates that had cleared all ten gates sat accruing nothing, indefinitely, while the
#: leg reported as scheduled and running.
#:
#: THE SHAPE TO RECOGNISE: a truncated job that restarts from the same end is not slow, it is
#: BROKEN, and it looks identical to slow on every dashboard. Either the pass must finish, or it
#: must consume its backlog first so that truncation still makes progress. `shadow_forward` gets
#: the budget to finish; the gauntlet already does the other (never-judged cells sort first).
LEG_BUDGET_SEC: dict[str, int] = {
    "enrol_clocks": 2_700,
    # THE FOUR ACTIVATION LEGS ARE SEARCHES, NOT RENDERERS. `weak_signals` rebuilds member
    # signals for up to 24 members across 67 symbols and its own `run()` already self-limits at
    # 2400s; a cycle budget below that would kill it at the same prefix every hour, which is the
    # failure `enrol_clocks` was raised for. The other three get room to reach their data.
    "weak_signals": 2_700,
    "residual_factors": 1_800,
    "exogenous_search": 1_200,
}


def _producer_impl(name: str, script: str, args: tuple[str, ...] = ()) -> dict:
    """The body: resolve the script against both roots and run it under the cycle budget.

    NOT IN-PROCESS, unlike `deepen`. These are search jobs: they allocate heavily, they can hang
    on a terminal call, and a crash inside them must not take the cycle's remaining legs with it.
    A subprocess with a timeout gives all three properties for the cost of an interpreter start.

    THE SCRIPT IS RESOLVED AGAINST BOTH ROOTS, and a miss is REPORTED rather than run.
    Every leg here used to live under `desks/mt5`, so `BASE / script` was always right. The
    publication legs do not: `build_zentech_state` and `run_miner_maintenance` are repo-level
    scripts, and `BASE / "scripts/build_zentech_state.py"` is a path that does not exist. Python
    given a nonexistent file exits 2 with a one-line error, which this would have captured as a
    perfectly ordinary failing leg -- a dashboard that silently stopped being rebuilt, reported
    hourly as a two-digit exit code nobody reads. ABSENCE IS NEVER A PASS (L1.28a): a script
    found at neither root says MISSING and names both places it looked.
    """
    for root in (BASE, REPO):
        target = root / script
        if target.exists():
            break
    else:
        return {"exit_code": None, "status": "MISSING",
                "why": f"{script} exists under neither {BASE} nor {REPO}",
                "at": datetime.now(UTC).isoformat()}
    budget = LEG_BUDGET_SEC.get(name, SEARCH_BUDGET_SEC)
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target), *args],
                           capture_output=True, text=True, cwd=str(root),
                           timeout=budget, check=False)
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "budget_s": budget, "at": datetime.now(UTC).isoformat()}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "timeout_s": budget,
                "note": f"{name} exceeded its cycle budget and was stopped; its partial work is "
                        f"whatever it had already written",
                "at": datetime.now(UTC).isoformat()}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "at": datetime.now(UTC).isoformat()}


def execution_twin() -> dict:
    """`execution_twin`: what the fill WOULD have been, against what it was.

    UNSCHEDULED UNTIL NOW, found by `scripts/check_producer_schedules.py` -- which is the fence
    written today precisely because five organs had already been found this way by hand. Its
    artifact is currently HUMAN_READ, so being off the clock cost a stale report rather than a
    stopped chain; that is a smaller failure than the compiler's and it is the same failure.
    """
    return _producer("execution_twin", "research/execution_twin.py")


def model_skill() -> dict:
    """`model_self_improvement`: score every prediction the desk makes against a named baseline.

    SCHEDULED FROM THE HOUR IT WAS WRITTEN, because the alternative is the defect this whole file
    keeps finding: an organ that exists, is imported, is documented, and runs never. A skill score
    is also only useful as a SERIES -- one reading says whether the desk forecasts well today, an
    hourly track says whether it is getting better -- and a series needs a clock.

    Its non-zero exit is a VERDICT, not a cycle failure: it exits 2 while any predictor is
    unscored or beaten by its baseline, which is true today (the research forecast register scores
    -0.177 Brier skill against its own base rate over 537 resolved claims). `_producer` records
    the exit code and the cycle continues, which is the right shape -- a measurement organ must
    never be able to stop the desk by reporting bad news.
    """
    return _producer("model_self_improvement", "research/model_self_improvement.py")


def causal_graph() -> dict:
    """`world_causal_graph`: which driver moves which instrument, and in which regime.

    The heaviest of the three newly-scheduled analysis organs, and the one whose staleness matters
    most: `beta(rates -> gold)` is state-dependent, so a graph fitted weeks ago describes a world
    the book is no longer being held in.
    """
    return _producer("world_causal_graph", "research/world_causal_graph.py")


#: The worker name this cycle claims under. One name, so a lease abandoned by a crashed pass is
#: recoverable by the next one rather than orphaned under a per-run identifier.
QUEUE_WORKER = "hourly_cycle"


def _claim_one(kind: str) -> tuple[object | None, object | None, str]:
    """Lease the most valuable READY task of `kind`, or explain why nothing was claimed. I2.

    THE QUEUE HAD NO CONSUMER, WHICH MADE IT A LOG. `task_queue`, `worker`, `org`,
    `wiring_campaign` and `coverage_governor` are five tested modules forming one complete loop,
    `queue_cycle` gave them a clock, and still no leg ever called `claim()` -- so the journal grew,
    the census reported it, and the cycle went on running every leg in source order regardless of
    whether anything had happened. A queue nothing claims from is a list of regrets.

    Returns (queue, task, why). `task is None` is the ordinary case and is NOT a failure: it means
    nothing of this kind is ready, which is the whole point of running because something happened.
    """
    try:
        from libs.ops.task_queue import TaskQueue
    except Exception as exc:
        return None, None, f"task_queue unimportable ({type(exc).__name__})"
    path = BASE / "data" / "task_queue.jsonl"
    if not path.exists():
        return None, None, f"no queue journal at {path.name}; queue_cycle has not produced yet"
    try:
        q = TaskQueue(path)
        task = q.claim(QUEUE_WORKER, kinds=(kind,))
    except Exception as exc:
        return None, None, f"claim failed ({type(exc).__name__}: {str(exc)[:100]})"
    if task is None:
        return q, None, f"no READY {kind!r} task -- nothing to do, which is the point"
    return q, task, ""


def orthogonality() -> dict:
    """`orthogonality`: tail dependence between sleeves -- the correction the allocator sizes past.

    MOVED FROM DAILY TO HOURLY 2026-09-13, and the mismatch it closes is this: `pf_allocator`
    refreshes every pass and `EFFECTIVE_BREADTH` (the LINEAR n_eff it sizes on) refreshes hourly,
    while the TAIL correction -- the reading that says 3.31 effective bets are really 3.05 when it
    costs something -- ran once a day on MT5-FrontierAudit at 05:10. So the desk's tail-risk view
    was permanently up to a day behind its own sizing decisions.

    The day that became indefensible: the cure lane enrolled 120 clocks in one hour and the book
    went 129 -> 251, none of which a 17-hour-old dependence estimate could see.

    It costs 3.5 SECONDS measured on the box, so there was never a compute argument for daily --
    only that nobody had asked. It stays on the frontier audit too; running twice is free and the
    artifact is idempotent.

    IT PUBLISHES AND DOES NOT RESIZE. Nothing here feeds the allocator: a dependence estimate that
    silently shrank the book would be a growth cut with no missed-growth ledger line behind it.
    """
    return _producer("orthogonality", "research/orthogonality.py", "--apply")


def lake_promote() -> dict:
    """`lake_promote`: what share of the desk's own intelligence survives a point-in-time question.

    I7. `libs/data/lake.py` carried the whole bronze/silver/gold ladder and its refusal rules, and
    nothing on the tree ever called `promote` -- so the ladder was a schema. This leg climbs it
    with the intelligence corpus the compiler reads, and publishes the REFUSAL count.

    The refusals are the output, not the promotions. A promoter that fills a missing `event_time`
    with the ingestion time produces a lake in which every backtest passes and none of them mean
    anything, because every row then claims to have been knowable the moment it was scraped.

    FIRST REAL PASS: 2,416 bronze rows, ZERO reached silver, all refused for "no resolvable
    event_time". Not one row of the desk's own intelligence carries a stamp saying WHEN it could
    have been known. That is a fact about the corpus, it was invisible until something ran the
    ladder, and it bears directly on every claim built from these rows.
    """
    return _producer("lake_promote", "research/lake_promote.py")


def session_allocation() -> dict:
    """`session_allocation`: which HOURS the desk has an edge in, and which its capital sits idle.

    `pf_allocator` solves posterior E[log W] per SLEEVE and nothing solved it per SESSION, so the
    one dimension that decides whether capital works 24 hours had no measurement at all. It could
    not have had one: all 228 forward clocks answered "?" to which window they trade, while the
    answer sat in their own keys.

    FIRST PASS, and both findings were invisible until something ran it. `overlap` held 14.2% of
    deployed heat with ZERO clocks and ZERO forward trades -- capital sized into a window carrying
    no forward evidence. And seven of twenty-four UTC hours have no forward clock at all, which no
    amount of sizing can fix; only mechanisms hunted in those hours will.

    It also corrected an impression worth correcting: the book's Asia concentration is EARNED.
    exp_R 0.5384 +/- 0.0803 over 155 trades is a 6.7-sigma edge, so 61.5% of heat there is the
    allocator being right, not drifting. `london_am` at 0.1649 +/- 0.1474 is ~1.1 sigma and
    correctly gets nothing.

    MEASUREMENT ONLY. A second allocator stacked on pf_allocator would shrink twice, and growth
    governance Rule 1 requires any reduction to prove it raises robust forward E[log W]. The
    honest use of this artifact is ADDITIVE: it hands the research side a target list of idle
    hours to fill with NEW independent bets (Rule 2), never a reason to take heat off a window
    that is earning.
    """
    return _producer("session_allocation", "research/session_allocator.py")


def session_chart_expansion() -> dict:
    """`session_chart_expansion`: every proven mechanism, asked about every other hour and chart.

    STANDING RULE, not a one-off sweep. A mechanism certified in one session is a hypothesis
    about the other eight, and a mechanism certified on one chart is a hypothesis about the other
    six. Nothing on this desk ever asked either question, which is why seven of twenty-four UTC
    hours carried no forward clock and every scalp sleeve was `xau_*`.

    EVERY PARENT, NOT JUST THE ASIA ONES. The desk's certificates happen to be mostly Asia today;
    the rule is not. An NY mechanism gets its London and Asia equivalents on the same pass.

    HOURS ARE RANKED BY MEASURED COVERAGE, so the budget goes where there are no clocks rather
    than back into the session the desk already owns. The first run showed why that matters: at a
    cap of six it spent three slots re-hunting Asia and never reached ny_open or ny_mid at all.
    As London and NY fill, they stop being cheap and Asia becomes eligible again -- the loop
    closes rather than permanently condemning a session.

    IT PROPOSES AND NOTHING MORE. No certificate, no authority, no size: every variant clears the
    same ten gates as anything else on the docket. The cost is a real one -- each cell raises the
    deflated-Sharpe bar every other cell must clear -- and it is bounded per parent for that
    reason. 451 cells against a docket of 21,692 is a 2.1% rise in the trial count, spent on
    variants of mechanisms measured at 105.6 survivors per 1,000 ruled cells while `discovered`
    returns 2.0.
    """
    return _producer("session_chart_expansion", "research/session_chart_equivalents.py", "--apply")


def stamp_freshness() -> dict:
    """`stamp_freshness`: artifacts that are REWRITTEN but not RE-STAMPED.

    An organ rewrites its artifact every pass and leaves the timestamp inside it wherever it last
    landed. The file is fresh, the stamp is ancient, and every consumer that reads the stamp --
    which is most of them, because a file mtime is destroyed by a checkout or a sync -- is told
    the organ is dead.

    NO EXISTING CHECK COULD SEE IT. `organ_contract` and `never_stale` judge by FILE AGE, so a
    rewritten-but-unstamped artifact passes them cleanly; `build_zentech_state` reads the internal
    STAMP, so the dashboard shows it dead. Neither looks at both numbers, and the contradiction
    between them IS the finding.

    FIRST RUN: two. `shadow_state.json` rewritten 0.0h ago carrying a stamp 434.8h old -- the one
    artifact the forward lane's own health check reads, which is why heal_forward_lane had been
    reporting "engine last evaluated this row 434.1h ago" about rows evaluated minutes earlier.
    And `anomaly_cursor.json`, 41h of lag, which nobody had noticed at all.
    """
    return _producer("stamp_freshness", "scripts/check_stamp_freshness.py")


def fill_attribution() -> dict:
    """`fill_attribution`: why every order became a fill or did not. The BINDING stage.

    conversion_ledger picks the binding constraint by its own rule and the answer is not in
    research: order -> fill is 1.9%. 52 orders, 34 unfilled, 10 rejected, 1 filled. Breadth
    multiplied by a 1.9% fill rate is still 1.9%.

    NOTHING READ THE REASON CODES. order_intents.jsonl recorded a broker retcode per attempt and
    no artifact ever parsed them, so every statement about why orders do not fill was a guess
    standing beside a file that held the answer.

    It also names a defect nobody had: the two execution ledgers CANNOT be row-joined.
    fill_corpus carries intent_id and status, order_intents carries retcode and no intent_id, and
    the only shared field is ticket -- which is 0 on every rejection, so the rows that most need
    explaining are exactly the ones that cannot be joined.
    """
    return _producer("fill_attribution", "research/fill_attribution.py")


def cost_to_edge() -> dict:
    """`cost_to_edge`: what each live sleeve PAYS to trade, against what it earns.

    THE ENGINE MODELS NO SWAP. mt5desk.engine.Costs carries spread and commission and nothing
    else, so every certificate was judged with zero financing cost. For an intraday sleeve that
    is correct; for overnight_gap_decay, which holds through rollover BY CONSTRUCTION, the
    dominant cost was never charged.

    Measured on the four live overnight sleeves: GBPMXN 0.246R and GBPNOK 0.202R round trip
    against a +0.135R expectancy assumption -- cost exceeding the entire edge. EURUSD is 0.025R
    for scale, and all four carry the same parameter hash.
    """
    return _producer("cost_to_edge", "research/cost_to_edge.py")


def swap_rejudge() -> dict:
    """`swap_rejudge`: every certificate re-priced against the financing it was never charged.

    THE ENGINE NOW CHARGES SWAP (Costs.swap_per_lot_per_night, 2026-09-15) and that only protects
    certificates minted from now on. The 58 already holding forward clocks were judged by an
    engine that charged zero, so this re-prices each against the venue's published swap points and
    the nights its OWN ledger says its trades crossed -- mean, not median, because the number it
    is charged against is an expectancy and the trades that hold are part of it.

    Measured 2026-09-15 over 58: 57 SURVIVES, 1 AT_RISK, 0 COST_NEGATIVE. The book is Asia-session
    H1 and mostly exits before rollover; the worst is GBPJPY at 27.5% of its edge. That is the
    answer being cheap rather than the fence being loose -- the same pass on the four live
    overnight_gap_decay sleeves is where `cost_to_edge` finds cost exceeding the whole edge.
    """
    return _producer("swap_rejudge", "research/swap_rejudge.py")


def asia_plane() -> dict:
    """`asia_plane`: every Asian ground converted into gauntlet cells, or named as converting to
    none.

    THE RULE (principal, 2026-09-15): every ground the desk ever covers must have machinery that
    turns it into cells. Not a collector, not a dashboard tile -- CELLS, judged or explicitly
    blocked on a named feed. A source that reaches no gauntlet is indistinguishable from a source
    nobody added, and this desk has had both and could not tell them apart.

    The hard-data half of the Asian surface: 45 official, exchange, physical, flow, genome and
    alternative sources, kept apart from `deep_forest_miner`'s 502 PRACTITIONER grounds because a
    forum post and an SHFE warehouse receipt earn completely different treatment -- one mints a
    hypothesis, the other can settle one.

    Measured on its first pass: 45 sources -> 393 cells, 100% compiling as STRUCTURED_HYPOTHESIS,
    16 instruments, 0 unconverted grounds, 4 transports declared as carrying other sources rather
    than minting their own, and 16 declared targets NAMED as not quoted on this account.
    """
    return _producer("asia_plane", "research/asia_plane.py")


def sge_premium() -> dict:
    """`sge_premium`: the Shanghai gold premium, which is physical Chinese demand priced directly.

    BUILT, CORRECT, AND IDLE SINCE IT WAS WRITTEN (III.16, found 2026-09-15). The module declares
    `data/lake/sge_daily.parquet` and that file did not exist anywhere in the tree -- no clock
    ever ran it. On the first scheduled run it fetched a genuine SGE print and created the file.

    WHY IT MATTERS MORE THAN ITS SIZE SUGGESTS. SGE day sessions are 09:00-11:30 and 13:30-15:30
    Beijing, which is 01:00-03:30 and 05:30-07:30 UTC -- exactly the desk's ASIA window, where its
    gold clocks fire and where its strongest measured edge lives. In those hours Shanghai, not
    London, is the marginal physical venue for gold, and the desk had ZERO Chinese gold data
    wired. That is a hypothesis about the best thing the book owns, not a finding, and it has been
    untestable purely because nothing scheduled the fetch.

    It FAILS CLOSED by construction: no genuine SGE print means UNAVAILABLE, never an
    interpolation and never a proxy called SGE. The premium needs overlapping days and the rate
    leg publishes with a lag, so the series grows forward from the wiring date.
    """
    return _producer("sge_premium", "research/fetch_sge_premium.py")


def asia_collector() -> dict:
    """`asia_collector`: ONE generic collector for every registered source. No bespoke fetchers.

    THE LAW (principal, 2026-09-15): if any declared data is ever blocked because nobody wrote a
    collector for it, that is a FLAW. 750 of 774 Asia cells were BLOCKED_ON_DATA, each waiting on
    a fetcher nobody had written -- and writing 89 of them would rot at 89 different rates and
    guarantee the 90th source was blocked the day it was added.

    The registry already declares the address, the SHAPE, the cadence and what needs a key, so the
    collector is DRIVEN BY IT and a new source is collected the hour it is declared. Everything is
    vaulted point-in-time under its content hash; a 200 with the wrong shape is ROUTE_CHANGED (the
    NOAA failure), a missing key is UNCONFIGURED rather than a silent skip, and a robots DISALLOW
    is refused rather than worked around.

    Measured on its first pass, 85 sources: 43 NEEDS_PARSER (bytes on disk, parser downstream),
    25 HTTP_ERROR (real 404s naming URLs to correct), 12 UNCONFIGURED, 3 BLOCKED_BY_ROBOTS,
    1 UNREACHABLE, 1 ROUTE_CHANGED. Using certifi's CA bundle took UNREACHABLE from 26 to 1: the
    `self-signed certificate` failures were TLS interception on this host's egress, not broken
    government sites.
    """
    return _producer("asia_collector", "research/asia_collector.py")


def asia_parser() -> dict:
    """`asia_parser`: one parser bank keyed by payload SHAPE, not one per source.

    `asia_collector` vaulted bytes for 43 of 85 sources and every one sat at NEEDS_PARSER --
    fetched and read by nothing, the whole regional programme stalled one move short of a series.
    Writing 43 parsers would rot at 43 rates and block the 44th source, so the census decides the
    design: 40 of 44 payloads are HTML, 3 PDF, 1 JSON. One HTML parser covers forty.

    A table-less statistics portal is an INDEX, not a failure: its payload is the .csv/.xlsx links
    it points at, which go back to the collector as new addresses. Measured first pass: 14 PARSED,
    9 INDEX_PAGE, 21 NO_TABLE, and 63 endpoints handed back.
    """
    return _producer("asia_parser", "research/asia_parser.py")







def source_routes() -> dict:
    """`source_routes`: is each data endpoint still there, or has it moved and started lying?

    A MOVED ENDPOINT DOES NOT REPORT AN ERROR, IT REPORTS ABSENCE. This repo's own history: NOAA
    renamed CurrentSummaries.json to CurrentStorms.json, the old path answered with a 404 page as
    HTML behind HTTP 200, and the miner read it as "no active storms" with four hurricanes live.

    So the probe asks whether the body is still the SHAPE the caller declared, not merely whether
    something answered. HTTP 200 carrying HTML where JSON was declared is MOVED, and MOVED is the
    only fatal verdict -- an honest non-200 is loud and self-announcing.

    FIRST RUN: gld_holdings 404 (a written fetcher aimed at a dead URL) and dukascopy 503, while
    sge_quotations answers JSON -- so fetch_sge_premium is idle rather than broken. That
    distinction is the whole point, and nothing else on the desk could make it.
    """
    return _producer("source_routes", "scripts/check_source_routes.py")


def strategy_paths() -> dict:
    """`strategy_paths`: per-sleeve return paths on one common clock. Four capabilities wait on it.

    dependence_blindness reads 2.93x on a constructed clone book and ~1.0 on an independent one --
    the discriminator provably works -- and on the REAL book it was UNMEASURED because
    data/strategy_paths.json did not exist. Without it there is no real n_eff, no covariance
    denoising, no dependence-aware Monte Carlo, and no answer to whether 190 sleeves are 13 bets.

    I CONCLUDED THIS FILE COULD NOT BE BUILT, FROM THE ROW. The shadow row carries only summaries,
    so "the data was never recorded" is a reasonable inference and a false one: shadow_forward
    writes a per-sleeve LEDGER beside every row with entry_time, exit_time, r_multiple and a
    forward/historical flag, and 173 of them were already on disk. The paths were one directory
    over the whole time.

    Forward trades only, and one daily grid spanning every sleeve's window -- equal LENGTH is not
    alignment. The measurement needs 60 common marks and the window is 19, so it rebuilds hourly
    and becomes available on its own.
    """
    return _producer("strategy_paths", "research/strategy_paths.py")


def weak_signal_ensembles() -> dict:
    """`weak_signals`: combine the cells that failed ONLY on power. Selection's discard pile.

    THE DESK CERTIFIES INDIVIDUALLY AND THEREFORE THROWS AWAY ITS OWN RAW MATERIAL. Ten gates are
    applied to each cell alone; a cell that clears every validity gate -- pbo, cpcv, walk_forward,
    lockbox, reality_check_spa, stress_costs -- and fails only deflated_sharpe or expected_value
    is not refuted. It is a real effect measured on too few observations to clear a bar charging
    597 trials. Under selection it is a failure. Under combination it is the INPUT, because k
    weak members with low mutual correlation carry a t-stat growing with sqrt(k) while no member's
    own edge has to move.

    IT WAS BUILT AND NEVER RUN BY ANYTHING. 284 lines, zero clock references, and `power_deficient`
    read a `gates` field the gauntlet has never written, so it reported "0 combinations" on a
    docket holding 560 qualifying cells across 67 eligible symbols. Unwired AND silently empty is
    how a capability stays invisible: the artifact said there was nothing to do.
    """
    return _producer("weak_signals", "research/weak_signal_compiler.py")


def residual_factors() -> dict:
    """`residual_factors`: cross-sectional residuals, the family with candidates and no sleeves.

    786 residual candidates have been mined and ZERO residual sleeves are live; all 61 live
    sleeves are session, gap or carry. Left unrun, that zero reads as "residuals do not work on
    this venue" -- a conclusion the desk has never actually tested, because the engine that
    measures them has no clock. Running it makes the zero a MEASUREMENT instead of a silence.
    """
    return _producer("residual_factors", "research/factor_residual_engine.py")


def markout() -> dict:
    """`markout`: adverse selection in the desk's OWN fills. Are we the desperate party?

    The desk cannot take the other side of somebody's forced liquidation -- but it can detect
    when it is SUPPLYING one, and that is the same measurement read the other way round. A markout
    curve that runs consistently against the fill says this book is the liquidity being taken.

    WHAT IT CURRENTLY MEASURES IS ZERO, AND THE REASON IS THE FINDING. 282 decisions, 275 not
    taken, of which 274 are `release_identity_refused` -- refused before a price was ever computed,
    so there is no counterfactual to replay. The organ is sound and the ledger was empty because
    the identity fence was rejecting everything upstream of it. That fence is fixed; this accrues
    from here, which is exactly why it needs a clock rather than a one-off run.
    """
    return _producer("markout", "research/counterfactual_markout.py")


def exogenous_search() -> dict:
    """`exogenous_search`: the licensed absurd-variable lane, run under the sealed trial count.

    Most desks cannot afford undirected search because their multiple-testing correction is
    nominal. This one's is not: `n_trials` is a SEALED campaign constant (597) and the
    deflated-Sharpe charge is paid whatever the search looked at, so an exogenous variable with
    no economic story costs the same as one with a story and is judged by the same bar.

    A LANE THAT FINDS NOTHING STILL PAYS. "We looked across this budget and there was nothing"
    is a real answer and belongs in `negative_knowledge`; silence does not.
    """
    return _producer("exogenous_search", "research/unknown_unknowns.py")


def stop_reverse_census() -> dict:
    """`stop_reverse`: count the times one price level paid twice, and entries into a dislocation.

    NAMED SO IT BECOMES COUNTABLE, NOT SO IT BECOMES A RULE. On 2026-09-11 a 60-point M1 wick took
    a gold long's stop and, because the bracket's sell_stop sat at that level, opened a short at
    the same price in the SAME SECOND -- at the low tick. Price was fully back six minutes later.
    Two losses of ~72 EUR from one round trip that ended where it began.

    There is no OCO, no cooldown and no opposite-leg cancellation in the gateway, so a wick through
    a stop is structurally guaranteed to open the reverse at the worst tick. Three such events in
    thirty days, net -30.20 -- but ONE of them earned +42.08, so an OCO would have cost that too.
    Three is not a sample, and building the fix now would fit execution logic to a handful of
    minutes (L0330). This leg counts, so that a fourth and fifth make it evidence.
    """
    return _producer("stop_reverse", "research/stop_reverse_census.py")


def forward_reconcile_leg() -> dict:
    """`forward_reconcile`: retire orphan clocks EVERY HOUR, because they accrue every hour.

    A DAILY CADENCE COULD NOT KEEP UP AND THE SHORTFALL WAS INVISIBLE. `forward_reconcile` runs
    once a day as MT5-ForwardReconcile, and its whole log is two lines: 81 actions, then 167.
    Run by hand on 2026-09-14 it took 190 more -- {'IDENTITY_UNFROZEN': 42, 'RETIRED_ORPHAN':
    190} -- and the retirement count is CLIMBING pass over pass (40 -> 125 -> 190). Orphans are
    minted continuously: 17 certificates landed in one day and every re-key orphans the ledger
    row it replaced.

    WHAT THE BACKLOG COST. `heal_forward_lane` reported 186 STALLED rows, 183 of them
    STALE_ATTEMPT with "engine last evaluated this row 453.8h ago" -- nineteen days of rows that
    LOOKED alive, held a clock, and accrued nothing. Retiring the orphans took STALLED from 186
    to 4 in a single pass. The forward lane is the desk's only source of out-of-sample evidence,
    so a stalled row is not cosmetic: it is a certificate that can never mature.

    AND IT FAILS SOFT BY DESIGN, which is why the backlog was silent -- `run_forward_reconcile.cmd`
    says so in its own header: "unreadable enrolment disables retirement for the pass". A pass
    that retires nothing and a pass that had nothing to retire write the same log line. Hourly
    cadence does not fix that ambiguity; it bounds the damage to an hour instead of a day while
    the census below makes the backlog itself visible.
    """
    return _producer("forward_reconcile", "research/forward_reconcile.py")


def _recertify_canon_claimed() -> dict:
    """`recertify_canon`, but only for a window the queue says is actually uncovered."""
    q, task, why = _claim_one("recertify")
    if task is None:
        return {"status": "STOOD_DOWN", "why": why,
                "note": ("not a failure: the queue is the schedule now, and an empty queue means "
                         "no window is UNCOVERED. Running anyway would spend the hour proving it")}
    payload = getattr(task, "payload", {}) or {}
    res = _producer("recertify_canon", "scripts/recertify_canon.py")
    ok = res.get("exit_code") == 0
    try:
        if ok:
            q.complete(getattr(task, "id", ""), QUEUE_WORKER,
                       why=f"recertify_canon exit 0 for {payload.get('cell', '?')}")
        else:
            q.fail(getattr(task, "id", ""), QUEUE_WORKER,
                   why=f"recertify_canon exit {res.get('exit_code')}")
    except Exception as exc:
        res["queue_bookkeeping_error"] = f"{type(exc).__name__}: {exc}"
    return {**res, "claimed": {"id": getattr(task, "id", ""),
                               "cell": payload.get("cell"),
                               "priority": getattr(task, "priority", None),
                               "understatement": payload.get("understatement")}}


def research_exchange_score() -> dict:
    """`research_exchange score`: which external source's proposals actually became anything.

    G1, AND IT IS THE MEASUREMENT THAT MAKES THE SEATS ACCOUNTABLE. `data/panel_scorecard.json`
    has held thirteen providers at 0 scored / hit_rate null since 2026-07-17, which the scorer
    itself says in its own output -- so every allocation between sources so far was made on
    REPUTATION. The scorer walks the exchange ledger and turns that into proposed/dead/dup/built/
    live per source, which is the only thing that can replace reputation with a yield.

    It was scheduled by nothing. Wired here rather than as a VPS timer because this cycle is the
    clock that demonstrably runs, and a timer on a machine that is not adopting is a clock in
    name. It is cheap -- a ledger read and an arithmetic pass -- and it writes an EMPTY scoreboard
    with an explicit "nothing has ever been ingested" when the ledger is empty, which is the
    honest state rather than a fabricated one.
    """
    return _producer("research_exchange_score", "scripts/research_exchange.py", "score")


def alpha_rl() -> dict:
    """`alpha_rl_run`: the sequential alpha search, learning from the allocator's own marginals.

    G4 HAD EXISTED AND RUN NOWHERE. `libs/research/alpha_rl.py` carried a complete Q-learner over
    the alpha-construction MDP -- replay buffer, epsilon floor, and a reward that is the book's
    measured marginal dE[log W] -- and its own Tier-1 row said so: "SEQUENTIAL CONTROL NOW EXISTS
    AND IS MEASURED; NOTHING RUNS IT". That is III.16 stated in the ledger and left there.

    Billed like every other leg, and bounded: the runner takes a wall-clock budget and reports how
    many of the requested episodes it reached, so a slow host loses episodes rather than the hour.

    ITS REFUSALS ARE PUBLISHED, WHICH IS WHY IT IS WORTH RUNNING AT ALL. With no allocator
    artifact the reward is UNMEASURED and NO episode runs -- an empty table, said plainly, rather
    than a confident ranking of a fabrication. An episode whose completed spec the book has never
    valued is discarded whole rather than scored zero. The first real pass reported 291 rewarded
    against 509 unpriced and learned almost entirely at `family` depth, which is exactly the sort
    of thing a reader must be able to see before acting on a ranking.
    """
    return _producer("alpha_rl", "research/alpha_rl_run.py")


def compile_candidates() -> dict:
    """`miner_candidate_compiler`: every crawler row becomes a candidate or a deepening task.

    NOTHING SCHEDULED IT. Measured 2026-09-05 by cross-referencing the capability graph against
    every scheduler surface on this tree -- `ops/crontab.manifest`, the box task manifest,
    `research_supervisor.PERIODIC`, this cycle and `daily_cycle` -- the compiler is named by NONE
    of them. It is the fifth organ found this way today.

    AND IT IS THE ONE THAT MATTERS MOST FOR THE TEXT CHAIN. The compiler is the single step
    between what the crawlers fetch and what the gauntlet can judge: it reads every intelligence
    artifact, emits executable candidates for the structured rows and routes everything else to
    `miner_deepening_queue.json`. `deepening_worker` then drains that queue. So an unscheduled
    compiler means the deepening worker spends every hour re-reading a queue nobody refreshed,
    and every row the world crawler fetched after the last manual run sits unread for ever --
    which is exactly the shape of "the crawlers run and nothing converts".

    ORDER IS LOAD-BEARING and this is why the legs below were reordered. mine -> compile -> deepen:
    the miners fetch, the compiler turns what they fetched into candidates and tasks, and the
    worker reverse-engineers the tasks. Running deepen before compile -- which is what the cycle
    did -- works this hour's worker against last hour's queue, so a row fetched at 10:05 could not
    reach the gauntlet until 11:xx at the earliest and only if somebody had run the compiler by
    hand in between.
    """
    return _producer("miner_candidate_compiler", "research/miner_candidate_compiler.py")


def pit_canaries() -> dict:
    """`pit_canaries`: planted past/now/future rows read point-in-time every hour; green only
    when the future row is invisible at now (closed-loop `truth.pit_canaries_green`)."""
    return _producer("pit_canaries", "scripts/check_pit_canaries.py")


def mutation_yield() -> dict:
    """`mutation_yield`: certification fate joined back to the generator and operator that
    proposed each cell, rewriting data/generator_weights.json -- the compute reallocation the
    closed loop measures (`meta.compute_reallocated_from_outcomes`). It was written by nothing
    on a clock; the weights were two days stale."""
    return _producer("mutation_yield", "research/mutation_yield.py")


def candidate_conservation() -> dict:
    """`candidate_conservation`: every docket candidate accounted for -- judged, waiting or
    evicted with a reason -- written for the closed-loop attestation's `truth` block."""
    return _producer("candidate_conservation", "scripts/check_candidate_conservation.py")


def breadth_sweep() -> dict:
    """`breadth_sweep`: cells for every unbanned READY family on every chart the desk holds bars
    for, merged into the docket idempotently (principal 2026-09-16: the discovery hunt is banned;
    its volume goes to every other mechanism, all charts, not tons of H1)."""
    return _producer("breadth_sweep", "research/breadth_sweep.py", "--apply")


def search() -> dict:
    """`edge_search`: the family-free hypothesis search. NOT SCHEDULED ANYWHERE BEFORE THIS.

    THE DASHBOARD CALLED IT AN HOURLY LEG AND NOTHING MADE IT HOURLY, which is the third instance
    of this exact pattern found today after the deepening worker and the clock healer. Measured
    off the live dashboard 2026-09-05:

        SEARCH: edge_search_results.json is 37.7h old (hourly leg) -- the search has stopped
                producing; the docket is running on miners alone

    `research_supervisor.PERIODIC` lists fragility, the hunts, the macro desks and a dozen others;
    it does not list `edge_search`, and no cron row or box task installs it either. So the desk
    reported a stale hourly leg for a leg that had no schedule at all, and the docket had been
    running on miner rows alone for a day and a half.
    """
    # THE SEARCH MINTS ONLY `discovered` HYPOTHESES. While that family is banned
    # (data/banned_families.json, principal 2026-09-16) this leg stands down and its hour goes
    # to every other leg; lifting the ban is one edit to that file.
    try:
        from family_policy import ban_reason, family_banned
        if family_banned("discovered"):
            return {"status": "SKIPPED", "leg": "edge_search",
                    "why": f"{ban_reason('discovered')}; the search leg mints only discovered "
                           f"hypotheses, so its hour goes to the other legs"}
    except Exception:
        pass
    return _producer("edge_search", "research/edge_search.py")


def sweep() -> dict:
    """`orthogonal_sweep`: the non-directional family sweep. Same defect, same cure.

        SWEEP: orthogonal_candidates.json is 32.4h old (hourly leg) -- the sweep has stopped
               producing; the docket is running on miners alone

    This one matters disproportionately for the reason `family_inputs` records: carry and the
    other orthogonal mechanisms are the desk's only genuinely non-directional edges, and the
    book's binding constraint is orthogonality. A stalled sweep does not just slow discovery, it
    slows discovery of exactly the cells that would raise effective breadth.
    """
    return _producer("orthogonal_sweep", "research/orthogonal_sweep.py")


def frontier() -> dict:
    """One frontier-miner pass: which external capability is worth replicating next.

    RUN HERE RATHER THAN ON ITS OWN SCHEDULE, and the reason is this desk's most repeated defect
    rather than convenience: an organ with its own task is an organ whose task can be missing from
    the box, and `check_box_tasks` measured fourteen tasks whose cadence this repo cannot even
    verify. A leg of the cycle that already runs hourly and now records its own cost is the one
    place a new organ is certain to actually run.

    NEVER IDLE (mandate section 70): the pass works the standing capability gaps when no new
    external finding appears, so a quiet hour still advances the queue.
    """
    try:
        sys.path.insert(0, str(BASE))
        from frontier_intel import frontier_supervisor
        doc = frontier_supervisor.one_pass()
        return {"scouted": doc.get("rows_scouted"), "new": doc.get("new_candidates"),
                "queued": (doc.get("ranked") or {}).get("n_queued"),
                "missing_capabilities": doc.get("capability_matrix_missing"),
                "at": datetime.now(UTC).isoformat()}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "at": datetime.now(UTC).isoformat()}


def refresh_bars() -> dict:
    """BARS, EVERY HOUR, AT EVERY TIMEFRAME. This was a DAILY step and that was the whole bug.

    `refresh_tail` lived only in `daily_cycle`, so the best any series could be was 24h old -- and
    it globbed `*_H1.parquet`, so the sub-hourly series were refreshed by nothing at all.
    MEASURED 2026-09-06: XAUUSD_M5/_M15/_M1 held no bar after 2026-08-21 23:55 while the three
    gold scalp sleeves had been on their forward clock since 2026-08-22. They had zero bars for
    every day of that clock, which is the entire reason they sat at forward n=0.

    A sleeve cannot trade a bar that was never fetched, so this is upstream of every other leg
    here: mining, searching and judging on a stale chart all produce confident answers about a
    market that has moved on. It runs FIRST for that reason.

    Exit 2 is `refresh_tail`'s honest "no MT5 terminal on this box" and is not a failure -- the
    VPS has no terminal and must not report one.
    """
    out = _producer("refresh_tail", "scripts/refresh_tail.py")
    if out.get("exit_code") == 2:
        out["note"] = "no MT5 terminal on this host; bars are refreshed by the box that has one"
    return out


def deep_forest() -> dict:
    """The deep-forest miner: a DAILY organ promoted to hourly.

    It is one of the desk's few genuinely broad discovery surfaces, and running it once a day
    meant twenty-three hours in which a newly published mechanism could not be seen. Its own
    cursor makes repeat passes cheap when nothing new has landed, so hourly costs little and a
    quiet pass still advances the queue (mandate section 70, never idle).
    """
    return _producer("deep_forest_miner", "research/deep_forest_miner.py")


def publish_survivors() -> dict:
    """`survivor_publication`: seal certified survivors into runnable shadow specs.

    UNSCHEDULED ANYWHERE UNTIL NOW -- not a cron row, not a timer, not a box task. It was only
    ever called inline by whatever happened to import it, so certificates could be certified and
    then simply not published, which is indistinguishable downstream from never having certified.
    This is the step that turns a gate verdict into something the shadow lane can actually run.
    """
    return _producer("survivor_publication", "research/survivor_publication.py")


def publish_dashboard() -> dict:
    """Rebuild web/desk_state.json -- the file every dashboard reads.

    ALSO A DAILY STEP UNTIL NOW, which put a 24-hour floor under the board's freshness before any
    other staleness was even considered. A desk that publishes its state once a day cannot answer
    "is this current" with anything better than "within a day", and every tile inherits that.

    Runs LAST, after every leg that writes something it reads, so the published view reflects the
    pass that just happened rather than the one before it.
    """
    return _producer("build_zentech_state", "scripts/build_zentech_state.py")


def forecast_contract() -> dict:
    """P4: audit the belief register -- who published, and whose beliefs were unscoreable.

    Runs every hour rather than daily because its whole value is catching a model that has begun
    publishing malformed beliefs BEFORE a day of them accumulates. A refusal rate that climbs
    quietly is the shape this desk keeps missing.
    """
    return _producer("forecast_contract", "research/forecast_contract.py")


def model_league() -> dict:
    """P7 / P41 / P79: rank every model on dElog after compute and complexity rent.

    The league only ever compares models that faced the same window, horizon bucket, cost model
    and a comparable sample; everything else is reported INCOMPARABLE. It ranks results that the
    skill tracker already measured rather than re-measuring them, so it can never become a
    second, disagreeing source of truth about how a model performed.
    """
    return _producer("model_zoo", "research/model_zoo.py")


def adversaries() -> dict:
    """P48/P49/P58: poison canaries, silent-defect hunt, claim genealogy.

    HOURLY BECAUSE THE CANARY RATE IS A CONSTANT TO DEFEND, NOT A METRIC TO TREND. The moment it
    drops below 100% a gate has stopped gating, and every certificate issued since that moment is
    suspect -- so the interesting quantity is not the trend, it is how few certificates get issued
    between the break and its detection.
    """
    return _producer("adversary", "research/adversary.py")


def coverage_map() -> dict:
    """WHICH INDEPENDENT AXES THE SEARCH HAS ACTUALLY COVERED -- 1,435 lines that nothing ran.

    The desk's stated lever is "roughly twice as many genuinely independent sources of P&L", and
    three modules were written to measure exactly that: `alpha_breadth` (nominal against EFFECTIVE
    breadth, which is the number that matters when sleeves correlate), `regime_coverage` (where
    the book has no edge, with coordinates rather than "x% of heat is unfundable"), and
    `alpha_periodic_table` (mechanism coordinates -- who acts, why they must, what information
    changes, when, where it appears first).

    NOTHING IMPORTED ANY OF THEM. 432 + 591 + 412 lines, three working entrypoints, zero callers.
    Without this the research governor has no map: it can only chase whichever family last
    produced a good backtest, which is how a search gets stuck re-mining one axis while the other
    nine stay dark. Coverage is what makes breadth a measured quantity instead of a hope.

    THREE LEGS AND NOT ONE, because they answer different questions and fail independently -- a
    combined leg would hide which of the three stopped.
    """
    return _producer("alpha_breadth", "research/alpha_breadth.py")


def regime_coverage() -> dict:
    """Where the book has no edge, in coordinates research can act on. See `coverage_map`."""
    return _producer("regime_coverage", "research/regime_coverage.py")


def periodic_table() -> dict:
    """Mechanism coordinates for every candidate, so an unexplored cell is visible as a gap
    rather than as an absence nobody noticed. See `coverage_map`."""
    return _producer("alpha_periodic_table", "side_channels/alpha_periodic_table.py")


def brain_ab() -> dict:
    """Did a change to the desk's own search actually help, or did it only feel like it?

    THE LOOP THE DESK HAD WRITTEN AND NEVER RUN. Every structural change to the search -- surgical
    mutation, novelty V2, Thompson allocation, the adapter registry -- was argued for and shipped,
    and none was measured. `libs/research_os/brain_ab.py` was written on 2026-08-30 to settle
    exactly that, its own docstring says "the hourly loop looks at this every hour", and nothing
    ever called it. This is that call.

    IT IS ALREADY MORE CAREFUL THAN THE THING IT IS BEING COMPARED TO. Arms are assigned by a
    deterministic blake2b of the candidate id AT PROPOSAL TIME -- before any outcome exists -- so
    a re-run assigns identically and nothing can steer a promising candidate into the favoured
    arm. (`hash()` is salted per process; using it would silently reshuffle the arms on every
    restart, and every historical comparison would be reading a different experiment than it
    thought.) The test is always-valid rather than a fixed-n t-test, because a t-test peeked at
    hourly has a false-positive rate far above its nominal alpha.

    AND IT REFUSES THE TRAP THAT MAKES A/B HARNESSES LIE. The metric anyone would name -- forward
    survivors -- is 0/0 and has been for the desk's whole history; an A/B on a metric that is
    identically zero returns "no difference" forever while looking rigorous. So it reports on the
    deepest rung BOTH arms have data for, names the rung, and states that a win on a leading rung
    is not a win. Reading a leading-metric win as a terminal one is how a desk convinces itself it
    is improving while live P&L does nothing.
    """
    return _producer("brain_ab", "libs/research_os/brain_ab.py")


def wiring_audit() -> dict:
    """Census the modules nothing calls, every hour, and write it where the wirer can read it.

    THE DESK'S DOMINANT FAILURE MODE, and it has never had a clock. MEASURED 2026-09-10: 135
    library modules built and unreachable -- 128 with tests proving they work and nothing calling
    them, 32 in money-path trees, and 49 of the "one link short" kind where the only importer is a
    script nothing runs, so the orphan check reads green while the module is as dead as ever.

    HOURLY, NOT DAILY, because the box adopts hourly: a pass that lands new code is exactly when
    the answer changes, and a census taken then is measuring the tree that is actually running.
    The whole audit is an AST walk of the repo -- seconds -- and `_costed` records what it really
    takes, so if that stops being true the ledger says so rather than this comment.

    IT REPORTS AND NEVER REFUSES. A leg that failed the pass on finding an orphan would be removed
    within a week, correctly. `scripts/max_audit.check_unwired_modules` is the gate and stays the
    gate; this is the evidence feed.
    """
    return _producer("wiring_audit", "libs/ops/wiring_audit.py")


def microstructure_census() -> dict:
    """WHICH MICROSTRUCTURE CONSTRUCTIONS THIS VENUE CAN EXPRESS AT ALL, and what blocks each.

    THE MEASUREMENT THAT DECIDES HALF OF THEM has been in the repo since 2026-08-17 and nothing
    ever read it: `data/tape/depth_probe.json` probed 22 symbols and found `levels: 0` on every
    one -- FX majors, gold, silver, both crypto CFDs. Fusion publishes no depth of market. So
    queue position, true order-flow imbalance, microprice from sizes, depth convexity, absorption
    and iceberg inference are not backlog on this desk; they are UNBUILDABLE on this venue, and
    building them on a book synthesised from bid/ask would model the synthesis.

    THE OTHER HALF IS FULLY AVAILABLE AND STARVED. Everything that needs the ORDER and TIMING of
    quote revisions rather than resting size -- effective spread at a latency, post-fill mid
    drift, realised spread, quote burstiness, the true intrabar path, the realised/bipower split
    -- is computable from `copy_ticks_from(COPY_TICKS_ALL)`, which this desk already records.

    IT IS THE SEPARATION THAT IS THE POINT. Collapsing STARVED into UNBUILDABLE is how a desk
    stops working on the half it could fix today; the reverse is how it spends a quarter modelling
    a synthesised book. The headline scores LIVE against REACHABLE so a broker with no order book
    costs this desk nothing it could have earned.
    """
    return _producer("microstructure_census", "libs/research/microstructure_census.py")


def tape_features() -> dict:
    """THE BRIDGE FROM TICKS TO EVERY CONSUMER, and its output has never reached origin.

    `recorders/tape_features.py` converts the recorded tick tape into the four artifacts the desk
    already reads: the silver tape the `liquidity_regime` and `orderflow_imbalance` families are
    starved of, `data/cost_surface_tick.json` (byte-compatible with the bar surface's schema, so
    `cost_surface.spread_pts` reads it verbatim), `data/tape/slippage_surface.json` (the execution
    twin's prior, computable from ticks WITHOUT a single fill), and the M1..D1 intrabar stack.

    IT IS ALREADY SCHEDULED AND ITS OUTPUT HAS NEVER ARRIVED. `recorders/install_tape_tasks.ps1`
    registers `MT5-TapeFeatures` hourly at :20. All three of its JSON outputs live under
    `desks/mt5/data/`, which `libs/ops/release.STATE_PREFIXES` makes a path the box COMMITS AND
    PUSHES, and none of them is gitignored -- so had any machine ever written one, the next adopt
    would have carried it here. None is here. Either the installer was never run on this box or
    the task fails silently, and from a research container with no SSH those are indistinguishable.

    A LEG SETTLES IT EITHER WAY. Run from the hourly cycle it no longer depends on a separately
    installed task nobody verified, and `_costed` records what it really takes and what it
    returns. `microstructure_census` measures 9 of its 12 fixable constructions blocked behind
    exactly this hop.

    ON A RESEARCH BOX IT FINDS NO TAPE AND SAYS SO, which is the correct outcome there rather
    than a failure: the ticks are recorded where the terminal is.
    """
    return _producer("tape_features", "recorders/tape_features.py", ("--days", "10"))


def futures_lead_lag() -> dict:
    """THE CLOCK THE DESK'S BARS ARE ON, measured against a venue whose clock cannot be wrong.

    THE QUESTION WAS SUPPOSED TO BE A LEAD. `alpha_breadth` reports `cross_asset_lead_lag` EMPTY
    IN BOTH the traded and the certified book, and its written brief names the payer: gold's price
    is made on COMEX, in a contract this desk can see and does not trade. The first run answered
    with a contemporaneous correlation of 0.10 and a spike three bars out. Two series on the same
    metal cannot correlate 0.10 within the hour -- that was a CLOCK, and chasing it as a lead
    would have certified a sleeve that traded a timezone.

    MEASURED 2026-09-10, per DST season, on 10,598 overlapping hours:

        summer +3h   winter +2h     lag-0 correlation 0.978 (gold), 0.989 (silver)

    The H1 parquet index is BROKER time carrying a UTC tzinfo. `data/broker_clock_measured.json`
    infers the offset from the diurnal shape of tick volume and records, on all ten symbols,
    `offset_by_trough: 2` against `offset_by_peak: 3` -- a disagreement it cannot settle, storing
    the trough's answer as ONE scalar. BOTH READINGS WERE RIGHT, in different seasons, so a scalar
    is wrong for half of every year. This is a third and much stronger method: it aligns actual
    returns against stamps that are epoch seconds and therefore UTC by definition.

    THAT HOUR IS SPENT BY EVERY JOIN FROM A TRUE-UTC SOURCE -- the event lane's filing acceptance
    times, the macro calendar, this feed. At H1 an hour is the whole bar.

    AND THE ORIGINAL QUESTION GETS A CLEAN NULL. With the per-season offsets applied, every lag
    but zero is noise (|corr| < 0.04): COMEX and the CFD price the metal in the same hour, and
    neither predicts the other's next one. `cross_asset_lead_lag` is not fillable by this pair at
    H1, and saying so is worth more than a spike that was a timezone.
    """
    return _producer("futures_lead_lag", "research/futures_lead_lag.py")


def edges_macro_fusion_sweep() -> dict:
    """THE EDGE LIBRARY RE-RANKED AT THE COST THE ACCOUNT ACTUALLY CHARGES.

    IT DIED AT IMPORT AND THAT IS WHY IT WAS NEVER WIRED. Four of the twelve families it was
    written against no longer exist on `mt5desk.families`, so the module raised AttributeError on
    the way in -- before any scheduler could have reached it. Two were unambiguous renames and
    are mapped; two are genuinely gone and are DROPPED AND NAMED rather than replaced with the
    nearest-looking family, because substituting one mechanism under another's name is how a
    sweep reports a result for a strategy nobody ran.

    WHAT IT SAYS, first run 2026-09-10, 10 families x 4 symbols x 3 cost regimes:

        WIDE   3 of 36 cells clear the t >= 1.96 screening bar
        RAW    9 of 36
        ZERO  10 of 36

    Every earlier sweep on this desk used `Costs.from_symbol(meta, mult=2.0)` -- WIDE -- which
    this module's own header calls "roughly five times the real cost on gold" on a
    raw-spread/commission account. Pricing the account correctly TRIPLES the candidate flow.

    AND THE RESULT IS NOT AN ARTIFACT OF THE OPTIMISTIC BOUND: ZERO returns 10 against RAW's 9,
    so RAW captures nearly all of it. A family that only worked at ZERO would be visible as
    exactly that, which is the reason all three are reported side by side rather than argued over.

    STAGE-A RANKING ONLY, and the module says so: "cheaper costs make more candidates rank; they
    do not make a ranked candidate an edge. Only forward evidence in a confirmation slot does."
    """
    return _producer("edges_macro_fusion_sweep", "research/run_edges_macro_fusion_sweep.py")


def cost_construction() -> dict:
    """WHERE A COST OBJECT IS BUILT BY HAND, and the two unit traps that live there.

    `engine.Costs.from_symbol` is the only correct constructor. It closes `quote_per_account` --
    absent, commission stays in ACCOUNT CURRENCY and is divided by contract_size as if it were
    PRICE, "184x too little on the JPY crosses where this desk's surviving edges actually live,
    in the direction that manufactures survivors" -- and it takes the per-SIDE commission rather
    than a round-turn figure in a per-side field. 113 sites build a Costs some other way.

    THREE WERE ON A SCHEDULE AND ARE FIXED (exit_study, run_hunt12, full_pipeline); this leg is
    what fails the day a fourth appears. It also tracks the five off-clock sites that stress a
    CONTRACTUAL commission, which widens a number that does not widen.

    IT FIXES NOTHING. Rewriting two dozen money-path call sites blind, to chase a trap that only
    bites non-account-currency quotes, is how one bug becomes two dozen.
    """
    return _producer("cost_construction", "scripts/check_cost_construction.py")


def fusion_cost() -> dict:
    """WHAT A FUSION ZERO ACCOUNT ACTUALLY CHARGES -- commission per lot, and a residual spread.

    MEASURED 2026-09-10: over the 161 symbols whose stored spread can be checked against their own
    bars, COMMISSION IS A MEDIAN 96% OF THE RAW-REGIME ROUND TRIP. Fusion Zero's published
    contract is USD 2.25 per lot per side; it is contractual, identical on every symbol, and it
    does not widen under stress. The spread this desk keeps arguing about is the other four
    percent -- and the stored spreads are wrong in BOTH directions:

        OVER   BlockInc 500x its own bars, USDRUB 34.8x, GBPCHF 23.6x, NZDJPY 9.8x, +2
        UNDER  six symbols billed ZERO against bars quoting a positive spread every hour

    The six over-charged sit outside even the 3x their own `stress_costs` gate tested, so nothing
    on them can pass the gauntlet. That is a Rule 2 breach -- a real opportunity suppressed by a
    broken number -- and it is the exact mirror of the six billed nothing at all.

    RAW IS THE DEFAULT AND ZERO IS NOT. `run_edges_macro_fusion_sweep` defined these three regimes
    and said in its own words that ZERO is "a BOUND, not because any account fills at it".
    Defaulting to it would make every backtest better in the one direction the desk's guards exist
    to prevent, so all three are published and none is chosen for a live decision here.

    IT REWRITES NO REGISTRY. `median_spread_pts` is a money-path field: changing it re-judges every
    certificate priced against it and rebases the forward clocks.
    """
    return _producer("fusion_cost", "libs/portfolio/fusion_cost.py")


def time_joins() -> dict:
    """WHERE AN EXTERNAL TIMESTAMP MEETS A BAR INDEX, and whether anything says which clock.

    ONE BUG OF THIS CLASS WAS FOUND ON 2026-09-10 and it was invisible at the call site: the code
    read correctly, the types lined up, the tzinfo said UTC, and `family_event_reaction` entered
    two to three hours BEFORE the news because the bar index is broker time under a UTC tzinfo. A
    defect that quiet is rarely alone, so the sites are enumerated rather than guessed at.

    IT FIXES NOTHING, DELIBERATELY. Which frame a source is on is a fact about THAT SOURCE, and
    guessing it is the original error repeated at scale. UNDECLARED is not a bug -- it is a site
    where nobody reading the code can tell a correct join from one that is three hours early.

    AND IT IS TUNED FOR PRECISION OVER RECALL, because a census nobody reads changes nothing. The
    first version reported 75 sites by matching any external word within forty lines, including
    `encode_quantile` and `realized_variation`, both purely internal. Requiring the external name
    in the JOIN'S OWN EXPRESSION leaves four, and a test fails if that count ever exceeds twenty.
    """
    return _producer("time_joins", "scripts/check_time_joins.py")


#: The FRED archive is refreshed when older than this. FRED publishes daily series once a day
#: (VIX and the 10-year in the evening, the dollar index with a lag), so six hours keeps the
#: macro state at most a print behind without asking the API for the same file 24 times.
FRED_REFRESH_S = 6 * 3600


def fred_macro() -> dict:
    """KEEP THE MACRO STATE FRESH. The archive was 14 days stale on 2026-09-16, and nothing
    scheduled the collector on the box that trades.

    `data/fred_macro.json` is read by three organs that size capital -- `mt5desk.macro_view`
    (per-order lean), `libs.portfolio.macro_state` (the allocator's regime kernel) and
    `libs.portfolio.leg_factors` (the VIX and 10-year change factors) -- and by
    `orthogonal_sweep._macro_series` on the research side. It was written only by a VPS pipeline
    and a manual run. Freshness decays every one of those consumers toward "no claim" by design,
    so a stale archive silently switched the macro layer off. This leg runs the collector when
    the archive is older than `FRED_REFRESH_S` (it needs `data/secrets/fred.json`; without it the
    collector says so and exits 0) and rebuilds `reports/MACRO_VIEW.json` from whatever is there.
    """
    arch = REPO / "data" / "fred_macro.json"
    age = time.time() - arch.stat().st_mtime if arch.exists() else float("inf")
    if age < FRED_REFRESH_S:
        out: dict = {"status": "FRESH", "age_h": round(age / 3600.0, 2),
                     "at": datetime.now(UTC).isoformat()}
    else:
        out = _producer("fred_macro", "scripts/collect_fred_macro.py")
        out["age_h_before"] = (round(age / 3600.0, 2) if age != float("inf") else None)
    try:
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from mt5desk import macro_view as _mv
        _mv.main()
        out["macro_view"] = "rebuilt"
    except Exception as exc:
        out["macro_view"] = f"not rebuilt: {type(exc).__name__}: {exc}"
    return out


def allocator_join() -> dict:
    """DOES THE ALLOCATOR'S BOOK REACH THE SLEEVES IT FUNDS? It did not, and nothing said so.

    `pf_allocation.json` names a sleeve `CHFNOK_carry_asia` and `sleeves.json` names the same
    sleeve `chfnok_carry_asia_p_98d7`. The gateway joined them by raw name, so across 40 LIVE
    rows the intersection was 1 with the dynamic book and 0 with the fallback -- every sleeve read
    `from_book = False` and was sized at `clamp_risk_frac`'s BASE_RISK_FRAC floor. The optimiser,
    the baseline contest, the proof certificate and the heat budget all arrived at the venue as
    one flat fraction, and a sleeve at forward +1.77R was sized like one at -0.574R.

    Every artifact looked correct throughout, which is why this is a scheduled fence and not a
    note: a join that empties is invisible in logs and fatal to allocation.
    """
    return _producer("allocator_join", "scripts/check_allocator_join.py")


def spread_provenance() -> dict:
    """WHERE THE COST EVERY BACKTEST CHARGES CAME FROM -- for 145 of 195 symbols, nothing says.

    `mt5desk/engine.py:124` bills `universe.json -> median_spread_pts` on every replay, gauntlet
    stage and certificate. THREE producers write that field with three different meanings:
    `fetch_universe` stores the median of the H1 spread column, `expand_universe` and
    `download_all_symbols` store `symbol_info.spread`, a point-in-time snapshot that is not a
    median at all. `universe_registry` has named this since it was written -- "EURUSD reads 12
    under one producer and 0 under the next" -- and 199 of 251 rows still carry no provenance.

    THE COST OF NOT KNOWING IS NOT ABSTRACT. `execution_cost` priced ZERO of 76 sleeves on
    2026-09-07 for exactly this reason, and `entry_timing`'s first pass read the same ambiguity as
    a 30x under-charge on eight EURCHF certificates that were fine. An unattributable number is
    worse than a missing one: it is confidently wrong in both directions.

    REPORT ONLY, DELIBERATELY, and the module author's own docstring is why: `--apply` "rewrites
    the number every backtest, gauntlet verdict and certificate is priced against, and the clocks
    rebase on the next pass". That is a decision a person takes, not an hourly leg. What the leg
    buys is that the gap stops being invisible -- it is measured every hour, on the machine that
    HAS the bars, and `repair_universe_spreads.py --apply` is one command away when someone wants
    it. The script already counts and names every symbol the repair would make CHEAPER, which is
    the shape of a desk talking itself into an edge; today that count is zero.
    """
    return _producer("spread_provenance", "scripts/repair_universe_spreads.py")


def entry_timing() -> dict:
    """WHAT THE BACKTEST CHARGED FOR SPREAD AGAINST WHAT THE TAPE MEASURED, at the firing hours.

    MEASURED 2026-09-10 on the live canon: 15 of 66 certificates can fire in an hour whose
    measured spread is more than THREE TIMES what the backtest was billed -- the multiple their
    own `stress_costs` gate ran at. EURCHF at 30x, AUDCAD at 17x, CADJPY at 10x. Six symbols are
    charged ZERO spread. Both numbers come from artifacts the desk has held for weeks:
    `universe.json -> median_spread_pts` is what `mt5desk/engine.py:124` bills, and
    `cost_surface.json -> hours[H].p50` is what the bars measured.

    IT SETS NO BAR OF ITS OWN. The comparison is against each cell's existing 3x stress gate, so
    this is a check on a test that already ran rather than a second hurdle nobody agreed to.

    AND IT NEVER REFUSES A TRADE. The entry window is priced, the uncovered cells are named, and
    `queue_cycle` raises each one as a `recertify` task owned by the validation role. A cell
    judged at the wrong cost gets judged again at the right one; it does not get vetoed here on
    evidence no gauntlet has weighed.
    """
    return _producer("entry_timing", "research/entry_timing.py")


def queue_cycle() -> dict:
    """THE QUEUE'S CLOCK -- five modules that formed a complete loop and were never instantiated.

    MEASURED 2026-09-10, by grepping the repo for the constructor:

        grep -rn 'TaskQueue(' --include=*.py . | grep -v tests   ->   no results

    `task_queue` (durable journal, leases, bounded attempts), `worker` (claim, capacity), `org`
    (roles, escalation to a human inbox), `wiring_campaign` (producer) and `coverage_governor`
    (producer) are all tested and were all dead: nothing on this desk had ever opened the file
    they share. That is the defect `wiring_audit` exists to find, occurring for the second time
    in the modules written to fix it -- the first time was fixed by wiring the audit, and this
    fixes it by giving the queue a clock.

    IT RUNS AFTER THE COVERAGE LEGS BECAUSE IT READS THEM. `coverage_governor` aims the search at
    the mechanism clusters with no bet in them, and it reads `EFFECTIVE_BREADTH.json` to know
    which those are. Run before `alpha_breadth`, it would aim this hour's search using last
    hour's map -- which is survivable, and still wrong on the hour a cluster stops being empty.

    WHAT IT PUBLISHES IS THE HALF OF ALERTING THAT NEEDS NO CHANNEL. `needs_a_person` counts the
    tasks that exhausted their attempts, were escalated up the chart, and reached a role that
    answers to nobody. A non-empty inbox is the desk asking for a decision. It has been possible
    for that to happen silently for as long as the queue has existed, because nothing read it.

    IT QUEUES AND NEVER EXECUTES. A `wire` task is a choice of consumer and call site, some of it
    on money paths; queueing the decision with its evidence attached is the automation that can be
    audited afterwards.
    """
    return _producer("queue_cycle", "libs/ops/queue_cycle.py")


def issue_board() -> dict:
    """Every issue the desk can see, aggregated -- and the safe ones repaired.

    Runs with --apply. A detector that reports and never acts is this desk's most repeated defect
    class: `monitor_mt5_shadow_sync` returned FAILED every thirty minutes for ten days into a
    timer whose exit code nobody reads. Only idempotent, cheap, reversible repairs are automated;
    anything touching capital, a gate or a merge is refused with its reason.
    """
    return _producer("issue_board", "research/issue_board.py", ("--apply",))


def queue_compact() -> dict:
    """Keep the research queue streamable: archive terminal rows older than a fortnight.

    Compaction is the maintenance half of the streaming fix. Streaming makes a large queue cheap
    to READ; compaction stops it growing without bound in the first place. Nothing is deleted --
    a queue that forgets what it tried will try it again, which on this desk means spending the
    multiplicity budget twice on one hypothesis.
    """
    return _producer("queue_store", "research/queue_store.py", ("--compact",))


def rebalance_trigger() -> dict:
    """P3/P35/P73: when a rebalance is worth its cost, whether the RL may run, exit domains."""
    return _producer("rebalance_trigger", "research/rebalance_trigger.py")


def edge_confidence() -> dict:
    """Size on the edge's LOWER BOUND, and stress k_eff toward crisis correlation.

    Both adjustments only ever reduce size. They sit above the 20% nominal heat floor, which is
    a floor and is never reduced by anything here -- this decides how far ABOVE the floor the
    evidence justifies going, and the answer is often "not far".
    """
    return _producer("edge_confidence", "research/edge_confidence.py")


def research_org() -> dict:
    """P53/P54/P60/P62: role separation, agent reputation, borrowed methods, the implementer.

    Runs hourly because role separation is only a control if it is checked at the moment a review
    opens; a conflict discovered in a weekly audit is a conflict that already shipped.
    """
    return _producer("research_org", "research/research_org.py")


def experiment_design() -> dict:
    """P18/P19/P65/P29/P30: which experiment is worth running, and at what capital.

    The EVSI queue is recomputed hourly because its inputs move: an experiment that could not
    change the decision last hour becomes decisive the moment the decision it feeds changes.
    """
    return _producer("experiment_design", "research/experiment_design.py")


def market_intel() -> dict:
    """P14/P16/P17/P23/P24/P26: what changed, what it looked like last time, what followed.

    Every retrieval here is PAST-ONLY by construction. A neighbour drawn from after the query
    window is tomorrow, and an answer built on tomorrow is perfect and unreachable.
    """
    return _producer("market_intelligence", "research/market_intelligence.py")


def ml_layer() -> dict:
    """P6/P8/P9/P42: representation, self-supervision, mixture of experts, distillation.

    CHALLENGER-ONLY. Everything here publishes beliefs through the forecast contract and owns no
    position; the capital allocator decides money. A model the desk has not learned to trust can
    therefore be run every hour at no risk, which is the only way it ever earns trust.
    """
    return _producer("ml_layer", "research/ml_layer.py")


def experiment_cache() -> dict:
    """P39/P40: cache hit rate, hours saved, and whether the next increment buys anything."""
    return _producer("experiment_cache", "research/experiment_cache.py")


def opportunity_gap() -> dict:
    """P66/P81/P50: where the chain from 'an edge exists' to 'the book earns it' actually stops.

    Runs AFTER the publication legs, because it reads the state they write. A decomposition
    computed from last hour's artifacts would name last hour's binding constraint, and the whole
    value of the number is that it points at what to do NEXT.
    """
    return _producer("opportunity_gap", "research/opportunity_gap.py")


def maintain_miners() -> dict:
    """The miner/seat maintainer: run all six fences and REPAIR what is repairable.

    Recovered 2026-09-06 from `claude/tier1-batch`, where it had been written and then stranded --
    never merged, so nothing on any branch that runs could reach it. The principal asked for a
    standing local fixer for the miners; it existed as a file and as no schedule at all, which is
    this desk's most repeated defect class and the exact thing the file itself was written to fix.

    Hourly rather than three-hourly because its cheapest repair -- clearing a lock whose owner is
    gone -- starves the next run for up to 45 minutes while it waits, so a three-hour clock can
    leave a miner idle for most of a shift over a fault that takes milliseconds to clear.
    """
    return _producer("miner_maintenance", "scripts/run_miner_maintenance.py")


def refresh_regime() -> dict:
    """Refresh from native ledgers only; never overwrite authority from a VPS mirror."""
    if sys.platform != "win32":
        return {"status": "SKIPPED", "why": "regime authority belongs to the native Windows desk"}
    return _producer("regime_monitor", "research/regime_monitor.py")


def main() -> None:
    _plan_words = {"core": "core legs only", "heavy": "research producers only"}
    if HOURLY_PLAN.startswith("dept:"):
        _plan_words[HOURLY_PLAN] = f"department {HOURLY_PLAN.split(':', 1)[1]} only"
    print(f"hourly cycle plan={HOURLY_PLAN} ({_plan_words.get(HOURLY_PLAN, 'every leg')})",
          flush=True)
    # BARS FIRST. Every leg below reasons about a chart, so a stale chart makes all of them
    # confidently wrong rather than merely late.
    rb = _costed("refresh_bars", refresh_bars)
    smoke = _costed("smoke_release", smoke_release)
    h = _costed("health", health)
    t = _costed("record_tape", record_tape)
    s = _costed("state_vector", state_vector)
    rg = _costed("regime_monitor", refresh_regime)
    d = _costed("daily", daily)
    hc = _costed("heal_clocks", heal_clocks)
    wa = _costed("wiring_audit", wiring_audit)
    ab = _costed("brain_ab", brain_ab)
    cm = _costed("alpha_breadth", coverage_map)
    # DEPTH, HOURLY (2026-09-16). alpha_evolution ran once a day with a 1500 s budget; the
    # docket it feeds is judged every ten minutes now, so the generator runs every hour with
    # a bounded budget and its IC pre-screen keeps unstable expressions off the docket.
    # THE BANDIT HAS AUTHORITY HERE (2026-09-16): the seconds this leg spends are its base
    # budget scaled by the bandit's share of the arms it serves (research_budget), recorded in
    # reports/RESEARCH_BUDGET.json so the attestation reads an obeyed price, not a printed one.
    _aev_s, _aev_rec = _bandit_budget("alpha_evolution", 240)
    aev = _costed("alpha_evolution", lambda: _producer("alpha_evolution",
                                                        "research/alpha_evolution.py",
                                                        "--budget-s", str(_aev_s)))
    # The closed-loop attestation: every flag derived from another organ's artifact.
    clp = _costed("closed_loop", lambda: _producer("closed_loop", "scripts/check_closed_loop.py"))
    rc = _costed("regime_coverage", regime_coverage)
    pt = _costed("alpha_periodic_table", periodic_table)
    mx = _costed("microstructure_census", microstructure_census)
    sp = _costed("spread_provenance", spread_provenance)
    tf = _costed("tape_features", tape_features)
    fll = _costed("futures_lead_lag", futures_lead_lag)
    tj = _costed("time_joins", time_joins)
    aj = _costed("allocator_join", allocator_join)
    # BEFORE pf_allocator, which conditions on the state this refreshes.
    fm = _costed("fred_macro", fred_macro)
    fzc = _costed("fusion_cost", fusion_cost)
    cxc = _costed("cost_construction", cost_construction)
    emf = _costed("edges_macro_fusion_sweep", edges_macro_fusion_sweep)
    # BEFORE queue_cycle, which turns its uncovered cells into owned recertification tasks.
    ety = _costed("entry_timing", entry_timing)
    # AFTER the coverage legs: the governor aims the search from the map they just published.
    qcy = _costed("queue_cycle", queue_cycle)
    # THE OTHER HALF OF THE SAME LEDGER. A certificate whose `shadow_spec.params` is None passed
    # all ten gates and can never be run: the parameterisation that passed was never recorded, so
    # there is nothing to replay. The issue board offers `survivor_publication` as the repair and
    # marks the row AUTO-REPAIRABLE -- but that organ can only publish parameters a gauntlet run
    # WROTE, so it ran hourly for weeks against six certificates it was structurally unable to
    # help. A fixer that cannot fix what it is offered for turns a standing defect into a line
    # everyone scrolls past.
    #
    # Re-testing is the only honest recovery, and it is cheap. Requeueing does not revoke the
    # certificate or invent parameters: the existing one stands until a new run replaces it, and
    # a re-run that fails the gates is the correct answer to a claim the desk could never execute.
    rq = _costed("requeue_unrunnable", lambda: _producer(
        "requeue_unrunnable", "research/requeue_unrunnable.py", "--apply"))
    # DUPLICATES REMOVED EVERY HOUR, WHICH IS ALSO THE DISK FIX. The discovery files are
    # append-only by construction: every miner pass writes a new timestamped file knowing nothing
    # about what earlier passes already wrote, so identical rows accumulate forever. Measured
    # 2026-09-07: trading_latam 3,003 rows of which 3,003 are exact repeats, seasonality 97%,
    # regional_survivors 77%, and 1,629 discovery files whose every row already existed.
    #
    # That is the same fact as the box sitting at 0.8 GB free -- and a full disk is not reported
    # as a full disk: a push dies as "the remote end hung up unexpectedly", a parquet write
    # truncates, a tape append loses what it could not flush. One cause, three subsystems blamed.
    #
    # Deduplicated on a hash of the row's own JSON, never on the economic key: a raw miner row
    # has no family or symbol yet, so `_mechanism_key` would call 36,982 different swap rows
    # identical and delete 36,981 of them. `data/tape` is excluded by resolved path at every
    # threshold -- a tick nobody recorded cannot be re-downloaded.
    dd = _costed("reclaim_disk", lambda: _producer(
        "reclaim_disk", "scripts/reclaim_disk.py", "--apply"))
    # THE CONVERSION CHAIN, IN THE ORDER IT CONVERTS. mine fetches, compile turns what was fetched
    # into candidates and deepening tasks, deepen reverse-engineers the tasks that are not yet
    # rules. The cycle previously ran deepen BEFORE mine and never ran compile at all, so the
    # worker spent every hour on a queue nobody had refreshed and anything the crawlers fetched
    # after the last manual compile was unread for ever.
    # THE MOAT, AS A PRODUCER. It runs immediately before `mine` so its rows are in
    # data/hypotheses/ when `compile_candidates` merges the docket in this same pass -- a
    # producer whose output arrives after its consumer has run is a producer nobody reads, which
    # is the defect this file has now recorded three times.
    mo = _costed("moat_miner", lambda: _producer("moat_miner", "research/moat_miner.py"))
    m = _costed("mine", mine)
    se = _costed("search", search)
    bs = _costed("breadth_sweep", breadth_sweep)
    ccv = _costed("candidate_conservation", candidate_conservation)
    pcn = _costed("pit_canaries", pit_canaries)
    myd = _costed("mutation_yield", mutation_yield)
    # DELAYED TRUTH (principal F12, 2026-09-12; wired 2026-09-16): realised R credited back
    # to the scientist that proposed each cell, live when the live ledger is thick enough,
    # forward otherwise and labelled. The bandit and the generator weights read it, bounded.
    cra = _costed("credit_assignment", lambda: _producer("credit_assignment",
                                                          "research/credit_assignment.py",
                                                          "--apply"))
    # THE BLUEPRINT ORGANS (principal, 2026-09-16; Tier-1 phases C/D). Each runs on the core
    # plan every hour and leaves its artifact; order matters where one reads another (the axis
    # registry before the ladder, the hazard engine before the posterior, the wiring CEO before
    # probation). UNWIRED OR IDLE IS A DEFECT (III.16) -- these were built today and are on a
    # clock today.
    axr = _costed("axis_registry", lambda: _producer("axis_registry",
                                                      "research/axis_registry.py"))
    # THE UNSEEN FRONTIER: Chao1 / Good-Turing over canonical mechanism hashes per ground, so
    # the allocator knows which grounds are saturating (reads the axis registry's vocabulary).
    usf = _costed("unseen_frontier", lambda: _producer("unseen_frontier",
                                                        "research/unseen_frontier.py"))
    bld = _costed("breadth_ladder", lambda: _producer("breadth_ladder",
                                                       "research/breadth_ladder.py"))
    ffc = _costed("forced_flow_calendar", lambda: _producer("forced_flow_calendar",
                                                             "research/forced_flow_calendar.py"))
    ngt = _costed("novelty_gate", lambda: _producer("novelty_gate", "research/novelty_gate.py",
                                                     "--limit", "3000"))
    hze = _costed("hazard_engine", lambda: _producer("hazard_engine",
                                                      "research/hazard_engine.py"))
    pal = _costed("posterior_alpha", lambda: _producer("posterior_alpha",
                                                        "research/posterior_alpha.py"))
    smm = _costed("semantic_memory", lambda: _producer("semantic_memory",
                                                        "research/semantic_memory.py", "build"))
    mrb = _costed("model_role_benchmark", lambda: _producer("model_role_benchmark",
                                                             "research/model_role_benchmark.py"))
    lss = _costed("live_system_state", lambda: _producer("live_system_state",
                                                          "research/live_system_state.py"))
    t1s = _costed("tier1_scorecard", lambda: _producer("tier1_scorecard",
                                                        "research/tier1_scorecard.py"))
    # THE RESOURCE EXCHANGE: every department's measured yield per compute-hour and the
    # elastic factor research_budget multiplies into its legs' seconds; its clock is its floor.
    rdp = _costed("research_departments", lambda: _producer("research_departments",
                                                             "research/research_departments.py"))
    # QUALITY-DIVERSITY (GoAnt): one elite per economic niche; explorer/exploiter/connector
    # proposals into the intake. Cheap (seconds), so core.
    qdf = _costed("qd_frontier", lambda: _producer("qd_frontier", "research/qd_frontier.py"))
    # THE BLIND REVIEWER (AgonAlpha): re-executes certificates with fresh eyes; a VETO withholds
    # the LIVE row (promoter.blind_review_veto). ~90 s per cell: the validate department.
    bvr = _costed("blind_reviewer", lambda: _producer("blind_reviewer",
                                                       "research/blind_reviewer.py",
                                                       "--max-cells", "12"))
    # THE EVALUATOR LAB (Agora / Red Queen): attack variants evolved against fixed controls
    # behind the sealed anchor; the validate department, ~15 s at five seeds.
    evl = _costed("evaluator_lab", lambda: _producer("evaluator_lab",
                                                      "libs/validation/evaluator_lab.py",
                                                      "--seeds", "5"))
    # VALUE OF DATA: one ratio per missing observation, handed to the acquirer as targets.
    vod = _costed("value_of_data", lambda: _producer("value_of_data",
                                                      "research/value_of_data.py",
                                                      "--no-prospector-append"))
    # THE TYPED RESEARCH API's coverage and the immutable artifact chain's integrity, published.
    rap = _costed("research_api_status", lambda: _producer("research_api_status",
                                                            "scripts/research_api_status.py"))
    acv = _costed("artifact_chain", lambda: _producer("artifact_chain",
                                                       "scripts/verify_artifact_chain.py"))
    # THE IGNORANCE LEDGER: every unexplained thing in one queue, priority = magnitude x
    # recurrence x unexplained fraction; the top items donated as hypotheses.
    rsq = _costed("residual_queue", lambda: _producer("residual_queue",
                                                       "research/residual_queue.py",
                                                       "--max-donations", "15"))
    # THE SOURCE REGISTRY: every ground with provenance and result-based reputation, and the
    # intel ROI share each source earns (the crawlers read it as their crawl budget).
    srg = _costed("source_registry", lambda: _producer("source_registry",
                                                        "research/source_registry.py"))
    # THE WIRING CEO hunts every build that is on no clock (principal 2026-09-16: "always
    # hunting"); probation (heavy plan) exercises the safe ones until they earn a named leg.
    wce = _costed("wiring_ceo", lambda: _producer("wiring_ceo", "research/wiring_ceo.py",
                                                   "--apply"))
    prb = _costed("probation", lambda: _producer("probation", "research/probation_runner.py"))
    sqs = _costed("standing_questions", lambda: _producer("standing_questions",
                                                           "research/standing_questions.py",
                                                           "--budget-s", "240"))
    exd = _costed("exposure_decomposition", lambda: _producer(
        "exposure_decomposition", "research/exposure_decomposition.py"))
    # EVERY BUILD ON A CLOCK: the auto-clocked organs of this plan (data/auto_legs.json).
    auto = run_auto_legs()
    sw = _costed("sweep", sweep)
    cc = _costed("compile_candidates", compile_candidates)
    dp = _costed("deepen", deepen)
    # THE GAUNTLET, ON A CLOCK. It was on NO schedule -- not this roster's fifty legs, not the
    # daily cycle (which runs `scalp_gauntlet`, the scalp lane's own fixed list), and not the
    # Windows task set, which installs exactly MT5-Gateway, MT5-Hourly and MT5-Shadow.
    # `ops/reboot_drill.ps1` REQUIRES a task named MT5-Gauntlet and `Install-QuantWindows.ps1`
    # has never created one, so the drill has been checking for something that does not exist.
    #
    # THAT IS WHY `certified` IS ZERO. The funnel produces: miners fill the docket hourly, the
    # compiler turns it into 4,742 executable cells, enrolment and promotion both run on this
    # roster -- and the one stage that mints a certificate ran only when a person started it by
    # hand. Measured 2026-09-07: 2,371 docket candidates, 0 certified, and a build cursor whose
    # newest entry is 2026-09-04. The desk reads as "the gates are too strict"; the gates were
    # not being reached.
    #
    # BOUNDED BY ITS OWN DESIGN, which is why it can sit on an hourly clock at all: the sweep
    # carries a memory budget (`MEMORY_BUDGET_MB`, measured from the host) and a per-symbol build
    # cursor, so each pass takes a slice and the next one resumes where it stopped instead of
    # restarting the rotation. Nothing here needs a time limit bolted on; the cursor IS the limit.
    # THE DOCKET WRITER, WHICH RAN ON NO CLOCK THIS BOX OWNS. `merge_hypotheses` is the ONLY
    # writer of external_survivors.json -- every producer on this roster feeds it and nothing
    # else consumes them. Its one scheduled caller is `nightly_catchup`, a SYSTEMD unit: it runs
    # on the VPS, and the box is Windows with no systemd. So every candidate this machine mined,
    # compiled, deepened or swept reached a merge only if the other machine happened to run one.
    # Third instance of this exact shape today, after enrolment and miner_conversion.
    mh = _costed("merge_docket", lambda: _producer(
        "merge_hypotheses", "research/merge_hypotheses.py"))
    # THE BACKTEST. Also on no clock, anywhere -- not this roster, not the daily cycle, not the
    # Windows task set. It is the stage that turns a docket row into a survivor, so with it
    # unscheduled the gauntlet below had nothing new to judge no matter how often it ran.
    #
    # It can be hourly now because it was given a cursor and a time budget (see run_all): cells
    # never tested go first, then least-recently-tested, results MERGE rather than replace, and
    # the pass stops at BACKTEST_BUDGET_MIN. Before that it rebuilt the full 4,742-cell grid on
    # every invocation and kept nothing until the last cell returned -- a 2.5 hour run with no
    # partial credit, which on an hourly clock would have restarted at cell 1 forever.
    bt = _costed("backtest", lambda: _producer(
        "run_external_backtest", "side_channels/run_external_backtest.py"))
    gt = _costed("external_gauntlet", lambda: _producer(
        "external_gauntlet", "scripts/external_gauntlet.py"))
    # THE FALSIFIERS RUN AGAINST THE FRESH CANON (Tier-1 item V4, 2026-09-09). libs/validation/
    # falsifiers.py had zero callers; every certificate was minted and never attacked. The
    # producer budgets itself (600 s default) under this leg's timeout and writes
    # reports/FALSIFIER_VERDICTS.json; a kill there is evidence for the promoter, never a gate here.
    fz = _costed("falsifier_run", lambda: _producer("falsifier_run", "research/falsifier_run.py"))
    # THE CANON SEAL, hourly rather than daily. A certificate the gauntlet minted at 02:00 sat
    # unsealed until the next midnight run, so `shadow_admission._canon` -- which enrolment,
    # promotion and the dashboard all read -- was up to 24 hours behind the gates.
    # RUNS BECAUSE SOMETHING HAPPENED, NOT BECAUSE THE HOUR TURNED (I2). `queue_cycle` raises a
    # `recertify` task for every window whose cost coverage came back UNCOVERED, priced by how
    # much the charge was understated. This leg now CLAIMS one instead of running unconditionally:
    # with an empty queue it stands down and says so, and the hour is spent on something that has
    # work waiting. That single change is what turns a cycle running in source order into one
    # running on events.
    #
    # The task is completed or failed by its outcome, so a pass that dies does not silently
    # consume the work -- the lease expires and the next pass re-claims it, which is the property
    # the durable journal exists to provide and which nothing was using.
    rc = _costed("recertify_canon", _recertify_canon_claimed)
    # ENROLMENT, ON THE MACHINE THAT MINTS THE CERTIFICATES. `heal_clocks` above repairs clocks
    # that EXIST and have gone IDENTITY_BROKEN; it does nothing whatever for a certificate that
    # has no clock at all, and those are two different failures that read the same on a dashboard.
    #
    # NOTHING ENROLLED ON THIS BOX, ON ANY SCHEDULE. `shadow_forward` is the enroller and this
    # cycle never called it -- it appears in this file only inside comments. The one scheduled
    # caller is nightly_catchup's `enrol_clocks` step, which is a SYSTEMD unit: it runs on the
    # VPS, and the box is Windows with no systemd. So the machine that certifies could never
    # enrol what it had just certified, and every new certificate waited for a human.
    #
    # MEASURED off the live board 2026-09-06: 66 certified, 6 unrunnable, 27 on a clock -- 33
    # runnable certificates passing every one of the ten gates and accruing no out-of-sample
    # evidence, so none of them could ever mature into capital. That is the whole promotion
    # pipeline stalled behind a missing hourly call, and it presents as a research shortfall.
    #
    # Verified in a checkout of the same canon: all 48 authorized runs enrol cleanly, so the
    # enrolment logic was never the defect -- only its cadence.
    ecl = _costed("enrol_clocks", lambda: _producer(
        "shadow_forward", "research/shadow_forward.py"))
    # THE GROWTH-MAXIMISING SIZER, WHICH HAS NEVER RUN. `pf_allocator` solves posterior E[log W]
    # for PER-SLEEVE heat -- the fraction of equity each sleeve should risk to maximise compound
    # growth, which is the only principled answer to "how big should this trade be". Everything
    # downstream is already wired for it: `decision_core.allocator_heat` reads its artifact,
    # `allocator_book` reads its per-sleeve fractions, and `promoted_lot(from_book=True)` sizes
    # from those instead of the authority ladder.
    #
    # MEASURED 2026-09-07: data/PF_ALLOCATOR_ARMED has been present since 2026-09-04 and
    # reports/pf_allocation.json HAS NEVER EXISTED. The allocator is armed, wired and consumed,
    # and nothing has ever called it -- so `allocator_heat` returns "no pf_allocation.json" every
    # pass, `allocator_book` returns None, and every sleeve on this desk falls back to
    # `ramped_fraction`: the authority ramp, which is a function of how many trades a sleeve has
    # closed and contains no estimate of growth whatsoever.
    #
    # AN HOURLY CLOCK IS NOT A CHOICE HERE, IT IS THE DESIGN. `decision_core._ALLOC_MAX_AGE_S` is
    # 3600, so the artifact is refused the moment it turns an hour old. Any cadence slower than
    # hourly guarantees the book is always stale and always rejected -- which is indistinguishable
    # from never running it, and is why "the allocator is armed" was true and worthless at once.
    #
    # `--mode normal` is the hourly fidelity the file's own three-clock design names (fast every
    # five minutes, normal hourly, heavy overnight), and its job lock makes an overlap safe: a
    # pass that cannot get memory waits rather than thrashing beside one already resident.
    #
    # It runs AFTER enrolment so it solves over this hour's sleeve set rather than last hour's.
    # HEAVY WHEN NOBODY ELSE HAS MEASURED (2026-09-08). Only `--mode heavy` runs the admission
    # scan (pf_allocator: `if heavy and funded`), the scan is what lets a PROMOTION_CANDIDATE
    # leave STANDBY (promoter.reconcile_capital reads it), and heavy had exactly ONE scheduler:
    # the persistent MT5-ResearchSupervisor worker. A dead or stalled supervisor meant no scalp
    # sleeve could ever go LIVE while every artifact read healthy. This roster is on a clock the
    # box owns, so it measures the scan itself whenever the last one is missing or older than
    # ADMISSION_SCAN_MAX_AGE_S -- a scheduling redundancy, not a change to any admission rule.
    #
    # AND ITS FIRST INPUT HAD NO CLOCK EITHER, WHICH IS WHY IT NEVER PRODUCED ANYTHING. Adding
    # the leg below was necessary and was not sufficient: `pf_allocator` assembles evidence
    # through `portfolio_projection`, which refuses outright without `reports/hunt12_partial.json`
    # -- and that report's only scheduler was `research_supervisor`, keyed on a ONE-SHOT
    # `reports/DONE_hunt12` marker, on the same worker this file already records as dead or
    # stalled. So the allocator was armed, wired, consumed and scheduled, and exited 1 on every
    # pass for want of a file nothing produced. `hunt12` runs first, and only when the sweep is
    # absent, unfinished or a week old.
    h12 = _costed("hunt12", hunt12)
    pa = _costed("pf_allocator", lambda: _producer(
        "pf_allocator", "research/pf_allocator.py", "--mode", _allocator_mode_for_the_hour()))
    # THE PROMOTER READS THE SCAN THE LEG ABOVE JUST WROTE (2026-09-08). A promoted row reaches
    # the gateway only at status LIVE, and LIVE is written only by the promoter -- on a fresh
    # MEASURED admission that admits the sleeve, and for a STANDBY row on PROMOTE_ADMIT_STREAK
    # consecutive such readings, each reading being one promoter pass (`reconcile_capital`).
    # The promoter had two schedulers: the 22:00 UTC gateway pass and the daily cycle. So the
    # allocator could measure an admission at 13:00 and the row that admission funds would wait
    # until 22:00 for its first reading and until the NEXT day's for its second, while the scan
    # that admitted it aged past the 26h the promoter accepts. Three scalp sleeves sat at
    # PROMOTION_CANDIDATE for seventeen days with every artifact reading healthy.
    #
    # `promoter.main` is idempotent on a roster that has not changed: a name already in
    # sleeves.json is skipped by every promotion door, `reconcile_capital` records the current
    # reading on each row and moves it only on the asymmetric rule it already holds, and the
    # retire walk applies the same thresholds it applies at 22:00. Running it here changes no
    # admission law, no streak, no threshold: it makes the readings hourly, which is the cadence
    # the allocator's own artifact expiry (`decision_core._ALLOC_MAX_AGE_S` = 3600) assumes.
    pr = _costed("promoter", lambda: _producer("promoter", "research/promoter.py"))
    # MOVED BELOW THE GAUNTLET, 2026-09-07. This leg used to sit here at position 8 -- above
    # `merge`, `backtest`, `external_gauntlet` and `recertify_canon`, all of which were added to
    # this roster today. So it enrolled the certificates the canon held at the START of the pass
    # and every certificate this hour minted waited a full extra hour for its clock, on a
    # fourteen-day maturation that is already the longest pole in the funnel.
    #
    # It runs after `recertify_canon` because that is what SEALS a certificate into the canon
    # `shadow_forward` reads. Enrolling before the seal would walk the previous canon and find
    # nothing new, which is the same one-hour lag wearing a different explanation.

    et = _costed("execution_twin", execution_twin)
    cg = _costed("causal_graph", causal_graph)
    arl = _costed("alpha_rl", alpha_rl)
    rxs = _costed("research_exchange_score", research_exchange_score)
    lkp = _costed("lake_promote", lake_promote)
    orth = _costed("orthogonality", orthogonality)
    sess = _costed("session_allocation", session_allocation)
    sxp = _costed("session_chart_expansion", session_chart_expansion)
    stf = _costed("stamp_freshness", stamp_freshness)
    fat = _costed("fill_attribution", fill_attribution)
    c2e = _costed("cost_to_edge", cost_to_edge)
    swr = _costed("swap_rejudge", swap_rejudge)
    asp = _costed("asia_plane", asia_plane)
    sge = _costed("sge_premium", sge_premium)
    aco = _costed("asia_collector", asia_collector)
    apr = _costed("asia_parser", asia_parser)
    # AFTER the collector has recorded its verdicts: every source it could not read gets the
    # webmaster's variants tried and the Wayback copy located (`research/source_fixer.py`).
    sfx = _costed("source_fixer", lambda: _producer("source_fixer", "research/source_fixer.py"))
    # The bars every study reads: an unreadable parquet is quarantined for the fetcher to
    # rebuild, a stale one is named by asset class (`scripts/check_universe_integrity.py`).
    uin = _costed("universe_integrity",
                  lambda: _producer("universe_integrity", "scripts/check_universe_integrity.py"))
    srt = _costed("source_routes", source_routes)
    spa = _costed("strategy_paths", strategy_paths)
    wse = _costed("weak_signals", weak_signal_ensembles)
    rfx = _costed("residual_factors", residual_factors)
    mko = _costed("markout", markout)
    exo = _costed("exogenous_search", exogenous_search)
    srx = _costed("stop_reverse", stop_reverse_census)
    fwr = _costed("forward_reconcile", forward_reconcile_leg)
    ms = _costed("model_skill", model_skill)
    fcx = _costed("forecast_contract", forecast_contract)
    mz = _costed("model_league", model_league)
    ad = _costed("adversaries", adversaries)
    fr = _costed("frontier", frontier)
    df = _costed("deep_forest", deep_forest)
    mm = _costed("maintain_miners", maintain_miners)
    # MEASURE THE CONVERSION WHERE THE DISCOVERIES ARE, AND ON THIS HOUR'S CODE. Nothing on this
    # box regenerated `data/miner_conversion.json`. It has one scheduled caller -- a systemd unit
    # -- which runs on the VPS, and the box is Windows with no systemd, so the file the dashboard
    # reads was written by whichever machine last happened to run it, whenever that was, with
    # whatever code it had then. Same shape as the enrolment gap two legs up.
    #
    # WHAT THAT COST, MEASURED OFF THE LIVE BOARD 2026-09-07. The published breadth panel showed
    # 52 miners, 290,105 discoveries, reached_backtest 0 for every one of them, and duplicate
    # rates of 99.9-100% -- 36,982 broker_swaps rows collapsing to ONE "distinct mechanism". That
    # is not a measurement of the desk, it is the signature of the OLD key: `_mechanism_key` is
    # family|SYMBOL|session, which a raw miner row does not carry, so every raw row keyed to
    # unknown|*|* and the intersection with tested rows was empty by construction (L0232). The
    # same checker on current code reads 53 miners and 6 zero-yield. So MINER_YIELD_ALARM has
    # been firing on a stale artifact, and "miners are producing rows and no survivors" was a
    # statement about a key, not about the miners.
    #
    # Last leg before publication, so the panel the dashboard renders is this hour's answer.
    # THE TAPE LEAVES THE BOX ON ITS OWN, THE HOUR A BUCKET EXISTS. The tick tape is the only
    # dataset here that cannot be re-obtained and the only one that grows without bound on a disk
    # shared with a git checkout and a 21-chart bar lake; every local answer to that is a choice
    # about what to sacrifice. This ships partitions older than KEEP_DAYS (45 -- fifteen days
    # clear of the thirty every reader opens) to S3-compatible storage, and deletes a source only
    # after the destination has been read back and proved to be those bytes.
    #
    # `--if-configured` so an unconfigured box exits 0 rather than reddening every cycle: it says
    # what is missing once an hour and moves nothing. Nothing here can delete a tick that has not
    # been verified somewhere else first.
    ta = _costed("archive_tape", lambda: _producer(
        "archive_tape", "scripts/archive_tape.py", "--dest", "s3://ticks", "--apply",
        "--if-configured"))
    mc = _costed("miner_conversion", lambda: _producer(
        "check_miner_conversion", "scripts/check_miner_conversion.py"))
    _costed("capacity", lambda: _producer("capacity", "research/capacity.py"))
    _costed("timeframe_coverage", lambda: _producer(
        "timeframe_coverage", "scripts/check_timeframe_coverage.py"))
    _costed("frontier_report", lambda: frontier_report(h))
    # THE FRONTIER LOOP'S LAST MISSING RUNG. Until now it ended at a plan: the supervisor scored a
    # gap, wrote a queue row, and a person carried the idea to a builder by hand. That courier
    # step is the thing the mandate names -- "no known gap is allowed to remain merely because
    # nobody manually remembered to tell the builder."
    #
    # `--apply` IS SAFE HERE FOR A STRUCTURAL REASON, not an optimistic one: the implementer can
    # only write under `frontier_intel/challengers/`, the containment is checked on the RESOLVED
    # path so a generated name carrying `..` cannot walk into the money path, and every artifact
    # is stamped authority ZERO. It opens no branch and merges nothing. A challenger nobody
    # promotes costs a directory; the ladder to capital is unchanged.
    fi = _costed("frontier_implementer", lambda: _producer(
        "frontier_implementer", "frontier_intel/implementer.py", "--apply"))
    # PUBLICATION IS THE LAST TWO LEGS, and their order is not arbitrary: sealing survivors makes
    # new rows the dashboard should show, so publishing the view before sealing would render a
    # board that is one full hour behind the pass that just produced it.
    ps = _costed("publish_survivors", publish_survivors)
    pd_ = _costed("publish_dashboard", publish_dashboard)
    ib = _costed("issue_board", issue_board)
    qc = _costed("queue_compact", queue_compact)
    rt = _costed("rebalance_trigger", rebalance_trigger)
    ec = _costed("edge_confidence", edge_confidence)
    ro = _costed("research_org", research_org)
    xd = _costed("experiment_design", experiment_design)
    mi = _costed("market_intel", market_intel)
    mll = _costed("ml_layer", ml_layer)
    xc = _costed("experiment_cache", experiment_cache)
    og = _costed("opportunity_gap", opportunity_gap)
    # ---- THE TWELVE THAT NOTHING RAN ------------------------------------------------------
    # Measured 2026-09-06 by blueprint/coverage: twelve capabilities sat at WIRED -- imported by
    # production code, named by no scheduler surface. A capability nothing runs is code, not a
    # capability, and the mandate's §146H says every WIRED-only organ must either be scheduled or
    # declare in writing why it is event-driven. These are the ones that are genuinely periodic.
    #
    # SUBPROCESSES VIA `_producer`, deliberately: several are heavy (world simulation, ensemble
    # optimisation, the graveyard model) and a hang or an allocation failure inside one must not
    # take the rest of the hour's legs with it. `_producer` bounds and reports each.
    #
    # NOT INCLUDED AND THE REASON MATTERS: heat_policy (P0.2) and capability_graph (P0.3) are
    # LIBRARIES the money path imports on every allocator pass, not producers with a cadence.
    # Scheduling them would run a no-op main() and turn WIRED into SCHEDULED without changing
    # anything -- a green light bought by fooling the fence, which is the failure the fence is
    # for. They are declared event-driven in the registry instead.
    xr = _costed("execution_resolver", lambda: _producer(
        "execution_resolver", "research/execution_resolver.py"))
    cw = _costed("counterfactual_world", lambda: _producer(
        "counterfactual_world", "libs/research/counterfactual_world.py"))
    eo = _costed("ensemble_optimizer", lambda: _producer(
        "ensemble_optimizer", "libs/self_improvement/ensemble_optimizer.py"))
    uk = _costed("frontier_unknowns", lambda: _producer(
        "unknowns", "frontier_intel/unknowns.py"))
    fo = _costed("frontier_ontology", lambda: _producer(
        "ontology", "frontier_intel/ontology.py"))
    xs = _costed("exit_study", lambda: _producer(
        "exit_study", "research/exit_study.py"))
    gm = _costed("graveyard_model", lambda: _producer(
        "graveyard_model", "libs/research/graveyard_model.py"))
    wc = _costed("world_crawler", lambda: _producer(
        "world_crawler", "side_channels/world_crawler.py"))
    # P0.1, THE LAST UNSCHEDULED CAPABILITY OF THE NINETY-FOUR. `release_identity.py` has a
    # main() and nothing on either machine ever called it: the registry names its ARTIFACT as the
    # producer, so `scheduler_for` searched for a schedule matching a .json path and found none,
    # and the empty list read as "no surface" rather than "never looked for the right thing".
    #
    # It answers whether the code that is TRADING is the code that was sealed, which every other
    # capability's evidence quietly assumes. Left to a manual run it goes stale silently and the
    # answer decays into a claim about whatever the box happened to be running yesterday --
    # measured 2026-09-06: last written 2026-09-05T23:17, ok=false, 1,074 paths of drift against
    # the sealed release, and nothing scheduled to notice.
    ri = _costed("release_identity", lambda: _producer(
        "release_identity", "mt5desk/release_identity.py"))
    # BURN-IN, RIGHT AFTER THE VERDICT IT RECORDS (2026-09-08). One row per pass: is the running
    # code the sealed code, what did it do with money in the last day, how long has that been
    # true. The review's bar for "deployment is boring" is thirty days of it with fills; this is
    # the file that makes that a subtraction rather than a memory (reports/burn_in.json).
    bi = _costed("burn_in", lambda: _producer("burn_in", "research/burn_in.py"))
    # THREE MEASUREMENTS OF THE MACHINE ITSELF (Tier-1 items G14, A13, I18; 2026-09-09), read
    # from what the legs above wrote, so they see this pass and not the last one:
    #   layer_census      which of the seven strategy layers the hour's compute went to
    #   opportunity_cost  what the hour therefore did NOT test, by name
    #   acceptance        the five acceptance properties, measured or UNMEASURED
    lc = _costed("layer_census", lambda: _producer("layer_census", "libs/research/layers.py"))
    oc = _costed("opportunity_cost", lambda: _producer(
        "opportunity_cost", "research/opportunity_cost.py"))
    ac = _costed("acceptance", lambda: _producer(
        "acceptance", "scripts/check_acceptance_properties.py"))
    # TWO FORECASTS THE DESK NEVER MADE (Tier-1 P15, P6; 2026-09-09), both reports:
    #   opportunity_forecast  where alpha is likely to EMERGE next, the graph read forward
    #   edge_reliability      P(this sleeve works now), one fused column per sleeve
    ofc = _costed("opportunity_forecast", lambda: _producer(
        "opportunity_forecast", "research/opportunity_forecast.py"))
    erl = _costed("edge_reliability", lambda: _producer(
        "edge_reliability", "research/edge_reliability.py"))
    # THE ARENA AND THE CLOCK'S CAPITAL (Tier-1 AP5 and P18; 2026-09-09). The arena records a
    # verdict per research arm against the leader -- the count AP5 measures -- and retires
    # nothing; session_capital reports which four-hour bands of the day the book's heat never
    # reached, which is the denominator a session auction would need.
    ar = _costed("arena", lambda: _producer("arena", "libs/research/arena.py"))
    # WHICH JUDGE HEARS WHOM (Tier-1 item V7): the two statistical stacks censused, with the
    # modules that judge nothing named. A census, never a gate.
    pc = _costed("prosecutor", lambda: _producer("prosecutor", "scripts/check_prosecutor.py"))
    # THE DESK'S OWN SCALING LAW (Tier-1 item I15): survivors per compute hour, fitted in logs,
    # now that every leg records its cost. UNMEASURED until the ledger holds seven days.
    slw = _costed("scaling_laws", lambda: _producer("scaling_laws", "libs/ops/scaling_laws.py"))
    # WHICH ORGANS HAVE ANYTHING ON THE OTHER END (Tier-1 item I4). Report only: nothing is
    # disabled, masked or deleted -- organs are retired by a person, on this evidence.
    dac = _costed("dead_architecture", lambda: _producer(
        "dead_architecture", "scripts/check_dead_architecture.py"))
    # THE BARS THE VERDICTS WERE MEASURED ON (Tier-1 item V16). The release seal pins the code a
    # verdict came from; this pins its inputs, so a re-run can tell a code change from a data one.
    iid = _costed("input_identity", lambda: _producer(
        "input_identity", "libs/data/input_identity.py"))
    scap = _costed("session_capital", lambda: _producer(
        "session_capital", "research/session_capital.py"))
    # LAST, AND DELIBERATELY SO: it publishes what every leg above just wrote. Placing it here
    # means one pass produces the state AND delivers it, instead of delivering the previous hour's.
    pub = _costed("publish_state", publish_state)
    (BASE / "data" / "sync_marker.json").write_text(
        json.dumps({"last_cycle": datetime.now(UTC).isoformat(),
                    "health": h, "tape": t, "state_vector": s, "daily": d,
                    "regime_monitor": rg,
                    "deepening": dp, "heal_clocks": hc, "mine": m,
                    "search": se, "breadth_sweep": bs, "candidate_conservation": ccv,
                    "pit_canaries": pcn, "mutation_yield": myd, "credit_assignment": cra,
                    "axis_registry": axr, "breadth_ladder": bld, "forced_flow_calendar": ffc,
                    "novelty_gate": ngt, "hazard_engine": hze, "posterior_alpha": pal,
                    "semantic_memory": smm, "model_role_benchmark": mrb,
                    "live_system_state": lss, "tier1_scorecard": t1s, "wiring_ceo": wce,
                    "research_departments": rdp, "qd_frontier": qdf, "blind_reviewer": bvr,
                    "evaluator_lab": evl, "value_of_data": vod, "research_api_status": rap,
                    "artifact_chain": acv, "residual_queue": rsq, "unseen_frontier": usf,
                    "source_registry": srg,
                    "probation": prb, "standing_questions": sqs, "exposure_decomposition": exd,
                    "auto_legs": auto,
                    "sweep": sw, "compile": cc,
                    "execution_twin": et, "causal_graph": cg, "alpha_rl": arl,
                    "research_exchange_score": rxs, "lake_promote": lkp,
                    "orthogonality": orth,
                    "session_allocation": sess,
                    "session_chart_expansion": sxp,
                    "stamp_freshness": stf,
                    "fill_attribution": fat,
                    "cost_to_edge": c2e,
                    "swap_rejudge": swr,
                    "asia_plane": asp,
                    "sge_premium": sge,
                    "asia_collector": aco,
                    "asia_parser": apr,
                    "source_fixer": sfx,
                    "universe_integrity": uin,
                    "source_routes": srt,
                    "strategy_paths": spa,
                    "weak_signals": wse,
                    "residual_factors": rfx,
                    "markout": mko,
                    "exogenous_search": exo,
                    "stop_reverse": srx,
                    "forward_reconcile": fwr,
                    "model_skill": ms,
                    "frontier": fr, "refresh_bars": rb, "deep_forest": df,
                    "maintain_miners": mm, "publish_survivors": ps,
                    "forecast_contract": fcx, "model_league": mz, "adversaries": ad,
                    "publish_dashboard": pd_, "opportunity_gap": og, "experiment_cache": xc,
                    "ml_layer": mll, "market_intel": mi, "experiment_design": xd,
                    "research_org": ro, "edge_confidence": ec, "rebalance_trigger": rt,
                    "queue_compact": qc, "issue_board": ib,
                    "execution_resolver": xr, "counterfactual_world": cw,
                    "ensemble_optimizer": eo, "frontier_unknowns": uk,
                    "frontier_ontology": fo, "exit_study": xs,
                    "graveyard_model": gm, "world_crawler": wc,
                    "release_identity": ri, "burn_in": bi, "layer_census": lc,
                    "opportunity_cost": oc, "acceptance": ac, "opportunity_forecast": ofc,
                    "edge_reliability": erl, "arena": ar, "session_capital": scap,
                    "prosecutor": pc, "scaling_laws": slw,
                    "dead_architecture": dac, "input_identity": iid,
                    "publish_state": pub,
                    "enrol_clocks": ecl, "requeue_unrunnable": rq, "reclaim_disk": dd,
                    "miner_conversion": mc, "moat_miner": mo, "archive_tape": ta,
                    "external_gauntlet": gt, "falsifier_run": fz, "merge_docket": mh,
                    "backtest": bt,
                    "wiring_audit": wa, "brain_ab": ab, "alpha_breadth": cm,
                    "alpha_evolution": aev, "closed_loop": clp,
                    "alpha_periodic_table": pt, "queue_cycle": qcy,
                    "microstructure_census": mx, "entry_timing": ety,
                    "spread_provenance": sp, "tape_features": tf,
                    "futures_lead_lag": fll, "time_joins": tj, "allocator_join": aj,
                    "fred_macro": fm,
                    "fusion_cost": fzc, "cost_construction": cxc,
                    "edges_macro_fusion_sweep": emf,
                    "recertify_canon": rc, "hunt12": h12,
                    "pf_allocator": pa, "promoter": pr,
                    "frontier_implementer": fi,
                    "smoke_release": smoke},
                   indent=1), encoding="utf-8")
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
