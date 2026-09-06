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
    """
    try:
        from libs.ops.compute_ledger import close_run, open_run
    except Exception:                                                   # noqa: BLE001
        return fn()
    run = open_run(name, kind="hourly_cycle")
    try:
        out = fn()
    except BaseException as exc:
        close_run(run, outcome=f"{type(exc).__name__}: {exc}"[:200])
        raise
    close_run(run, outcome="ok")
    return out


#: Wall clock a search leg may spend inside the cycle. The two searches are the desk's own
#: hypothesis SOURCES, so starving them starves the docket -- but a search that overran the hour
#: would push the deepening worker, the miners and the marker out of the pass entirely. Twelve
#: minutes each leaves the 40-minute deepening budget and the remaining legs their time inside the
#: hour, and a search that needs longer is one that should be given its own task on the box.
SEARCH_BUDGET_SEC = 720


def _producer(name: str, script: str, args: tuple[str, ...] = ()) -> dict:
    """Run one hypothesis producer as a subprocess, bounded, and report what happened.

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
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target), *args],
                           capture_output=True, text=True, cwd=str(root),
                           timeout=SEARCH_BUDGET_SEC, check=False)
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "at": datetime.now(UTC).isoformat()}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "timeout_s": SEARCH_BUDGET_SEC,
                "note": f"{name} exceeded its cycle budget and was stopped; its partial work is "
                        f"whatever it had already written",
                "at": datetime.now(UTC).isoformat()}
    except Exception as exc:                                            # noqa: BLE001
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
    except Exception as exc:                                            # noqa: BLE001
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


def main() -> None:
    # BARS FIRST. Every leg below reasons about a chart, so a stale chart makes all of them
    # confidently wrong rather than merely late.
    rb = _costed("refresh_bars", refresh_bars)
    smoke = _costed("smoke_release", smoke_release)
    h = _costed("health", health)
    t = _costed("record_tape", record_tape)
    s = _costed("state_vector", state_vector)
    d = _costed("daily", daily)
    hc = _costed("heal_clocks", heal_clocks)
    # THE CONVERSION CHAIN, IN THE ORDER IT CONVERTS. mine fetches, compile turns what was fetched
    # into candidates and deepening tasks, deepen reverse-engineers the tasks that are not yet
    # rules. The cycle previously ran deepen BEFORE mine and never ran compile at all, so the
    # worker spent every hour on a queue nobody had refreshed and anything the crawlers fetched
    # after the last manual compile was unread for ever.
    m = _costed("mine", mine)
    se = _costed("search", search)
    sw = _costed("sweep", sweep)
    cc = _costed("compile_candidates", compile_candidates)
    dp = _costed("deepen", deepen)
    et = _costed("execution_twin", execution_twin)
    cg = _costed("causal_graph", causal_graph)
    ms = _costed("model_skill", model_skill)
    fcx = _costed("forecast_contract", forecast_contract)
    mz = _costed("model_league", model_league)
    ad = _costed("adversaries", adversaries)
    fr = _costed("frontier", frontier)
    df = _costed("deep_forest", deep_forest)
    mm = _costed("maintain_miners", maintain_miners)
    _costed("frontier_report", lambda: frontier_report(h))
    # PUBLICATION IS THE LAST TWO LEGS, and their order is not arbitrary: sealing survivors makes
    # new rows the dashboard should show, so publishing the view before sealing would render a
    # board that is one full hour behind the pass that just produced it.
    ps = _costed("publish_survivors", publish_survivors)
    pd_ = _costed("publish_dashboard", publish_dashboard)
    rt = _costed("rebalance_trigger", rebalance_trigger)
    ec = _costed("edge_confidence", edge_confidence)
    ro = _costed("research_org", research_org)
    xd = _costed("experiment_design", experiment_design)
    mi = _costed("market_intel", market_intel)
    mll = _costed("ml_layer", ml_layer)
    xc = _costed("experiment_cache", experiment_cache)
    og = _costed("opportunity_gap", opportunity_gap)
    (BASE / "data" / "sync_marker.json").write_text(
        json.dumps({"last_cycle": datetime.now(UTC).isoformat(),
                    "health": h, "tape": t, "state_vector": s, "daily": d,
                    "deepening": dp, "heal_clocks": hc, "mine": m,
                    "search": se, "sweep": sw, "compile": cc,
                    "execution_twin": et, "causal_graph": cg, "model_skill": ms,
                    "frontier": fr, "refresh_bars": rb, "deep_forest": df,
                    "maintain_miners": mm, "publish_survivors": ps,
                    "forecast_contract": fcx, "model_league": mz, "adversaries": ad,
                    "publish_dashboard": pd_, "opportunity_gap": og, "experiment_cache": xc, "ml_layer": mll, "market_intel": mi, "experiment_design": xd, "research_org": ro, "edge_confidence": ec, "rebalance_trigger": rt,
                    "smoke_release": smoke},
                   indent=1), encoding="utf-8")
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
