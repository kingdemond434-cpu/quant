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
# EVERY BUDGETED CHILD RUNS UNDER THE TREE-KILLING RUNNER (libs/ops/proctree.py). Measured
# 2026-09-22: `subprocess.run(timeout=)` killed the leg and left its worker pools behind --
# 72 orphans, 147 GB of commit -- until every new leg died of STATUS_COMMITMENT_LIMIT.
try:
    from libs.ops import proctree as _proctree
    _run_tree = _proctree.run
except Exception:
    _run_tree = subprocess.run
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
        r = _run_tree([sys.executable, "-u", "-W", "ignore", str(target)],
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


#: WHERE THE STATE-VECTOR BUDGET COMES FROM, and why it is not a constant.
#:
#: MEASURED 2026-09-23 on the trading box: a full `state_vector_build` pass costs **470 seconds**
#: and exits 0 with its own named GAPs. This leg gave it 45 and killed it at 45 EVERY HOUR --
#: the compute ledger recorded `state_vector TIMEOUT wall=45.167` and `data/state_vector.json`
#: was **18.7 hours old** on a box whose regime lane is hourly. The allocator's
#: `_admitted_extra_dims` reads that file to pick the state the book is solved and certified in,
#: so every pass for most of a day conditioned on yesterday's world while reporting today's.
#:
#: A constant is what caused this, so the replacement is not another constant. The budget is
#: LEARNED from this leg's own outcomes: a pass that completes sets the next budget to 1.5x what
#: it took, a pass that is killed doubles it, and both are bounded by the cycle's own slack --
#: never by a number chosen off a machine size. An unreadable memory falls back to the measured
#: need, which is the honest floor rather than the historic 45.
_SV_MEMORY = BASE / "data" / "state_vector_budget.json"
#: One quarter of the hourly cycle. The ceiling is the CLOCK's, not the box's: a leg that ate
#: more than this would starve the legs after it, and the cycle is the only thing that owns that
#: trade-off.
_SV_CEILING_S = 900.0
#: The measured cost of one full pass, 2026-09-23. The floor, so an unreadable memory cannot
#: reinstate a budget that is known to kill the build.
_SV_FLOOR_S = 480.0


def _state_vector_budget_s() -> float:
    """This leg's budget, learned from its own outcomes and bounded by the cycle's slack."""
    env = os.environ.get("STATE_VECTOR_HOURLY_BUDGET_SEC")
    if env:
        with suppress(ValueError):
            return max(15.0, float(env))
    try:
        mem = json.loads(_SV_MEMORY.read_text(encoding="utf-8"))
        want = float(mem["next_budget_s"])
    except (OSError, ValueError, KeyError, TypeError):
        return _SV_FLOOR_S
    return float(min(_SV_CEILING_S, max(_SV_FLOOR_S, want)))


def _state_vector_budget_learn(*, ok: bool, spent_s: float) -> None:
    """Record what this pass cost so the next one is sized by measurement, never by guess."""
    nxt = min(_SV_CEILING_S, max(_SV_FLOOR_S, spent_s * (1.5 if ok else 2.0)))
    with suppress(OSError, TypeError, ValueError):
        _SV_MEMORY.parent.mkdir(parents=True, exist_ok=True)
        _SV_MEMORY.write_text(json.dumps({
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "last_budget_s": round(float(spent_s), 1), "last_outcome": "OK" if ok else "KILLED",
            "next_budget_s": round(float(nxt), 1),
            "ceiling_s": _SV_CEILING_S, "floor_s": _SV_FLOOR_S,
            "rule": ("completed -> 1.5x what it took; killed -> 2x, bounded by one quarter of "
                     "the hourly cycle. Measured 2026-09-23: a full pass costs 470s"),
        }, indent=1) + "\n", encoding="utf-8")


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
    timeout_s = _state_vector_budget_s()
    try:
        r = _run_tree(
            [sys.executable, "-u", "-W", "ignore", str(target), "--budget-s",
             str(max(10, timeout_s - 5))],
            capture_output=True, text=True, cwd=str(BASE), timeout=timeout_s, check=False,
        )
        _state_vector_budget_learn(ok=r.returncode == 0, spent_s=timeout_s)
        return {
            "exit_code": int(r.returncode),
            "status": "OK" if r.returncode == 0 else "FAILED",
            "budget_s": timeout_s,
            "tail": (r.stdout or r.stderr or "")[-500:],
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    except subprocess.TimeoutExpired as exc:
        _state_vector_budget_learn(ok=False, spent_s=timeout_s)
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


def _priced_budget(leg: str, base: int) -> tuple[int, dict]:
    """The meta controller's priced budget for a leg, recorded; the base on any failure.

    ONE CONTROLLER PRICES EVERY USE OF RESEARCH RESOURCES (Tier-1 B27). `_bandit_budget` below
    asks `research_budget`, which knows the two legs whose arms the bandit prices;
    `cycle_pricing` asks the whole price stack -- the meta controller's dE[log W] board first,
    then the bandit, then the compute policy's tier split -- for EVERY leg, and records planned
    against applied in reports/CYCLE_PRICING.json. A leg no source prices sits at the median and
    runs on its base, which is the honest reading of UNMEASURED (L1.28a).

    NEVER STALLS A LEG. Any failure to price returns the base budget, so the worst case is the
    behaviour this cycle had before the controller existed.
    """
    try:
        import cycle_pricing
        return cycle_pricing.applied_budget(leg, base)
    except Exception as exc:
        return int(base), {"leg": leg, "applied": False, "factor": 1.0,
                           "why": f"cycle_pricing unavailable: {type(exc).__name__}: {exc}"}


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
    "forward_reconcile", "clock_liveness",
    "closed_loop", "acceptance", "candidate_conservation", "pit_canaries",
    "mutation_yield", "credit_assignment", "publish_survivors", "publish_dashboard",
    # The cheap half of the Tier-1 B rows: each reads artifacts and writes one, in well under a
    # minute, and the closed-loop attestation that runs in this same plan reads three of them.
    # `regime_hierarchy` and `representation_discovery` fit models and stay on the heavy plan.
    "release_authority", "residual_map", "failure_prior", "scientist_standings",
    "frontier_ceo", "evig_acquisition",
    "stamp_freshness", "time_joins", "layer_census", "opportunity_cost", "dead_architecture",
    "producer_census", "productivity_census", "preregistration",
    "cycle_pricing", "causal_invariance",
    # THE CLOSED-LOOP ORGANS (Tier-1 B14-B25): all cheap readers of artifacts that already exist,
    # so they belong on the core clock rather than the heavy one. `actor_pressure` and
    # `counterfactual_timeframes` read bars and stop themselves at their own budget.
    "source_evig", "source_drain", "pack_cells", "ground_depth", "timeframe_fanout",
    "fill_recorder",
    "actor_pressure", "destroyer_pool", "quantbench",
    "evidence_chain",
    "clock_ledger", "shortfall_model", "counterfactual_timeframes", "meta_rnd",
    "prosecutor", "scaling_laws", "arena", "session_capital", "session_allocation",
    "allocator_join", "rebalance_trigger", "edge_reliability", "edge_confidence", "capacity",
    "fill_attribution", "execution_resolver", "markout", "swap_rejudge", "queue_compact",
    "requeue_unrunnable", "merge_docket", "miner_conversion", "graveyard_model",
    "research_exchange_score", "model_skill", "research_org", "experiment_design",
    "experiment_cache", "opportunity_gap", "opportunity_forecast", "forecast_contract",
    "alpha_breadth", "alpha_periodic_table", "regime_coverage", "timeframe_coverage",
    "frontier_unknowns", "frontier_report", "frontier_ontology", "counterfactual_world",
    "strategy_paths", "reclaim_disk", "archive_tape", "queue_cycle",
    # THE 2026-09-16 BLUEPRINT ORGANS (phases C/D of the Tier-1 ledger), all cheap readers.
    "axis_registry", "tier1_scorecard", "novelty_gate", "forced_flow_calendar", "breadth_ladder",
    "wiring_ceo", "live_system_state", "hazard_engine", "posterior_alpha", "semantic_memory",
    "model_role_benchmark", "research_departments", "qd_frontier", "value_of_data",
    "research_api_status", "artifact_chain", "residual_queue", "unseen_frontier",
    "source_registry", "queue_census",
    # THE CANONICAL REGISTRY BRIDGE (2026-09-17): every pass pours the desk's record in.
    "registry_sync",
    # THE CONVERSION AND RESEARCH DEBT LEDGERS (M7): cheap registry reads, every pass.
    "research_debt",
    # THE INGESTION-EXPLOITATION GATE (LAWS 5c): an artifact read and two ratchets, every pass.
    # The LEDGER it reads is heavy and stays in the data department; the gate is not.
    "ingestion_exploitation",
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
#: THE FOREST FEDERATION (principal 2026-09-17): every region is its own 24/7 research
#: civilization running eleven agent roles in parallel, not one global crawler that occasionally
#: searches Korea. Each is its OWN department with its OWN resident (the per-forest task in
#: `libs.research.forests.FOREST_TASKS`), so the twelve regions and the five global layers
#: run CONCURRENTLY and compete for compute through
#: `libs/research/forests.allocation_for` rather than queueing behind one another. Japan and
#: global_macro already have residents (`japan`, `macro`); the eleven below are the ones that did
#: not, and the four global-layer legs join `regions`, which is the department that already hosts
#: the cross-country research OS.
FOREST_DEPARTMENTS: tuple[str, ...] = ("korea", "china", "russia_cis", "south_asia", "asean",
                                       "oceania", "europe", "north_america", "latam", "mena",
                                       "africa")
#: The global-layer forests: a LAYER of the world rather than a place, so they do not get a
#: region resident of their own -- they run on the `regions` resident beside global_research_os.
GLOBAL_FOREST_LEGS: tuple[str, ...] = ("forest_global_web", "forest_global_academic_code",
                                       "forest_global_physical_data", "forest_global_market_data")

DEPARTMENTS: tuple[str, ...] = ("japan", "regions", "data", "intel", "discovery", "validate",
                                "macro", "execution",
                                "forward", "meta", "rest", "mathlab", *FOREST_DEPARTMENTS)
LEG_DEPARTMENT: dict[str, str] = {
    # data: bars, tapes, lakes, sources -- the inputs every other department reads
    **dict.fromkeys(("refresh_bars", "tape_features", "lake_promote", "universe_integrity",
                     "source_routes", "source_fixer", "asia_collector", "asia_parser",
                     # walking inside a registered ground's own door is collection, like the
                     # collector above it: it fetches documents and files them as claims
                     "ground_depth",
                     "asia_plane", "archive_tape", "reclaim_disk", "maintain_miners",
                     "spread_provenance", "microstructure_census", "fusion_cost",
                     "cost_construction", "swap_rejudge", "sge_premium", "moat_series",
                     "unused_information", "ingestion_ledger", "representation_forge",
                     "feature_compiler", "data_acquisition_scientist", "coverage_drain",
                     "judge_coverage", "orthogonality_yield", "effective_trials"), "data"),
    # intel: the global intelligence agency -- crawlers, forests, frontier scouts
    **dict.fromkeys(("world_crawler", "deep_forest", "moat_miner", "market_intel", "mine",
                     "moat_candidate_compiler", "algorithm_db",
                     "exogenous_search", "standing_questions", "frontier", "frontier_report",
                     "frontier_implementer", "hunt12", "scout_roster", "analyst_pipeline",
                     "knowledge_graph", "moat_collectors", "actor_atlas", "scout_swarm",
                     "source_frontier", "data_scout", "external_federation",
                     "understanding_seat", "archaeology", "sares", "shadow_institutional",
                     "source_civilizations", "evidence_watchtower", "prediction_markets",
                     "latent_actors", "residual_hunt", "evidence_router",
                     # Tier-1 B6/B8/B9: the tree, the residual map that aims the exogenous
                     # search, and the docket the sealed gauntlet orders its sweep by.
                     "research_tree", "residual_map", "frontier_ceo",
                     "federation_ops", "sandbox_runner", "sandbox_provision",
                     "sandbox_roster", "proposer_seat", "kimi_hunt",
                     # Derives each instrument's own session from its own bars and mints the
                     # breakout aimed at it, instead of porting gold's hours everywhere.
                     "session_structure"),
                    "intel"),
    # discovery: the candidate pipeline, in order, plus the evolutionary generators
    **dict.fromkeys(("search", "sweep", "breadth_sweep", "compile_candidates", "merge_docket",
                     "deepen", "alpha_evolution", "alpha_rl", "ml_layer", "ensemble_optimizer",
                     "requeue_unrunnable", "queue_cycle", "queue_compact", "miner_conversion",
                     "recertify_canon", "session_chart_expansion", "experiment_design",
                     "experiment_cache", "probation", "axis_proposer", "program_alpha_lane",
                     "trajectory_evolution", "descendants", "card_explosion", "alpha_lineage",
                     "alpha_recombination", "graveyard_resurrection", "discovery_compiler",
                     "conversion_maximiser", "trend_core"),
                    "discovery"),
    # validate: the adversarial evidence lab
    **dict.fromkeys(("external_gauntlet", "backtest", "falsifier_run", "adversaries",
                     "stop_reverse", "orthogonality", "blind_reviewer", "synthetic_regimes",
                     "evaluator_lab", "lead_replication", "science_controller",
                     "replication_civilization", "certificate_truth", "model_search",
                     "loop_liveness", "counterexample_agent", "judging_throughput",
                     "forward_enrolment", "residual_gate"),
                    "validate"),
    # macro: the cross-asset / macro brain
    **dict.fromkeys(("fred_macro", "futures_lead_lag", "causal_graph", "residual_factors",
                     "weak_signals", "edges_macro_fusion_sweep", "strategy_paths",
                     "counterfactual_world", "opportunity_forecast", "forecast_contract",
                     "exposure_decomposition", "event_response_atlas", "causal_lab",
                     "event_graph_lab",
                     "world_lab", "macro_department", "news_event_stream",
                     "event_sleeves", "macro_intelligence", "world_model",
                     "market_constitution", "dislocation_lab", "macro_state_engine",
                     # Tier-1 B3/B4: the per-asset world model and the learned representation
                     # lane are both about what the market IS, before anything predicts it.
                     "regime_hierarchy", "representation_discovery",
                     "event_surprise"), "macro"),
    # execution: the execution research command
    **dict.fromkeys(("execution_twin", "entry_timing", "cost_to_edge", "exit_study",
                     "execution_resolver", "netting_report", "execution_alpha",
                     "latency_lab", "feed_clock_lab", "impact_lab", "digital_twin",
                     "net_edge", "cost_truth"),
                    "execution"),
    # forward: forward evidence, promotion and the allocator
    **dict.fromkeys(("enrol_clocks", "pf_allocator", "daily", "hunt12_forward", "regime_router",
                     "forward_slot_ranker", "forward_exploitation", "shadow_discovery",
                     "missed_trade_archaeologist", "portfolio_bounty",
                     "drawdown_alpha_miner", "trade_autopsy", "counterfactual_attribution",
                     "clock_liveness", "allocator_liveness", "allocator_trigger"),
                    "forward"),
    # meta: the machine that runs the machine (the heavy part of it)
    **dict.fromkeys(("issue_board", "publish_state", "model_league", "ml_layer_meta",
                     "research_os_archive", "registry_sync", "mining_objective",
                     "research_gap_map", "gauntlet_backpressure", "miner_specialisation",
                     "research_auction", "bottleneck_law", "bottleneck_attack",
                     "research_latency",
                     "alpha_replenishment", "research_dashboard",
                     "research_roi", "experiment_spine", "implementer",
                     "research_debt", "paradigm_router", "meta_controller",
                     "ingestion_exploitation", "coverage_tensor", "research_evolution",
                     "compute_economics", "control_plane", "attribution_reconcile",
                     "fence_battery", "organ_battery", "research_artifacts", "engine_registry",
                     "search_paradigm_census", "producer_census", "productivity_census",
                     # Tier-1 B1/B7/B10/B11: the release bit, the scientists' league table, the
                     # failure prior and the unified EVIG acquisition are all the machine
                     # measuring and scheduling itself.
                     "release_authority", "scientist_standings", "failure_prior",
                     "evig_acquisition",
                     # INDEPENDENCE AT INTAKE: the ladder, the grid occupancy and the mutation
                     # mix that decide whether an hour of judge buys independent ground or
                     # another constant. The machine measuring its own breadth: meta.
                     "independence_intake",
                     # ATTRIBUTION AT BIRTH: who produced every cell and from which
                     # region, stamped at the registry doors. The machine measuring its
                     # own lineage: meta.
                     "attribution_census",
                     "runtime_attestation", "self_repair"), "meta"),
    # japan: the Japan research division (the principal's 47-section mandate, hourly)
    **dict.fromkeys(("japan_department",), "japan"),
    # mathlab: the AI mathematics research civilization -- twenty-eight mathematical traditions
    # in parallel over the world model's residual, every object through the same gauntlet, credit
    # back to the mathematical method (principal 2026-09-17 / 2026-09-22). Its own 24/7 resident.
    **dict.fromkeys(("math_lab", "expression_factory", "physics_lab", "coevolution"),
                    "mathlab"),
    # regions: the global native-market research OS over every country lab, plus the four
    # GLOBAL-LAYER forests (web, academic+code, physical data, market data) -- layers of the
    # world that would be mined seventeen times over if each region hunted them itself.
    **dict.fromkeys(("global_research_os", *GLOBAL_FOREST_LEGS), "regions"),
    # the forest federation: one department per regional civilization, each its own resident
    **{f"forest_{_fid}": _fid for _fid in FOREST_DEPARTMENTS},
    # the read-only join behind the 24/7 dashboard: it measures nothing new, it only puts what
    # the desk already measured into one document with each value's source and age. `rest`
    # because it must never compete with a producing department for the hour's compute.
    "desk_dashboard_state": "rest",
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


#: POSITION DECIDED WHETHER A LEG RAN, AND NINETEEN LEGS LOST (measured 2026-09-23).
#: `main()` is a straight line of ~325 `_costed` calls and `MT5-HourlyCore` gives it 40 minutes
#: (ExecutionTimeLimit=PT40M). A pass out of clock is killed WHERE IT STANDS and the next trigger
#: restarts at the top, so the legs past the kill point are not late -- they are unreachable, and
#: they are the same legs every hour. The compute ledger (89,986 rows) measured the result: 19 of
#: 112 CORE_LEGS had NEVER executed once, and the reach was COLLAPSING as organs were wired into
#: the head -- head legs last ran 21:15, the middle 11:15, and everything past `residual_queue`
#: had not run since the previous day at 23:05.
#:
#: The cure is the law-gate battery's (`run_law_gate.rotate_gate`): rotate the roster across
#: passes inside a stated window and publish by name what the window did not reach. Rotation
#: decides MEMBERSHIP only -- legs still execute in file order, so every "must run after" comment
#: below still holds -- and it never shrinks the work: a deferred leg leads the next pass, and
#: the budget it is charged against is the scheduler's own limit, which rotation did not create.
_ROTATION: dict[str, object] = {}


def _rotation() -> object | None:
    """This pass's membership decision, built once on the first leg and reused by every later one.

    NEVER FAILS THE PASS, for the same reason `_costed` does not: a scheduler that can be taken
    down by the thing measuring it is removed within a week, correctly. An unavailable rotation
    module means every leg runs exactly as it did before this file learned to rotate.
    """
    if "built" in _ROTATION:
        return _ROTATION.get("decision")
    _ROTATION["built"] = True
    _ROTATION["decision"] = None
    try:
        from libs.ops import leg_rotation as _lr
        full = _lr.legs_in_order(Path(__file__).resolve())
        roster = [leg for leg in full if in_plan(leg)]
        att = _lr.read_attendance(
            prior=_lr.Attendance.from_json(_lr.load_record().get("attendance")))
        dec = _lr.plan_pass(roster, att, plan=HOURLY_PLAN, full_roster=full)
        _ROTATION.update({"decision": dec, "attendance": att, "lr": _lr,
                          "started": datetime.now(UTC), "ran": []})
        print(f"leg rotation plan={HOURLY_PLAN} roster={len(roster)}/{len(full)} "
              f"admitted={len(dec.admitted)} deferred={len(dec.deferred)} "
              f"budget={dec.budget_s:.0f}s planned={dec.planned_s:.0f}s "
              f"never_run={len(dec.never_run)}", flush=True)
        if dec.never_run:
            print(f"  NEVER RUN ({len(dec.never_run)}): {', '.join(dec.never_run[:40])}",
                  flush=True)
        # PUBLISHED BEFORE THE FIRST LEG RUNS. A pass killed at its 40-minute limit never reaches
        # its own epilogue, which is precisely how the cycle came to hold no record of what it
        # could not reach. `never_run` is known here, so it is on disk here.
        _lr.record(dec, att, [], started=_ROTATION.get("started"), complete=False)
    except Exception as exc:
        print(f"leg rotation UNAVAILABLE ({type(exc).__name__}: {exc}); "
              "every leg runs in file order as before", flush=True)
    return _ROTATION.get("decision")


def _rotation_publish() -> None:
    """Publish what this pass ran, what it deferred, and what has NEVER run -- by name."""
    dec = _ROTATION.get("decision")
    lr = _ROTATION.get("lr")
    att = _ROTATION.get("attendance")
    if dec is None or lr is None or att is None:
        return
    with suppress(Exception):
        doc = lr.record(dec, att, list(_ROTATION.get("ran") or []),      # type: ignore[attr-defined]
                        started=_ROTATION.get("started"))
        print(f"leg rotation recorded: ran={len(doc.get('ran_this_pass') or [])} "
              f"deferred={doc.get('n_deferred')} never_run={len(doc.get('never_run') or [])} "
              f"outside_{doc.get('window_h')}h={len(doc.get('outside_window') or [])}", flush=True)


AUTO_LEGS_FILE = BASE / "data" / "auto_legs.json"


def _auto_leg(entry: dict, leg: str | None = None) -> dict:
    """Run one auto-clocked organ under its PRICED budget; a dict result, never a raise.

    `leg` is the costed leg name so `cycle_pricing` can price this organ like any other; without
    it the entry's own measured budget stands, which is what it was before B27."""
    organ = str(entry.get("organ") or "")
    target = REPO / organ
    if not target.exists():
        return {"exit_code": None, "status": "MISSING", "why": f"{organ} is not in the tree",
                "at": datetime.now(UTC).isoformat()}
    budget = max(15, int(entry.get("budget_s") or 120))
    if leg:
        budget = max(15, _priced_budget(leg, budget)[0])
    cwd = BASE if organ.startswith("desks/mt5/") else REPO
    try:
        r = _run_tree([sys.executable, "-u", "-W", "ignore", str(target),
                       *[str(a) for a in (entry.get("argv") or [])]],
                           capture_output=True, text=True, cwd=str(cwd), timeout=budget,
                           check=False)
        # STDERR IS KEPT SEPARATELY, and that is not cosmetic. `tail` is `stdout or stderr`, so a
        # leg that printed ANYTHING to stdout before dying lost its traceback entirely -- which is
        # why `coverage_tensor` exiting 1 on 199 of its last 204 passes never told anyone WHY.
        # The write-or-explain contract reports the last lines of stderr on a failure, and it can
        # only do that if they survive to here.
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "stderr_tail": (r.stderr or "")[-1200:],
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
    # THE ORDER IS THE CONTROLLER'S (Tier-1 B27). When the hour runs short the legs at the back
    # of this list are the ones that do not run, so position IS an allocation -- and until now it
    # was whatever order the wiring CEO happened to write the file in. `cycle_pricing.order`
    # sorts by price with every leg staler than its scout window pulled to the FRONT, so a
    # cheaply-priced leg is delayed, never starved. An unavailable pricer leaves the order alone.
    named = [(str(e.get("leg") or ("auto_" + Path(str(e["organ"])).stem)), e) for e in chosen]
    try:
        import cycle_pricing
        rank = {n: i for i, n in enumerate(cycle_pricing.order([n for n, _e in named]))}
        named.sort(key=lambda ne: rank.get(ne[0], len(rank)))
    except Exception as exc:
        print(f"auto legs: unpriced order ({type(exc).__name__}: {exc})", flush=True)
    for name, e in named:
        out[name] = _costed(name, lambda e=e, n=name: _auto_leg(e, n))
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
    # THE ROTATION, AND WHY IT IS HERE RATHER THAN AT THE CALL SITES. Every leg passes through
    # this one boundary, so membership can be decided for all 325 of them without moving a line
    # of `main()` -- which means the dependency order every leg comment states is untouched. A
    # ROTATED_OUT leg returns in microseconds, so the pass races past it and the 40-minute clock
    # actually reaches the tail; it is the FIRST thing admitted next pass. No ledger row, for the
    # same reason SKIPPED_BY_PLAN writes none: it did not run here, and `opportunity_cost` and
    # the meta-controller's epoch must read that truth rather than a phantom run.
    _rot = _rotation()
    if _rot is not None:
        _ok, _why = _rot.should_run(name, _ROTATION.get("attendance"),   # type: ignore[attr-defined]
                                    (datetime.now(UTC)
                                     - _ROTATION["started"]).total_seconds())   # type: ignore[operator]
        if not _ok:
            return {"status": "ROTATED_OUT", "plan": HOURLY_PLAN, "why": _why,
                    "at": datetime.now(UTC).isoformat(timespec="seconds")}
        _ran = _ROTATION.get("ran")
        if isinstance(_ran, list):
            _ran.append(name)
    try:
        from libs.ops.compute_ledger import close_run, open_run
    except Exception as exc:
        # LOUD, NOT SILENT (theirs, 2026-09-10). `compute_ledger` says in its own words that a
        # denominator which fails silently is a scaling law nobody can draw; this was the import
        # that could fail without a word.
        print(f"{name} compute ledger UNAVAILABLE: {type(exc).__name__}: {exc}", flush=True)
        open_run = close_run = None                                     # type: ignore[assignment]
    # THE PRICE RIDES ONTO THE LEDGER ROW (Tier-1 B27's consumer). `close_run` writes `**meta`
    # into the compute-ledger row, so every hourly row now carries the seconds the controller
    # ALLOWED this leg beside the seconds it actually spent -- which is the only way a later
    # reader can tell a leg that was priced down from one that finished early. A missing pricer
    # writes nothing extra and the row is exactly what it always was.
    _meta: dict[str, object] = {}
    try:
        import cycle_pricing
        _row = (cycle_pricing.plan().get("legs") or {}).get(name)
        if isinstance(_row, dict):
            _meta = {"applied_budget_s": _row.get("planned_s"),
                     "price_factor": _row.get("factor"),
                     "priced_by": ",".join(_row.get("priced_by") or [])}
    except Exception:
        _meta = {}
    run = open_run(name, kind="hourly_cycle", **_meta) if open_run else None
    # THE WRITE-OR-EXPLAIN CONTRACT (2026-09-23). Stat the leg's DECLARED artifact before and
    # after, at the one boundary every leg passes through, so the check covers every leg at once
    # instead of organ by organ. See `libs/ops/write_or_explain.py` for the eight silent failures
    # of one day that this exists to end; the short version is that a leg exiting 0 having written
    # nothing was, until this line, indistinguishable from a leg with nothing to write.
    _woe = _woe_before(name)
    _woe_t0 = time.monotonic()
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
        _woe_after(name, _woe, None, raised=detail, wall_s=time.monotonic() - _woe_t0)
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
    _advance_watermark(name, outcome)
    _woe_after(name, _woe, out, wall_s=time.monotonic() - _woe_t0,
               verdict_exits=VERDICT_EXITS.get(name, ()))
    return out


def _woe_before(name: str) -> dict:
    """Stat leg `name`'s DECLARED artifact(s) before it runs. Never fails the leg."""
    try:
        from libs.ops.write_or_explain import before_leg
        return before_leg(name)
    except Exception:
        return {}


def _woe_after(name: str, before: dict, out: object, *, raised: str = "",
               wall_s: float | None = None, verdict_exits: tuple = ()) -> None:
    """THE WRITE-OR-EXPLAIN VERDICT: did the leg write what it declared, or say why not?

    PRINTS THE DEFECT, which is the entire point -- SILENT_NO_OP had no name and no line of
    output anywhere on this desk until today, and an organ producing nothing looked exactly like
    an organ with nothing to produce. A leg that wrote, or that named its reason, says nothing
    here: the noise belongs to the failures.

    Never fails the leg, for the reason the compute ledger and the event log do not: an organ
    that dies because its telemetry failed is worse than one that runs untelemetered.
    """
    try:
        from libs.ops.write_or_explain import DEFECTS, observe
        rec = observe(name, before, out, raised=raised, wall_s=wall_s,
                      verdict_exits=tuple(verdict_exits))
        if str(rec.get("verdict")) in DEFECTS:
            print(f"  {rec['verdict']} {rec.get('detail', '')}", flush=True)
            tail = str(rec.get("stderr_tail") or "").strip()
            for line in tail.splitlines()[-5:]:
                print(f"      stderr| {line[:160]}", flush=True)
    except Exception as exc:
        print(f"  write-or-explain not recorded for {name}: {type(exc).__name__}: {exc}",
              flush=True)


def _advance_watermark(name: str, outcome: str) -> None:
    """THE LEG'S PROGRESS WATERMARK (LAWS.md 7). A PID is not health; a moving work counter is.

    One monotone counter per leg, advanced only when the leg actually COMPLETED -- a failed,
    timed-out or skipped leg leaves the watermark where it was, which is the whole point: the
    control plane reads a watermark that has not moved beyond the component's silence window as
    STALLED, and a leg that "ran" and failed every hour must look exactly like one that stopped.

    Never fails the leg, for the same reason the compute ledger and the event log do not: an
    organ that dies because its telemetry failed is worse than one that runs untelemetered.
    """
    if not outcome.startswith("ok") and not outcome.startswith("verdict_exit"):
        return
    try:
        from libs.ops.control_plane import watermarks as wm
        cid = f"leg:{name}"
        prev = wm.read(cid) or {}
        wm.progress(cid, "leg_completions", int(prev.get("value") or 0) + 1,
                    run_id=f"hourly_cycle@{datetime.now(UTC).isoformat(timespec='seconds')}")
    except Exception as exc:
        print(f"  watermark for {name} not recorded: {type(exc).__name__}: {exc}", flush=True)


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
    # The causal invariance organ stops itself at --budget-s 600 and writes; the cap sits above.
    "causal_invariance": 700,
    # THE CONTROL PLANE'S OBSERVE PASS walks ~1,100 components, every watermark, every lease and
    # every mandatory edge. Its own budget is 600 s (it stops itself), so the cycle's cap sits
    # above that: a cap BELOW an organ's own budget is the truncated-job defect that cost this
    # desk eighty-four forward clocks.
    "control_plane": 660,
    "probation": 1_800,   # a pass is 40 organs; at 720 s it was cut at ~12 min every hour
    "enrol_clocks": 2_700,
    # Both stop themselves at --budget-s 300 and write their artifact; the caps sit above their
    # own budgets for the reason `enrol_clocks` was raised -- a cap below an organ's budget
    # truncates it at the same prefix every hour. `judging_throughput` must also finish BEFORE
    # the gauntlet leg it sizes, which is the other reason it is cheap by design.
    "judging_throughput": 400,
    "forward_enrolment": 400,
    # THE FOUR ACTIVATION LEGS ARE SEARCHES, NOT RENDERERS. `weak_signals` rebuilds member
    # signals for up to 24 members across 67 symbols and its own `run()` already self-limits at
    # 2400s; a cycle budget below that would kill it at the same prefix every hour, which is the
    # failure `enrol_clocks` was raised for. The other three get room to reach their data.
    "weak_signals": 2_700,
    "residual_factors": 1_800,
    "exogenous_search": 1_200,
    # THE THREE 2026-09-17 ORGANS. Each subprocess timeout sits ABOVE the organ's own internal
    # budget, so it stops itself and WRITES its artifact rather than being killed with the pass
    # half done. A cycle cap below the organ's own budget is the `enrol_clocks` defect exactly:
    # truncated at the same prefix every hour, reported as scheduled, and never finishing.
    "world_model": 1_500,
    "representation_forge": 1_100,
    # THE FEATURE COMPILER runs the forge over its own typed fields under a 900 s budget and the
    # ACQUISITION SCIENTIST samples under 600 s; each cap sits above the organ's own budget so
    # it stops itself and writes its artifact rather than being killed at the same prefix.
    "feature_compiler": 1_000,
    "data_acquisition_scientist": 700,
    "residual_hunt": 800,
    # THE META-EVOLUTION LAYER stops itself at 900 s and writes; the cycle's cap sits above.
    "research_evolution": 1_020,
    # THE TWO LAWS-5m ORGANS each stop themselves at their own 900 s `--budget-s` and write
    # their artifact; the cycle's cap sits above that for the reason `enrol_clocks` was raised.
    "event_graph_lab": 1_000,
    "attribution_reconcile": 400,
    "macro_state_engine": 700,
    "research_artifacts": 400,
    "engine_registry": 400,
    "counterfactual_attribution": 700,
    "trend_core": 700,
    "event_surprise": 400,
    "counterexample_agent": 700,
    "search_paradigm_census": 700,
    "replication_civilization": 1_000,
    # The dislocation lab stops itself at --budget-s 900 and writes; the cap sits above it.
    "dislocation_lab": 1_000,
    # The intake measurement stops itself at --budget-s 240: one registry scan and three
    # artifact reads. The cap sits above it.
    "independence_intake": 300,
    # The attribution census stops itself at --budget-s 240: two registry scans and one
    # bounded backfill that commits per chunk and resumes. The cap sits above it.
    "attribution_census": 300,
    # The coverage drain stops itself at --budget-s 900 -- and it scales that DOWN further off
    # measured free memory, because its cost is network wait on the box that also holds the
    # terminal. The cap sits above its own budget for the reason `enrol_clocks` was raised: a
    # cap below an organ's budget truncates it at the same prefix every hour, and for a drain
    # that would mean the same rows at the head of the queue never being reached.
    "coverage_drain": 1_000,
    # Judge coverage stops itself at --budget-s 120; it reads two files and sorts. The cap sits
    # above its own budget for the reason every other leg's does.
    "judge_coverage": 300,
    # Orthogonality yield is one indexed scan of the candidate registry, one pass over the gate
    # ledger and 79 leave-one-out SVDs of a 79 x ~1000 indicator matrix. Measured 2026-09-23 on
    # the trading box against 323,313 registry rows and 146,359 ledger rows: under a minute. The
    # cap sits above that for the reason every other leg's does.
    "orthogonality_yield": 300,
    # Effective trials stops itself at --budget-s 300; its cost is one O(m^2) similarity matrix
    # per grid cell, and grid cells are small (the live docket's largest holds ~470 rows). The cap
    # sits above its own budget for the reason every other leg's does.
    "effective_trials": 700,
    # The net-edge spine stops itself at --budget-s 600 and writes NET_EDGE.json plus the
    # intake join file; the cap sits above it so the hour is never cut at the same prefix.
    "net_edge": 700,
    # Cost truth stops itself at --budget-s 600 (80% of it inside the terminal walk, which is
    # where the M1 pulls are) and resumes from its own cursor next hour, so a cut hour costs
    # coverage and never the artifact. The cap sits above its budget.
    "cost_truth": 700,
    # The conversion maximiser stops itself at --budget-s 900 and writes CONVERSION_MAXIMISER.json
    # plus its ratchet; the cap sits above its own budget for the reason `enrol_clocks` was
    # raised -- a cap below an organ's budget truncates it at the same prefix every hour.
    "conversion_maximiser": 1_000,
    # The producer census relights at most six dark producers at 240s each and re-measures after
    # every repair; the cap sits above 6*240 so a pass is never cut inside a repair it has
    # already started, which would leave a producer half-run and the census judging the stub.
    "producer_census": 1_600,
    # The productivity census is a read-only sweep of two rosters, the alpha registry and the
    # compute ledger; it finishes in seconds and its own --budget-s 300 bounds a pathological
    # registry, so the cap only has to sit above that.
    "productivity_census": 400,
    # The sandbox runner stops itself at --budget-s 900 (each system inside its ROI share) and
    # writes SANDBOX_RUNNER.json; the cap sits above it so it is never cut at the same prefix.
    "sandbox_runner": 1_000,
    # The supply line stops itself at --budget-s 600 (one pinned wheel at a time, ROI order) and
    # the roster generator at 120; both caps sit above their own budgets for the same reason.
    "sandbox_provision": 1_600,
    "sandbox_roster": 200,
    # The physics lab stops itself at --budget-s 600 and writes PHYSICS_LAB.json; the cap sits
    # above it so the institution's pass is never cut at the same prefix every hour.
    "physics_lab": 700,
    # The certificate-truth audit reads six JSON stores and stops itself at --budget-s 120.
    # The experiment spine stops itself at --budget-s 600 (conversion capped at 55% of it so
    # the graph refresh, the credit ledger, the prior update and the funnel always run) and
    # writes both artifacts; the cycle's cap sits above its own budget for the reason
    # `enrol_clocks` was raised -- a cap below an organ's budget truncates it at the same prefix.
    "experiment_spine": 700,
    "certificate_truth": 150,
    # Each standing battery stops itself at --budget-s 600 (it starts no organ it cannot finish
    # inside what is left); the cap sits above that so a rotation is never cut at the same prefix
    # every hour, which would starve the tail of the roster permanently.
    "fence_battery": 720,
    "organ_battery": 720,
    # The loop liveness prover stops itself at --budget-s 240; the cap sits above it. It reads
    # the registry and the artifacts only -- measured 2.3 s on the box -- so the budget is head-
    # room for a busy sqlite, never a size it expects to use.
    "loop_liveness": 300,
    # The clock-liveness organ stops itself at --budget-s 300 and spends most of it inside the
    # re-enrolment actuator, which fetches bars for the frozen identities; the cap sits above it
    # so the repair is never cut at the same prefix every hour -- the failure `enrol_clocks` was
    # raised for, and the one this organ exists to catch.
    "clock_liveness": 420,
    # The expression factory stops itself at --budget-s 600 and writes; the cap sits above it.
    "expression_factory": 720,
    # The closed co-evolution stops itself at --budget-s 900 (breeding, then the islands) and
    # writes COEVOLUTION.json; the cap sits above it so it is never cut at the same prefix.
    "coevolution": 1_020,
    # The model-family civilization stops itself at --budget-s 600 and writes MODEL_SEARCH.json.
    "model_search": 720,
    # the organ's own budget is 900 s; the cap sits above it so it stops itself, never cut
    "market_constitution": 1_020,
    # A FOREST IS GIVEN THE BUDGET IT IS ASKED FOR. Each leg passes `--budget-s 3000` down to
    # `forest_runner`, which divides it across eleven parallel agents; a 720 s cycle cap would
    # SIGKILL every forest at the same prefix every hour -- the truncated-job failure that cost
    # this desk eighty-four forward clocks -- so the cycle's own limit sits above it.
    **{f"forest_{_fid}": 3_300 for _fid in
       (*FOREST_DEPARTMENTS, "global_web", "global_academic_code", "global_physical_data",
        "global_market_data")},
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
    # THE META CONTROLLER'S PRICE SETS THE SECONDS (Tier-1 B27). `LEG_BUDGET_SEC` is now the
    # BASE, not the answer: `cycle_pricing` scales it by the hour's rank price, floors every leg
    # at a scout budget, and can never reduce the hour's total. An unavailable pricer returns the
    # base unchanged, so this line is exactly what it was whenever the price cannot be read.
    budget, _price_rec = _priced_budget(name, LEG_BUDGET_SEC.get(name, SEARCH_BUDGET_SEC))
    try:
        r = _run_tree([sys.executable, "-u", "-W", "ignore", str(target), *args],
                           capture_output=True, text=True, cwd=str(root),
                           timeout=budget, check=False)
        # STDERR IS KEPT SEPARATELY, and that is not cosmetic. `tail` is `stdout or stderr`, so a
        # leg that printed ANYTHING to stdout before dying lost its traceback entirely -- which is
        # why `coverage_tensor` exiting 1 on 199 of its last 204 passes never told anyone WHY.
        # The write-or-explain contract reports the last lines of stderr on a failure, and it can
        # only do that if they survive to here.
        return {"exit_code": r.returncode, "tail": (r.stdout or r.stderr or "")[-300:],
                "stderr_tail": (r.stderr or "")[-1200:],
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


def session_structure() -> dict:
    """Derive every instrument's own session from its own bars, and aim the breakout at it.

    WHY IT IS ON A CLOCK AND NOT A ONE-OFF. A venue changes its hours, a CFD's liquidity moves
    with its underlying, and a new instrument arrives in the registry -- all of which change where
    the quiet run sits. A window derived once is right on the day it is written and silently
    wrong afterwards, which is the same failure mode as a hand-kept symbol list.

    Measured 2026-09-23: 1,174 of 2,248 `session_range_breakout` verdicts NEVER FIRED, because
    their range window was inherited from gold rather than derived. Cheap on repeat -- it reads
    parquet already on disk and donates through the ordinary EXACT_RECIPE door.
    """
    return _producer("session_structure_miner", "research/session_structure_miner.py")


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
    # THE MOAT EXCHANGE, PRICED AND CLAIMED (Tier-1 M6 + M4). Measures novelty vs live,
    # novelty vs graveyard and independence on queued candidates -- the three factors
    # `registry.score_candidate` multiplies and 8,741 rows carried as PRIOR -- rescores
    # them, then lets each department bid through `claim_candidates` and donates the
    # claims into the intake the docket is built from.
    mcp = _costed("moat_candidate_compiler", lambda: _producer(
        "moat_candidate_compiler", "research/moat_candidate_compiler.py", "--once",
        "--budget-s", "180"))
    # THE PROGRAM DATABASE (Tier-1 Q3): parameterised ALGORITHM configs per class --
    # search policy, regime detector, execution model, cost model, validator battery --
    # with lineage, evolved by mutation/crossover and scored by each class's own organ.
    adb = _costed("algorithm_db", lambda: _producer(
        "algorithm_db", "research/algorithm_db.py", "--once", "--budget-s", "120"))
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
    # ---------------------------------------------------------------- THE CLOSED-LOOP B-ROWS
    # Tier-1 phase B, rows B1-B11 (2026-09-23). Each was PARTIAL with a named gap; each organ
    # below closes its own gap, leaves an artifact and has a named consumer. Order matters where
    # one reads another: the release bit first (it is about the code everything else runs), then
    # the per-asset world model (the failure prior's state half reads it), the residual map
    # (which aims `exogenous_search` later in this cycle), the failure prior (which the compiler
    # stamps), the scientists' league table (which the docket ranks by), the docket itself, and
    # finally the unified EVIG acquisition, which prices what the four above produced.
    rla = _costed("release_authority", lambda: _producer(
        "release_authority", "research/release_authority.py", "--once"))
    rgh = _costed("regime_hierarchy", lambda: _producer(
        "regime_hierarchy", "research/regime_hierarchy.py", "--once", "--budget-s", "900"))
    rsm = _costed("residual_map", lambda: _producer(
        "residual_map", "research/residual_map.py", "--once"))
    fpr = _costed("failure_prior", lambda: _producer(
        "failure_prior", "research/failure_prior.py", "--once", "--budget-s", "300"))
    sst = _costed("scientist_standings", lambda: _producer(
        "scientist_standings", "research/scientist_standings.py", "--once"))
    fce = _costed("frontier_ceo", lambda: _producer(
        "frontier_ceo", "research/frontier_ceo.py", "--apply"))
    rtr = _costed("research_tree", lambda: _producer(
        "research_tree", "research/research_tree.py", "--apply"))
    rpd = _costed("representation_discovery", lambda: _producer(
        "representation_discovery", "research/representation_discovery.py",
        "--once", "--budget-s", "900"))
    eva = _costed("evig_acquisition", lambda: _producer(
        "evig_acquisition", "research/evig_acquisition.py", "--once"))
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
    # NOTHING IS PARKED (principal 2026-09-23): every queue in the desk, its depth, its oldest
    # row's age and its measured drain rate, in one artifact. scripts/check_no_queues.py fences it.
    qcn = _costed("queue_census", lambda: _producer("queue_census", "research/queue_census.py",
                                                    "--once", "--budget-s", "120"))
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
    # SYNTHETIC REGIMES: eleven named worlds absent from history applied to certified and live
    # sleeves for hidden structural failure modes; synthetic profit is never a merit.
    syr = _costed("synthetic_regimes", lambda: _producer("synthetic_regimes",
                                                          "research/synthetic_regimes.py",
                                                          "--max-sleeves", "25"))
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
    # LIVE TRADE ATTRIBUTION, RECONCILED (Tier-1 W0): MetaTrader truncates the sleeve into the
    # position comment, so the exact-name join reads 4.6% on a book whose trades all have
    # owners. The reconciler recovers them by unique prefix and by the tp/sl price the terminal
    # itself wrote, and PUBLISHES BY NAME every deal it still cannot reach.
    atr = _costed("attribution_reconcile", lambda: _producer(
        "attribution_reconcile", "research/attribution_reconcile.py", "--once",
        "--budget-s", "300"))
    # COUNTRY/REGION STATE BLOCKS AND THE EDGE-CHANGE HUNTER (W7): the state vector was
    # single-country and the causal graph never published its edge CHANGES as objects a
    # hunter could reach. A link that turned on, flipped sign or died is now a dated ROW
    # with a change-point p-value, and the top ones are donated as hypotheses.
    mse = _costed("macro_state_engine", lambda: _producer(
        "macro_state_engine", "research/macro_state_engine.py", "--once", "--budget-s", "600"))
    # THE HASH-LINKED RESEARCH CHAIN, POPULATED (W9): the chain library and its verifier
    # landed and the chain was EMPTY, which verifies clean at n=0. The gauntlet and the
    # promoter are sealed, so the writer is a HARVESTER: it appends the SOURCE -> CLAIM ->
    # HYPOTHESIS -> CODE -> DATA -> CONFIG -> RESULTS -> REVIEW records the artifacts
    # those organs already leave behind, idempotently, and reports a broken link.
    rart = _costed("research_artifacts", lambda: _producer(
        "research_artifacts", "research/research_artifacts.py", "--once", "--budget-s", "300"))
    # P(certified | method, domain) (W17): which research ENGINE actually converts in which
    # asset class, as a Beta-Binomial posterior with its credible interval and a yield per
    # compute hour, so compute can follow yield. It caps nothing.
    engr = _costed("engine_registry", lambda: _producer(
        "engine_registry", "research/engine_registry.py", "--once", "--budget-s", "300"))
    # THE FUSED GLOBAL POSTERIOR, THE CONDITIONAL SLEEVE DISTRIBUTIONS AND THE PER-TRADE
    # COUNTERFACTUAL (U3): what the same rule would have returned in the other state
    # bucket, at the modelled cost, and not taken at all. It allocates nothing.
    cfat = _costed("counterfactual_attribution", lambda: _producer(
        "counterfactual_attribution", "research/counterfactual_attribution.py", "--once",
        "--budget-s", "600"))
    # THE CORE OF THE CORE-PLUS-SLEEVE BOOK (W21): a trend-following core across the whole
    # multi-asset universe, volatility-scaled, read as ONE bet through its own measured
    # correlation structure, donated through the normal proposer contract so the ten
    # gates judge it like anything else. No privileged path to capital.
    tcor = _costed("trend_core", lambda: _producer(
        "trend_core", "research/trend_core.py", "--once", "--budget-s", "600"))
    # ACTUAL AGAINST CONSENSUS (W21): the standardized surprise per calendar event and the
    # measured reaction of every instrument to it, by horizon and regime. The collector is
    # lawful-pages-only and degrades to UNMEASURED rather than inventing a consensus.
    esur = _costed("event_surprise", lambda: _producer(
        "event_surprise", "research/event_surprise.py", "--once", "--budget-s", "300"))
    # THE ADVERSARY THAT ATTACKS A HYPOTHESIS BEFORE A TRIAL IS SPENT ON IT (W6): placebo
    # symbol, placebo date, sign flip, neighbouring parameter, excluded window. It records
    # evidence on the registry row and changes no status: the sealed gauntlet and the
    # promoter remain the only judges.
    cexa = _costed("counterexample_agent", lambda: _producer(
        "counterexample_agent", "research/counterexample_agent.py", "--once", "--budget-s", "600"))
    # THE SEARCH CONTROLLER AND THE POPULATIONS GET A CLOCK, AND THE PARADIGMS GET A
    # REDUNDANCY MEASURE (W6): pairwise overlap between what each paradigm proposed, an
    # effective-paradigm count, and NOT_SCHEDULED by name for every paradigm that did not
    # run -- which is the row the wiring hunter needs.
    spc = _costed("search_paradigm_census", lambda: _producer(
        "search_paradigm_census", "research/search_paradigm_census.py", "--once",
        "--budget-s", "600"))
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
    # THE EVENT-RESPONSE ATLAS: measured reactions per event kind x instrument x horizon x
    # conditioner from the desk's own calendar and bars; clearing cells donated (macro dept).
    era = _costed("event_response_atlas", lambda: _producer("event_response_atlas",
                                                             "research/event_response_atlas.py",
                                                             "--budget-s", "240"))
    # NEWS AS A FIRST-CLASS EVENT STREAM: the fast lane classifies every new collected document,
    # nudges data/world_state.json in logit space with its uncertainty, and lodges a re-solve
    # REQUEST the allocator may read; the deep lane interprets what clears novelty x surprise.
    # Nothing here sizes. `--once` is the hourly pass; the 60 s `--resident` loop is a box task
    # that does not exist yet and is a NAMED gap on the ledger row, not a silent absence.
    nes = _costed("news_event_stream", lambda: _producer(
        "news_event_stream", "research/news_event_stream.py", "--once"))
    # THE EVENT-CONDITIONED SLEEVES: eight family cards validated BEFORE an event, so a headline
    # moves a posterior instead of inventing a strategy; hosted cards donated, unhostable ones
    # written to program_candidates.jsonl with the gap named. Publishes p_alpha_positive_now.
    evs = _costed("event_sleeves", lambda: _producer("event_sleeves", "research/event_sleeves.py"))
    # THE WORLD-MODEL LAB: do(shock) propagated over the admitted causal graph with measured
    # participant responses; hypotheses donated with authority ZERO (the gauntlet judges on
    # real history). Macro department.
    wlb = _costed("world_lab", lambda: _producer("world_lab", "research/world_lab.py",
                                                  "--max-donations", "20"))
    # THE CAUSAL DISCOVERY LAB: PCMCI-style lagged discovery with FDR, a NOTEARS-lite DAG,
    # economic restrictions and edge classes on the PIT panel; an LLM never invents an edge.
    clb = _costed("causal_lab", lambda: _producer("causal_lab", "research/causal_lab.py"))
    # THE CROSS-MARKET EVENT GRAPH WITH ITS CAUSAL / MECHANISM ADJUDICATOR (LAWS 5m): the graph
    # over events, entities, industries, commodities, countries, currencies, rates, flows and
    # MT5 assets built from the ontology, the country packs' seeds and the world causal graph;
    # a rotating slice of edges measured on the desk's own series (x_t against y_(t+lag)); the
    # newest queued candidates and every LIVE/STANDBY sleeve adjudicated through identification
    # -> estimation -> counterfactual -> refutation, verdicts recorded on the registry rows
    # (status untouched) and edge-derived seeds donated to the compiler. Macro department.
    egl = _costed("event_graph_lab", lambda: _producer("event_graph_lab",
                                                        "research/event_graph_lab.py",
                                                        "--once", "--budget-s", "900"))
    # THE GLOBAL PROBABILISTIC WORLD MODEL (principal 2026-09-17): forward log returns of the
    # hypothesis lane at 1h/4h/1d/5d from every PIT series the desk holds, strictly
    # anti-lookahead, with per-dataset contribution and the regime forecast. It ALLOCATES NO
    # CAPITAL -- it publishes epsilon so `residual_hunt` can hunt what it cannot explain.
    wmd = _costed("world_model", lambda: _producer("world_model", "research/world_model.py",
                                                    "--once", "--budget-s", "1200"))
    # THE CANONICAL RESEARCH REGISTRY (principal 2026-09-17: one registry, its research chain
    # populated by the organs that do the work): the bridge leg lands the desk's record --
    # candidates, trials, runs, cards+events, memories, workers -- and publishes the counts,
    # the conversion debt and the trial-chain verification. Core: runs every pass.
    rsy = _costed("registry_sync", lambda: _producer("registry_sync",
                                                      "research/registry_sync.py",
                                                      "--once", "--budget-s", "300"))
    # THE EVOLVABLE ONTOLOGY (Q10): new axes proposed, tested OOS against unexplained residual,
    # registered only after two consecutive passes. Discovery department.
    axp = _costed("axis_proposer", lambda: _producer("axis_proposer",
                                                      "research/axis_proposer.py",
                                                      "--budget-s", "240"))
    # THE PROGRAM-ALPHA LANE (D4): restricted executable programs in an auditable IR, slots
    # tuned by TPE on a cheap screen, winners to program_candidates.jsonl. Discovery.
    pal = _costed("program_alpha_lane", lambda: _producer("program_alpha_lane",
                                                           "research/program_alpha_lane.py",
                                                           "--budget-s", "240",
                                                           "--max-programs", "20"))
    # TRAJECTORY EVOLUTION (D2): whole research trajectories mutate at the step that failed and
    # cross only under causal compatibility; children donated as structured hypotheses.
    tev = _costed("trajectory_evolution", lambda: _producer("trajectory_evolution",
                                                             "research/trajectory_evolution.py",
                                                             "--budget-s", "240",
                                                             "--max-children", "30"))
    # THE RESEARCH-OS ARCHIVE (Q1/W12): a population of research policies competing on measured
    # productivity behind the immutable wall; the active policy's factors feed the budget. Meta.
    roa = _costed("research_os_archive", lambda: _producer("research_os_archive",
                                                            "research/research_os_archive.py"))
    # THE REGIME ROUTER (D8/Q16): P(alpha>0 | state) per sleeve and a per-sample router that is
    # active only where it beats the unrouted model out of sample. Forward department.
    rgr = _costed("regime_router", lambda: _producer("regime_router",
                                                      "research/regime_router.py"))
    # MACRO INTELLIGENCE FUSION (LAWS 5c, the second half of the principal's order). Every
    # macro-relevant ingested unit fused into regime posteriors, nowcasts, next-decision
    # expectations, a ranked news lane and TWO-SIDED suggestions the allocator MAY read through
    # the router's own `p_alpha_positive_now` convention. It writes its own file and never
    # `sleeves.json`, never an allocator file, and it sizes nothing. Macro department.
    mci = _costed("macro_intelligence", lambda: _producer("macro_intelligence",
                                                           "research/macro_intelligence.py",
                                                           "--budget-s", "240"))
    # THE MARKET CONSTITUTION COMPILER (LAWS 5m; U22/U23): exchange rules, auction states,
    # price bands, short-sale states, settlement, fee and HFT regimes as POINT-IN-TIME columns
    # on the desk's own tapes (data/rule_states/<venue>.parquet); every dated rule change run
    # as a natural experiment against an unaffected control venue with a placebo null; each
    # measured effect or null a DESK discovery; survivors donated to the compiler; the 2027
    # TSE random close pre-registered. It sizes nothing. Macro department.
    mcc = _costed("market_constitution", lambda: _producer("market_constitution",
                                                            "research/market_constitution.py",
                                                            "--once", "--budget-s", "900"))
    # THE MOAT SERIES REGISTRY + BUILDER (C20/W13): every proprietary series registered with its
    # depth, coverage, moat score and named gaps; derived tape series built per instrument-day.
    mos = _costed("moat_series", lambda: _producer("moat_series", "research/moat_series.py",
                                                    "--budget-s", "240", "--max-days", "3"))
    # THE SCOUT ROSTER (W4): every intelligence organ as a scout with a beat, a clock, a measured
    # yield and a cost; open beats named. Intel department.
    scr = _costed("scout_roster", lambda: _producer("scout_roster", "research/scout_roster.py"))
    # DESCENDANTS (W16): every survivor is the root of a family; each child moves along ONE axis
    # (instrument, session, horizon, exit, state, cross-market); coverage of the axes measured.
    dsc = _costed("descendants", lambda: _producer("descendants", "research/descendants.py",
                                                    "--max-per-root", "4", "--budget-s", "240"))
    # THE FORWARD SLOT RANKER (C15/W10): slots ranked by P(certify) x dElogW x diversification
    # / time to maturity; REPLACEABLE clocks reported with their missed-growth line, never acted.
    fsr = _costed("forward_slot_ranker", lambda: _producer("forward_slot_ranker",
                                                            "research/forward_slot_ranker.py"))
    # THE ANALYST PIPELINE (W5): leads -> triage -> structuring -> pre-screen -> donation ->
    # follow-up, every rejection coded and counted, conversion per lead kind. Intel department.
    anp = _costed("analyst_pipeline", lambda: _producer("analyst_pipeline",
                                                         "research/analyst_pipeline.py",
                                                         "--max-leads", "200",
                                                         "--budget-s", "240"))
    # THE KNOWLEDGE GRAPH (W2/M3): one lead schema; claims collapsed by dedupe key with
    # PRODUCED/BECAME/JUDGED/DUPLICATES/CONTRADICTS/DERIVES_FROM edges; unconverted leads named.
    kng = _costed("knowledge_graph", lambda: _producer("knowledge_graph",
                                                        "research/knowledge_graph.py",
                                                        "--max-rows", "5000"))
    # THE EVIDENCE ROUTER (LAWS 5e): every source walks DISCOVER -> CAPTURE METADATA ->
    # LEGAL/ACCESS -> EVIDENCE -> RESEARCH and lands three INDEPENDENT labels plus a quarantine
    # flag. Legality is a surgical router beside the research system, never a brake on it: an
    # unclear source is quarantined with its metadata kept, and the three prohibited labels are
    # refused WITH THE REASON rather than silently skipped. Intel department resident.
    evr = _costed("evidence_router", lambda: _producer("evidence_router",
                                                        "research/evidence_router.py",
                                                        "--once", "--budget-s", "600"))
    # THE UNKNOWN-UNKNOWNS RESIDUAL HUNT (principal 2026-09-17): the world model's epsilon
    # clustered by target x regime x session x calendar class x time of day, tested against a
    # circular-block permutation null, and every persistent cell turned into a search target
    # naming the missing dataset / participant / region / representation / mechanism /
    # interaction that could explain it. Intel department: it opens ground for the scouts.
    rhu = _costed("residual_hunt", lambda: _producer("residual_hunt", "research/residual_hunt.py",
                                                      "--once", "--budget-s", "600"))
    # INCREMENTAL ALPHA AFTER NEUTRALISATION (C9): every candidate the desk records a daily series
    # for, regressed on the CURRENT book's latent factors and on its survivor series, published
    # as the t of the intercept. The row's own next_step asked for a stage inside the sealed
    # `external_gauntlet`; this is the `hostile` -> `blind_reviewer` shape instead -- a library
    # with no side effects and a mount that publishes. It refuses nothing: the family-level t is
    # a TIE-BREAK inside merge_hypotheses.breadth_order and removes no row from the docket.
    rsg = _costed("residual_gate", lambda: _producer(
        "residual_gate", "research/residual_gate_mount.py", "--once", "--budget-s", "180"))
    # THE MOAT ALPHA FACTORY ENGINES (M5, principal 2026-09-17): the desk exploits everything it
    # has already learned. Each engine records discoveries in the canonical registry; the ones
    # that can host a family donate structured hypotheses through the same intake as every miner.
    mce = _costed("card_explosion", lambda: _producer("card_explosion",
                                                       "research/moat_card_explosion.py",
                                                       "--max-per-card", "40",
                                                       "--budget-s", "240"))
    mal = _costed("alpha_lineage", lambda: _producer("alpha_lineage",
                                                      "research/alpha_lineage_search.py",
                                                      "--budget-s", "240"))
    mgr = _costed("graveyard_resurrection", lambda: _producer("graveyard_resurrection",
                                                               "research/graveyard_resurrection.py",
                                                               "--max-candidates", "60",
                                                               "--budget-s", "240"))
    msd = _costed("shadow_discovery", lambda: _producer("shadow_discovery",
                                                         "research/shadow_discovery.py",
                                                         "--budget-s", "240"))
    # THE MISSED-TRADE ARCHAEOLOGIST (LAWS 5m, U35): every large adverse move, missed forward
    # move, bad exit and regime failure in the live and shadow ledgers, reconstructed from bars
    # that had closed before the decision; each answer a frozen prospective hypothesis or
    # dataset_request, credited only by later unseen evidence. Forward department.
    mta = _costed("missed_trade_archaeologist", lambda: _producer(
        "missed_trade_archaeologist", "research/missed_trade_archaeologist.py",
        "--once", "--budget-s", "600"))
    mfe = _costed("forward_exploitation", lambda: _producer("forward_exploitation",
                                                             "research/forward_exploitation.py"))
    mar = _costed("alpha_recombination", lambda: _producer("alpha_recombination",
                                                            "research/alpha_recombination.py",
                                                            "--max-combinations", "40",
                                                            "--budget-s", "240"))
    mui = _costed("unused_information", lambda: _producer("unused_information",
                                                           "research/unused_information.py",
                                                           "--budget-s", "120"))
    # THE REPRESENTATION FORGE (principal 2026-09-17): a dataset is never one feature. Surprise,
    # pace, z, revision, interaction and the composed grammar over every PIT series, PIT stamps
    # carried, ROI per representation in the registry. Data department: it makes inputs.
    rfg = _costed("representation_forge", lambda: _producer("representation_forge",
                                                             "research/representation_forge.py",
                                                             "--once", "--budget-s", "900"))
    # THE MULTIMODAL FEATURE COMPILER (LAWS 5m; RESEARCH 11): every ingested modality -- prices,
    # text claims through polyglot, the shadow/data-plane sensors, calendars, rule states,
    # positioning, macro releases -- typed into contracted, lineage-hashed representations with a
    # FEATURE GENOME and routed through the forge to the world model. Data: it makes inputs.
    fcp = _costed("feature_compiler", lambda: _producer("feature_compiler",
                                                         "research/feature_compiler.py",
                                                         "--once", "--budget-s", "900"))
    # THE UNIVERSAL DISCOVERY-TO-CELL COMPILER (M7): every discovery gets a disposition; the
    # closure under economic compatibility, twelve transformation miners, three gates, exact
    # rules compiled into the registry and the docket. Discovery department resident.
    dcp = _costed("discovery_compiler", lambda: _producer("discovery_compiler",
                                                           "research/discovery_compiler.py",
                                                           "--budget-s", "240",
                                                           "--max-discoveries", "200"))
    # THE CONVERSION MAXIMISER (principal 2026-09-23, "squeeze the life out of everything we get
    # and have"). The compiler above converts what ARRIVES; this drains the residue already in
    # the registry -- rows that arrived, failed one field of the compile contract and stopped.
    # It classifies every non-converted row by its exact blocker in the compilers' own defect
    # vocabulary, ACTS per class (supplies the standing re-judgement falsifier, binds a family,
    # resolves the instrument through the universe registry, names the missing data as an
    # acquisition task, routes prose to the naming seat), retires what the two-lane law and the
    # universe mandate forbid, and re-enqueues the rest with effective trials charged. It runs
    # AFTER `discovery_compiler` on purpose: this hour's arrivals are part of what it drains.
    # Discovery department, prediction layer.
    cvm = _costed("conversion_maximiser", lambda: _producer(
        "conversion_maximiser", "research/conversion_maximiser.py", "--once",
        "--budget-s", "900"))
    rdb = _costed("research_debt", lambda: _producer("research_debt",
                                                      "research/research_debt.py"))
    # THE INGESTION-EXPLOITATION CONTRACT (LAWS 5c, principal 2026-09-17). Every ingested unit --
    # seat row, claim, axis series, tape day, bar file, sleeve ledger, normalised document --
    # registered, disposed, and given EXACTLY ONE downstream state; a stranded unit becomes a
    # discovery so `discovery_compiler` closes it rather than a report nobody reads. It runs
    # AFTER the compiler on purpose: this hour's conversions are what it measures. Data dept.
    igl = _costed("ingestion_ledger", lambda: _producer("ingestion_ledger",
                                                        "research/ingestion_ledger.py",
                                                        "--budget-s", "240",
                                                        "--grace-hours", "24"))
    # ITS GATE: the exploitation ratchet (up only), the DATA STRANDING ratchet (down only) and
    # the twelve-question data-utilization audit per dataset. A cheap reader, so it is a CORE
    # leg -- a gate that never ran is a claim the desk cannot cash (L1.49). Meta dept.
    ige = _costed("ingestion_exploitation", lambda: _producer(
        "ingestion_exploitation", "scripts/check_ingestion_exploitation.py"))
    # THE MINING OBJECTIVE (M17/M18): the five sovereign KPIs, the miner reward and the
    # separation-of-powers check, from the registry. Meta.
    mob = _costed("mining_objective", lambda: _producer("mining_objective",
                                                         "research/mining_objective.py"))
    # THE FIVE-ROI DELAYED-CREDIT REALLOCATOR (LAWS 5f rules 10-12): every survivor credits its
    # source, region, representation and scientist along the provenance DAG; every failed family
    # becomes NEGATIVE KNOWLEDGE; regions, departments, trial budget and forward slots follow the
    # measured ROI, two-sided, with a scout floor nobody falls through. Meta department resident.
    rroi = _costed("research_roi", lambda: _producer("research_roi", "research/research_roi.py",
                                                      "--once", "--budget-s", "600"))
    # THE RESEARCH GAP MAP (M21): every economically valid cell of the breadth grid in one of
    # eight states, the highest-value holes named. Meta.
    rgm = _costed("research_gap_map", lambda: _producer("research_gap_map",
                                                         "research/research_gap_map.py",
                                                         "--budget-s", "240"))
    # THE AUTHORITATIVE COVERAGE TENSORS (U4, LAWS 5f). WORLD: country x sector x information
    # type x mechanism x representation x asset x session x regime x horizon x execution. FOREST:
    # country x language x source class x sector x mechanism x asset transmission x freshness x
    # accessibility. Every hole is an EXPLICIT frontier row with an EVIG breakdown and the one
    # move that raises it a rung, handed to the compiler as a `coverage_gap` discovery. Meta.
    cov = _costed("coverage_tensor", lambda: _producer("coverage_tensor",
                                                        "research/coverage_tensor.py",
                                                        "--once", "--budget-s", "900"))
    # THE COVERAGE DRAIN (principal 2026-09-23). The tensor above says WHICH INPUTS EXIST; this
    # leg makes the ones the desk already owns and has never read actually fall. It registers
    # every root the country packs declare and every ground in `deep_forest_sources.json`,
    # resolves the rows the evidence router minted with no url, refuses only the five ACTS of
    # LAWS 5e, crawls the rest through `moat_collectors`, verifies each pack's ten layers against
    # a registry row that was actually fetched, and publishes the day's single largest
    # information gap by expected value. `scripts/check_coverage_drain.py` ratchets the overdue
    # backlog DOWN. It was written because `loop_liveness` called the `sources_ingested` stage
    # STALLED -- 148 uncrawled, the oldest waiting 134 hours -- and nothing owned the number.
    cdr = _costed("coverage_drain", lambda: _producer("coverage_drain",
                                                       "research/coverage_drain.py",
                                                       "--once", "--budget-s", "900"))
    # THE JUDGE TESTS 100% OF WHAT THE DESK MINES (principal 2026-09-23). Measured from 120,000
    # gate verdicts: 18% of the judge went to `discovered` -- banned from live capital, 0 passes
    # -- while `cross_asset_residual` (55,190 mined), `overnight_drift` (26,721) and
    # `clock_transition` (20,081) barely appeared. The gauntlet is sealed and takes its docket in
    # order under a bar budget, so ORDER IS SELECTION and the fix belongs at intake: this leg
    # allocates the hour by UNJUDGED BACKLOG per family -- an equal floor to every family holding
    # one, the remainder in proportion -- and publishes mined/queued/judged/unjudged/oldest per
    # family. `merge_hypotheses` calls the same allocator when it writes the docket, so this leg
    # is the standing MEASUREMENT of what shipped; `scripts/check_judge_coverage.py` ratchets the
    # carried backlog DOWN. Data department, information layer.
    #
    # ORTHOGONALITY YIELD RUNS FIRST, because judge_coverage's ranking reads its artifact. The
    # principal's order of 2026-09-23 is that compute go to producers that yield ORTHOGONALITY and
    # to those that yield CERTIFICATES, both, so this leg measures both per producer -- the
    # leave-one-out drop in the candidate grid's effective rank when that producer's cells are
    # removed, and certificates per judge-hour from the gate ledger -- and publishes one factor
    # per axis. Both factors are one-sided at or above par, so this can lift a producer's
    # priority and can never lower it, and the 25% floor below is untouched. Data department.
    oyz = _costed("orthogonality_yield",
                  lambda: _producer("orthogonality_yield",
                                    "research/orthogonality_yield.py",
                                    "--once", "--budget-s", "120"))
    jcv = _costed("judge_coverage", lambda: _producer("judge_coverage",
                                                      "research/judge_coverage.py",
                                                      "--once", "--budget-s", "120"))
    # EFFECTIVE TRIALS: the multiplicity budget is charged in independent TESTS, not in docket
    # rows. Measures nominal vs effective per family (participation ratio of (grid cell, content)
    # identities within each mechanism), publishes the ratio, and writes the corrected campaign
    # charge into policy/gate_spec.yaml -- the one input the SEALED gauntlet reads for it. Data
    # department, information layer.
    eft = _costed("effective_trials", lambda: _producer("effective_trials",
                                                        "research/effective_trials.py",
                                                        "--once", "--budget-s", "300"))
    # GAUNTLET BACKPRESSURE (M23) and MINER SPECIALISATION (M24): the gauntlet talks back and
    # the organisation routes work by measured value per miner per domain. Meta.
    gbp = _costed("gauntlet_backpressure", lambda: _producer("gauntlet_backpressure",
                                                              "research/gauntlet_backpressure.py"))
    msp = _costed("miner_specialisation", lambda: _producer("miner_specialisation",
                                                             "research/miner_specialisation.py"))
    # THE TIER-5 RESIDUALS (mandate 90, 110, 131/132, 133, 134, 136, 97/98, 162). The allocator
    # publishes the payoff shapes and regimes it LACKS and they become research requests; the
    # departments bid compute for those bounties and the winners are funded next epoch; the
    # funnel's slowest stage is measured from the registry's own counts and compute shifts
    # TOWARD it; what pays during the book's own drawdown windows is mined from the live and
    # forward ledgers; every closed live deal gets an autopsy row; idea->cell->verdict->forward
    # ->live is timed; the decay-driven replenishment target is compared with what arrived; and
    # the dashboard joins the hour's artifacts. None of them cuts anything (GROWTH_GOVERNANCE
    # Rule 1): a bounty is a REQUEST, a bid is two-sided and never a cap.
    pbt = _costed("portfolio_bounty", lambda: _producer("portfolio_bounty",
                                                        "research/portfolio_bounty.py",
                                                        "--once", "--budget-s", "300"))
    rau = _costed("research_auction", lambda: _producer("research_auction",
                                                        "research/research_auction.py",
                                                        "--once", "--budget-s", "300"))
    btl = _costed("bottleneck_law", lambda: _producer("bottleneck_law",
                                                      "research/bottleneck_law.py",
                                                      "--once", "--budget-s", "300"))
    dam = _costed("drawdown_alpha_miner", lambda: _producer("drawdown_alpha_miner",
                                                            "research/drawdown_alpha_miner.py",
                                                            "--once", "--budget-s", "300"))
    tap = _costed("trade_autopsy", lambda: _producer("trade_autopsy",
                                                     "research/trade_autopsy.py",
                                                     "--once", "--budget-s", "300"))
    rlt = _costed("research_latency", lambda: _producer("research_latency",
                                                        "research/research_latency.py",
                                                        "--once", "--budget-s", "300"))
    arp = _costed("alpha_replenishment", lambda: _producer("alpha_replenishment",
                                                           "research/alpha_replenishment.py",
                                                           "--once", "--budget-s", "300"))
    # THE INTELLIGENCE REFINERY (M2/M8/M9/M10/M11): immutable captures and claims, the scout
    # swarm over the source frontier, the actor atlas. Intel department resident.
    mcl = _costed("moat_collectors", lambda: _producer("moat_collectors",
                                                        "research/moat_collectors.py",
                                                        "--budget-s", "300",
                                                        "--max-sources", "20"))
    sfr = _costed("source_frontier", lambda: _producer("source_frontier",
                                                        "research/source_frontier.py"))
    ssw = _costed("scout_swarm", lambda: _producer("scout_swarm", "research/scout_swarm.py",
                                                    "--once", "--budget-s", "600"))
    aat = _costed("actor_atlas", lambda: _producer("actor_atlas", "research/actor_atlas.py"))
    # THE UNDERSTANDING SEAT (2026-09-17, principal's permanent order): nothing the desk
    # collected is left unread. It runs AFTER the collectors and the scouts because it reads
    # what they produced -- every normalised moat document, every registry claim and every
    # intelligence row -- re-reads each natively through `libs/research/polyglot.py`, and asks
    # the LLM seats about whatever is still not understood. It also publishes the two gap lists
    # nothing else on this desk can produce: the languages with no terminology map, and the
    # language/source-layer cells with no NATIVE QUERY vocabulary. Intel department resident.
    usd = _costed("understanding_seat", lambda: _producer("understanding_seat",
                                                          "research/understanding_seat.py",
                                                          "--budget-s", "240"))
    # THE NETTING DIAGNOSTIC (R1/R2): sleeve intents netted per instrument, the currency-factor
    # exposure and effective rank of the gross book; publishes, sizes nothing. Execution.
    ntr = _costed("netting_report", lambda: _producer("netting_report",
                                                       "research/netting_report.py"))
    # THE EXECUTION-TAPE ALPHA ENGINE (M5 #5): P(adverse | spread, state, time) and delayed-vs-
    # immediate entry from the tape and the fills; discoveries for the compiler. Execution.
    exa = _costed("execution_alpha", lambda: _producer("execution_alpha",
                                                        "research/execution_alpha_miner.py",
                                                        "--budget-s", "240"))
    # THE PARADIGM ROUTER (M14): every lead meets every discovery paradigm; disagreement recorded.
    prr = _costed("paradigm_router", lambda: _producer("paradigm_router",
                                                        "research/paradigm_router.py",
                                                        "--budget-s", "240",
                                                        "--max-leads", "50"))
    # THE ONE META-CONTROLLER (F11/F27, canonical item 27): nine kinds of action priced in one
    # budget market; it was built on 2026-09-12 and clocked by nothing, which is why every
    # closed-loop reading said the controller had not started. Meta department resident.
    mtc = _costed("meta_controller", lambda: _producer("meta_controller",
                                                        "research/meta_controller.py",
                                                        "--apply"))
    # THE EXPERIMENT SPINE (RD-Agent closure items 1/4/5/11/16/20, principal 2026-09-22): every
    # research civilization's row compiles into ONE canonical ExperimentSpec, reaches the campaign
    # queue, lands in the experiment memory graph, sends credit back along its ancestry, moves the
    # priors the next allocation draws from, and is divided by what the hour cost in
    # RESEARCH_FUNNEL.json. A row that cannot compile gets a NAMED blocker in the conversion-debt
    # ledger -- conversion debt to zero is the standing law. Meta department, meta layer.
    exs = _costed("experiment_spine", lambda: _producer("experiment_spine",
                                                        "research/experiment_spine.py",
                                                        "--once", "--budget-s", "600"))
    # THE RECOMMENDATION LEDGER'S DRAIN (principal 2026-09-23, "our CEO n implementer"). The CEO
    # docket ran daily into a ledger that had not been written for 281.7 hours: the ledger CLI
    # imported fcntl and could not run on this box at all, and its only drain was an LLM cron on
    # the VPS. This leg takes the OPEN rows in priority order and drives each to implemented,
    # scheduled, rejected -- or an exactly NAMED blocker with an owner, on a row that stays open
    # and visible. Meta department, meta layer; fenced by scripts/check_recommendation_flow.py.
    imp = _costed("implementer", lambda: _producer("implementer",
                                                   "research/implementer.py",
                                                   "--once", "--budget-s", "600"))
    # THE META-EVOLUTION LAYER (LAWS 5m, U33): the research machinery evolved under the immutable
    # rails -- every proposal fenced by immutable_rails before it is applied, one elite per
    # (search family x data family x region x horizon), fitness the delayed yield research_roi
    # credits. Meta department resident.
    rev = _costed("research_evolution", lambda: _producer("research_evolution",
                                                           "research/research_evolution.py",
                                                           "--once", "--budget-s", "900"))
    # THE COMPUTE-ECONOMICS SCIENTIST (U34): survivors per CPU-hour, wall-hour and data-pound by
    # department, forest, search family and layer; the 70/20/10 policy learned two-sided and
    # written to data/compute_policy.json for the departments' exchange and the forest
    # allocator to read. Meta.
    cec = _costed("compute_economics", lambda: _producer("compute_economics",
                                                          "research/compute_economics.py",
                                                          "--once", "--budget-s", "300"))
    # LEAD-LEVEL BLIND REPLICATION (M13): important leads frozen and reproduced by a second
    # implementation with minimal context before they earn expensive resources. Validate.
    lrp = _costed("lead_replication", lambda: _producer("lead_replication",
                                                         "research/lead_replication.py",
                                                         "--max-leads", "10",
                                                         "--budget-s", "240"))
    # THE INDEPENDENT REPLICATION CIVILIZATION (LAWS 5m): every certificate and every
    # forward-enrolled row rebuilt in rotation from its WRITTEN specification and the raw bars
    # only -- no import of the original implementation -- and quarantined by name when fills,
    # P&L, position state or costs disagree materially. Validate.
    rpc = _costed("replication_civilization", lambda: _producer(
        "replication_civilization", "research/replication_civilization.py",
        "--once", "--budget-s", "900"))
    # THE ANYTIME-VALID SCIENCE CONTROLLER (LAWS 5k/5m, Tier-1 U19): stamps the research genome
    # and family id on every registry candidate, prices the trial stream at N_effective (the
    # count follows the FAMILY), keeps online-FDR wealth per lineage and records BLOCKED for the
    # launches an exhausted lineage cannot afford. Report only: it lowers no sealed gate.
    # Validate department, 600 s.
    scc = _costed("science_controller", lambda: _producer(
        "science_controller", "research/science_controller.py", "--once", "--budget-s", "600"))
    # THE DATA-DISCOVERY SWARM (M12): every missing information requirement and the cheapest
    # PIT-clean source that could expose it, as dataset discoveries. Intel.
    dsc2 = _costed("data_scout", lambda: _producer("data_scout", "research/data_scout.py",
                                                    "--budget-s", "120"))
    # THE ACTIVE DATA-ACQUISITION SCIENTIST (LAWS 5m; RESEARCH 11): which MISSING dataset has the
    # highest expected research value -- P(independent survivor) x diversification value /
    # (data + compute + engineering) x 1[legal] -- read off the coverage holes, the residual
    # targets, the missed-trade parents and the packs' declared-absent datasets; a small lawful
    # sample through the existing fetch path; a DatasetContract on every dataset_request.
    daq = _costed("data_acquisition_scientist", lambda: _producer(
        "data_acquisition_scientist", "research/data_acquisition_scientist.py", "--once",
        "--budget-s", "600"))
    # THE JAPAN RESEARCH DIVISION (the principal's mandate, 2026-09-17, HOURLY): the twenty-step
    # loop over the twenty-four Japan miners, the compiler, the registers, the frontier and the
    # dashboard, as one leg of the japan department resident.
    jpd = _costed("japan_department", lambda: _producer("japan_department",
                                                         "research/region_department.py",
                                                         "--region", "japan", "--once",
                                                         "--budget-s", "1800"))
    # THE AI MATHEMATICS RESEARCH CIVILIZATION (mathlab, 24/7 resident): twenty-eight parallel
    # mathematical traditions attack the world model's residual, each object charged its own
    # search burden, the executable ones donated to the compiler's EXACT_RECIPE door as `formula`
    # recipes, credit back to the tradition through generator_yield and data/math_allocation.json.
    # THE BUDGET MUST FIT THE KILL TIMEOUT (measured 2026-09-23). `_producer_impl` runs this leg
    # under `LEG_BUDGET_SEC.get("math_lab", SEARCH_BUDGET_SEC)` = 720 s, so a pass that plans
    # 3,000 s could only ever be killed before it wrote MATH_LAB.json -- an organ that runs for
    # twelve minutes an hour and leaves no artifact. A 300 s pass with the physics wing measured
    # 1,228 s (the judge, not the scientists, is the cost); math_lab now stops its own judge at
    # 80% of the budget, so 600 s finishes inside the 720 s timeout like `physics_lab` does.
    mlb = _costed("math_lab", lambda: _producer("math_lab", "research/math_lab.py", "--once",
                                                 "--budget-s", "600"))
    # THE EXPRESSION FACTORY (LAWS 5l, 5k; RESEARCH 11), the mathlab department's second leg:
    # the 101 public parent genomes and the desk's own families through a typed, unit-checked
    # DSL -- harvest -> transfer unchanged -> credit-weighted dimension-preserving mutation ->
    # invention -- a cost-ordered cheap layer, a three-null factory, the trial ledger and the
    # lockbox before any gauntlet cell; survivors become registry candidates with provenance
    # (campaign PROPOSED -> SCREENED -> QUEUED -> TESTING -> FORWARD | FAILED).
    xpf = _costed("expression_factory", lambda: _producer("expression_factory",
                                                           "research/expression_factory.py",
                                                           "--once", "--budget-s", "600"))
    # THE PHYSICS LAB (2026-09-22), the mathlab department's institution: two independent
    # civilizations (disjoint seeds) of the nineteen physics traditions plus a rotating slice of
    # the mathematical ones over LOCKBOXED panels; every object becomes a hypothesis card with a
    # falsifier, consequences, peer review (discoverer + destroyer), a multiplicity charge through
    # the effective-trial ledger, a second independent run before FORWARD, a Pareto front, credit
    # back to the method, planted nulls that must die, the fifteen engines, the theorem memory
    # under data/mathlab/, and a wiring proof naming every organ that ran.
    phl = _costed("physics_lab", lambda: _producer("physics_lab", "research/physics_lab.py",
                                                    "--once", "--budget-s", "600"))
    # FACTOR x MODEL CO-EVOLUTION, closed (2026-09-22, Tier-1 items 2, 3, 7, 10, 13, 14, 15,
    # 17, 18). Separate populations of factors and of models, bred on four ISLANDS with
    # different priors and different slices of the vocabulary; BOTH sides mutate from the
    # residual, the pooled residuals are re-interrogated as a research dataset on seven axes,
    # every failure emits the descendant its kind implies, migration moves only strictly
    # stronger concepts, self-play makes a champion beat the strongest SIMPLER explanation, the
    # next experiment is chosen by expected information gain, and the desk's own
    # synthetic-world rediscovery score is re-measured every pass. Writes COEVOLUTION.json.
    cev = _costed("coevolution", lambda: _producer("coevolution",
                                                   "research/factor_model_coevolution.py",
                                                   "--once", "--budget-s", "900"))
    # MODEL-FAMILY SEARCH as its own civilization (Tier-1 items 6 and 7): ten families -- linear,
    # sparse, tree, boosting, neural, state-space, Bayesian, sequence, graph, mixture-of-experts
    # -- each with a factor's lineage, novelty key and declared falsifier (its tax), crossed with
    # six representations of the same bars. The whole (R x M) grid is published, a representation
    # is DEAD only when every learner tried on it failed, and an absent heavy library reads
    # UNMEASURED while the pure-Python fallback carries the run. Writes MODEL_SEARCH.json.
    mds = _costed("model_search", lambda: _producer("model_search", "research/model_search.py",
                                                    "--once", "--budget-s", "600"))
    # THE GLOBAL NATIVE-MARKET RESEARCH OS (regions): every country lab at equal priority with
    # measured adjustments, the transmission engine, the compiler; one pass per hour.
    gro = _costed("global_research_os", lambda: _producer("global_research_os",
                                                           "research/global_research_os.py",
                                                           "--once", "--budget-s", "3000"))
    # THE ARCHAEOLOGY CIVILIZATION: twenty families of public trading history a pass, every
    # source paid by measured survivors (LAWS 5g). Nothing is fetched that the access
    # classifier has not cleared; the population file is append-only forever.
    arch = _costed("archaeology", lambda: _producer("archaeology",
                                                     "research/archaeology/civilization.py",
                                                     "--once", "--budget-s", "900"))
    # SARES, THE STRATEGY ARCHAEOLOGY AND REVERSE-ENGINEERING SANDBOX (RESEARCH 11, LAWS 5m):
    # ten specialist agents over the population and captures the civilization already holds --
    # graded A-F cells with a falsifier and a genealogy, illusions as cells, negative knowledge
    # from the graveyard. Reaches no host; leaderboard profitability never bypasses the gauntlet.
    srs = _costed("sares", lambda: _producer("sares", "research/archaeology/sares.py",
                                             "--once", "--budget-s", "900"))
    # ONE CERTIFICATE TRUTH (principal 2026-09-22). Audits every store that claims a certificate
    # or a clock (canon + seal, survivors ledger, sleeve registry, shadow and lane states,
    # sleeves.json, forward_reconcile.json) against the ONE lane -- external_gauntlet.py writes
    # UNIVERSAL_SURVIVORS.json, promoter.py reads it -- and publishes every divergence to
    # reports/CERTIFICATE_TRUTH.json. NEVER --apply on the clock: the migration is a one-time
    # act the coordinator runs on the box. scripts/check_certificate_truth.py fails on residue.
    ctt = _costed("certificate_truth", lambda: _producer(
        "certificate_truth", "research/certificate_truth.py", "--once", "--budget-s", "120"))
    # THE RUNTIME ATTESTATION (a GitHub reviewer, 2026-09-23): "GitHub code is not current VPS
    # reality ... comments in the code describe measured runs, but that is not the same as seeing
    # runtime state." Correct, and uncloseable by committing `desks/mt5/reports/**` (~50 MB the
    # box rewrites hourly). So this leg derives, from the component registry and the artifacts on
    # THIS host, one small COMMITTED file -- docs/research/runtime_state.json + RUNTIME_STATE.md
    # -- carrying every organ's clock, last run and exit, and its artifact's age, size, SHA-256
    # and a handful of scalars the organ itself published. Hashes and scalars only, never a
    # report body. MISSING / STALE / NEVER / UNMEASURED are states, never blanks, and the
    # document names the one host it measured and refuses to describe any other.
    rta = _costed("runtime_attestation", lambda: _producer(
        "runtime_attestation", "research/runtime_attestation.py", "--once", "--budget-s", "180"))
    # FIX THE CLASS, ON A CLOCK, OR IT IS NOT FIXED (LAWS 7, principal 2026-09-23). The twin of
    # the birth fence: that one stops a NEW thing arriving incomplete, this one proves every
    # KNOWN defect class carries a detector, a repair, a fence and fresh evidence -- and names
    # the classes still found by hand, which is the count that must reach zero.
    slf = _costed("self_repair", lambda: _producer(
        "self_repair", "research/self_repair_registry.py", "--once", "--budget-s", "120"))
    # THE TWO STANDING BATTERIES (principal 2026-09-22: "100 percent of everything built always
    # must be used never forgotten"). A long tail of fences, standing fixers and region organs is
    # too small to deserve a leg each and invisible the moment it stops running; each battery
    # rotates its roster under one budget and publishes, per organ, its last verdict and the AGE
    # of that verdict -- so a rostered organ that died is NAMED in BATTERY_*.json, never silence.
    fbt = _costed("fence_battery", lambda: _producer(
        "fence_battery", "research/batteries.py", "--battery", "fences", "--once",
        "--budget-s", "600"))
    obt = _costed("organ_battery", lambda: _producer(
        "organ_battery", "research/batteries.py", "--battery", "organs", "--once",
        "--budget-s", "600"))
    # THE LOOP LIVENESS PROVER. Every leg above reports on ITSELF, so the loop can break at one
    # arrow while fifty-odd reports stay individually truthful and nothing names WHICH arrow.
    # This leg proves the chain sources -> discoveries -> conversion -> cells -> TEN GATES ->
    # certificates -> clocks -> accrual -> promoter -> allocator from the registry and the
    # artifacts, and publishes a stage with input waiting and no output as a STALLED DEFECT
    # naming the organ and its last costed run. Validate department, meta layer. Reads only.
    llv = _costed("loop_liveness", lambda: _producer(
        "loop_liveness", "research/loop_liveness.py", "--once", "--budget-s", "240"))
    # THE CLOCK-LIVENESS ORGAN, one arrow further in and one law stricter. `loop_liveness` can
    # only say the `clocks_accruing` ARROW is alive; it cannot say WHICH clock stopped, and on
    # this box the way a clock stops is silent -- the identity leaves the certificate canon, the
    # ledger row is never pruned, and `shadow_forward` simply stops visiting a key that still
    # reads ACTIVE (measured 2026-09-23: 364 of 483 rows off a 119-key roster). This leg counts
    # each clock's lag in ITS OWN venue's bars (weekends and holidays out, from the market
    # constitution), and then REPAIRS every FROZEN one in the same pass through the control
    # plane's actuators -- A REPORT IS NOT A REMEDY (LAWS 7). Forward department, meta layer.
    clk = _costed("clock_liveness", lambda: _producer(
        "clock_liveness", "research/clock_liveness.py", "--once", "--budget-s", "300"))
    # THE FREE SHADOW-INSTITUTIONAL STACK: public proxies for the institutional capabilities
    # the desk cannot buy, each latent fused from at least two sensors or named UNMEASURED.
    shi = _costed("shadow_institutional", lambda: _producer("shadow_institutional",
                                                             "research/shadow_institutional.py",
                                                             "--once", "--budget-s", "900"))
    # THE LATENT ACTORS: who else is in this tape, fitted from causal daily footprints, with
    # the unknown components kept as unknowns rather than labelled.
    lat = _costed("latent_actors", lambda: _producer("latent_actors",
                                                      "research/latent_actors.py",
                                                      "--once", "--budget-s", "600"))
    # THE LATENCY LAB: what this desk can actually reach in time, measured end to end. It
    # ROUTES research and never sizes capital (growth governance).
    lab = _costed("latency_lab", lambda: _producer("latency_lab",
                                                    "research/latency_lab.py",
                                                    "--once", "--budget-s", "600"))
    # THE FEED/CLOCK/PROPAGATION OBSERVATORY (LAWS 5m): feed health per instrument stamped into
    # data/feed_health.json (an INPUT for entry timing, never a cap), the causally admissible
    # propagation graph, and the timing-corruption test on every LIVE/STANDBY sleeve.
    fcl = _costed("feed_clock_lab", lambda: _producer("feed_clock_lab",
                                                       "research/feed_clock_lab.py",
                                                       "--part", "observatory",
                                                       "--once", "--budget-s", "600"))
    # THE EXECUTION / MARKET-IMPACT ALPHA LAB (LAWS 5m): the desk's own fills against its own
    # tape -- Kyle-lambda with a permutation null, session cost curves, toxicity as a state,
    # execution cells recorded and execution-conditioned seeds donated to the compiler.
    imp = _costed("impact_lab", lambda: _producer("impact_lab",
                                                   "research/feed_clock_lab.py",
                                                   "--part", "impact",
                                                   "--once", "--budget-s", "600"))
    # THE NET-EDGE SPINE (principal 2026-09-23, "maximum edge possible of NET"). ONE function
    # (libs/research/net_edge.py) prices net = gross - spread/slippage at the cell's own size
    # and state - market impact at that size - financing and swap over the holding period -
    # commission - the multiplicity charge already owed, and applies it at THREE DOORS: the
    # intake's ranking (data/net_edge_ranks.json -> miner_candidate_compiler), the forward-slot
    # ranking (net_slot_value beside slot_value) and the allocator's evidence (a heat-neutral
    # net_of_cost tilt plus per-sleeve CAPACITY). It also judges the cost model BACKWARD against
    # every closed live trade. It vetoes nothing, sizes nothing and preserves the heat total
    # exactly; COST_DEAD is a ranking plus a lower-turnover donation, billed as missed growth.
    nee = _costed("net_edge", lambda: _producer("net_edge",
                                                "research/net_edge_spine.py",
                                                "--once", "--budget-s", "600"))
    # COST TRUTH (principal 2026-09-23, "double check if the costs are actually Fusion costs ...
    # just in case we dismissed edges net based on overcharged false costs"). Three readings per
    # symbol -- what the model CHARGES, what the broker QUOTES on this account over the whole
    # session, what the account has actually PAID -- from the terminal and the desk's own deals.
    # It publishes COST_TRUTH.json, the rendered page, and EXECUTION_COST_SURFACE.json, which is
    # the artifact the spine above already reads and which NOTHING on this desk wrote. A box with
    # no terminal reads UNMEASURED rather than failing. Fence: scripts/check_cost_truth.py.
    ctr = _costed("cost_truth", lambda: _producer("cost_truth",
                                                  "research/cost_truth.py",
                                                  "--once", "--budget-s", "600"))
    # THE OPEN-SOURCE RESEARCH FEDERATION (LAWS 5h): every public research system disposed,
    # ledgered, delta-watched and budgeted, and every sandbox packet drained into the one
    # canonical gauntlet. It never fetches or executes third-party code -- provisioning is
    # its own explicit act -- so this leg is cheap and runs every hour.
    xfd = _costed("external_federation", lambda: _producer("external_federation",
                                                            "research/external_federation.py",
                                                            "--once", "--budget-s", "600"))
    # FEDERATION OPERATIONS (LAWS 5h/5m): the persisted per-system registry with its append-only
    # history, upstream delta scans by hash through the existing fetcher, spawn signals from
    # already-fetched material through `admit`, the technique exchange across the forests, the
    # benchmark twins, and reports/FEDERATION.json naming the first broken invariant. Reads the
    # federation organ's state and the sandbox runner's artifacts; never runs third-party code.
    fops = _costed("federation_ops", lambda: _producer("federation_ops",
                                                        "research/federation_ops.py",
                                                        "--once", "--budget-s", "600"))
    # THE SANDBOX SUPPLY LINE (LAWS 5h/5m): installs the pinned requirement of the systems the
    # runner could only record UNMEASURED, into ONE shared venv over the desk's own interpreter,
    # proves the module imports, reads the licence at the same pin, and settles what this
    # interpreter can never host as PERMANENTLY_UNAVAILABLE with its exact error and its cover.
    sbp = _costed("sandbox_provision", lambda: _producer("sandbox_provision",
                                                         "research/sandbox_provision.py",
                                                         "--once", "--budget-s", "1500"))
    # THE SANDBOX RUNNER (LAWS 5h): the federation's execution layer. Runs the highest-ROI
    # runnable adapters in their sandboxes and the desk's own rebuilt cells over the desk's PIT
    # bars, converts every packet into registry candidates with provenance and charged trials,
    # records UNMEASURED with an install task for every absent library; TEXT_ONLY is never a
    # resting state. Third-party code runs only inside libs/research/sandbox.py.
    sbr = _costed("sandbox_runner", lambda: _producer("sandbox_runner",
                                                      "research/sandbox_runner.py",
                                                      "--once", "--budget-s", "900",
                                                      "--allow-network"))
    # THE ROSTER (LAWS 5h): one GENERATED table naming every roster seed, every adapter and
    # every rebuilt cell with its disposition, licence, capability family, whether it runs here,
    # its last run, what it produced and its marginal breadth. Never hand-written.
    sbo = _costed("sandbox_roster", lambda: _producer("sandbox_roster",
                                                      "research/sandbox_roster.py",
                                                      "--once", "--budget-s", "120"))
    # THE MACRO RESEARCH DIVISION as a region instance (the Japan template for global macro):
    # nineteen miners over G10 banks, releases, positioning, rates, auctions, interventions,
    # propagation, fixings, commodity fundamentals, risk regimes; hourly on the macro resident.
    mcd = _costed("macro_department", lambda: _producer("macro_department",
                                                         "research/region_department.py",
                                                         "--region", "macro", "--once",
                                                         "--budget-s", "1800"))
    # THE PARALLEL SOURCE CIVILIZATIONS (principal 2026-09-17): the twelve roles over material
    # frontier_intel and the collectors ALREADY fetched, the six L1vsun and three bl888m families,
    # the research primitives and the cross-source interaction forge. NOT a fetcher and not a
    # second frontier miner -- it reads the claims store and the frontier queue, mints discoveries
    # for the compiler, and writes the thesis clocks and the gate-attribution ledger. Intel.
    svc = _costed("source_civilizations", lambda: _producer("source_civilizations",
                                                            "research/source_civilizations.py",
                                                            "--budget-s", "300"))
    # THE EVIDENCE WATCHTOWER: every claim checked against a direct observable and an independent
    # second source, every already-seen object re-scanned, and a transition recorded ONLY when the
    # evidence changed. Its own false-transition rate is measured on a fixture every pass. Intel.
    ewt = _costed("evidence_watchtower", lambda: _producer("evidence_watchtower",
                                                           "research/evidence_watchtower.py",
                                                           "--budget-s", "120"))
    # PREDICTION-MARKET INTELLIGENCE: calibration fitted per category, resolution truth, the
    # disagreement vector and the dependency deviations, as a SENSOR for gold, the dollar, rates,
    # oil and the indices. No account, no order, no scrape -- `--no-fetch` by default. Intel.
    pmk = _costed("prediction_markets", lambda: _producer("prediction_markets",
                                                          "research/prediction_markets.py",
                                                          "--no-fetch", "--budget-s", "180"))
    # THE PROBABILITY AND FAIR-VALUE DISLOCATION LAB (RESEARCH 11, LAWS 5m): six independent
    # probability engines, each with a reliability curve per regime measured on history under
    # the anti-lookahead rule, against what the instrument itself prices. A cell fires only
    # when the CALIBRATED ensemble disagrees net of costs, model uncertainty and a regime
    # buffer, and is donated as an exact recipe. It CONSUMES the macro, world, news, shadow,
    # transmission and prediction-market reports the legs above write, re-implements none of
    # them, and sizes nothing. Macro department, prediction layer.
    dsl = _costed("dislocation_lab", lambda: _producer("dislocation_lab",
                                                       "research/dislocation_lab.py",
                                                       "--once", "--budget-s", "900"))
    # INDEPENDENCE AT INTAKE (2026-09-23). 227.5 cells an hour reach the judge and their
    # orthogonality-weighted equivalent is 23.4: the desk emits ten times more volume than
    # independent ground. This leg publishes the dedup ladder, the family x instrument x horizon
    # grid's occupancy with its empty cells as ranked targets, and the declared mechanism-mutation
    # share that `survivor_distiller` spends -- tuned by the orthogonality gain each operator
    # class is MEASURED to open. It caps nothing and slows no producer: the levers are order,
    # operator mix and where generation is aimed. Meta department, meta layer.
    ind = _costed("independence_intake", lambda: _producer("independence_intake",
                                                           "research/independence_intake.py",
                                                           "--once", "--budget-s", "240"))
    # ATTRIBUTION AT BIRTH (2026-09-23). Every cell and discovery carries WHO produced it and,
    # where the producer belongs to one, from WHICH region -- stamped by the two registry doors
    # through libs/research/attribution.py. This leg measures the coverage, recovers from lineage
    # what rows born before the stamp still hold, and DECLARES the rest UNATTRIBUTABLE with the
    # reason so the denominator is honest. Measured the day it landed: producer coverage 0 -> 1.0,
    # region coverage 0 -> 0.977, certificates 25 -> 47 of 58 traced, and Europe's unique cells
    # 0 -> 129 on a board that had read `1,973 sources, 0 cells`. Meta department, meta layer.
    att = _costed("attribution_census", lambda: _producer("attribution_census",
                                                          "research/attribution_census.py",
                                                          "--once", "--budget-s", "240"))
    # THE FOREST FEDERATION (principal 2026-09-17). Korea 24/7 || Japan 24/7 || China 24/7 ||
    # Russia 24/7 || ... || Global 24/7: every region its own research civilization, running the
    # eleven agent roles in parallel on its own resident, all feeding ONE registry through ONE
    # dedup chain (`libs/research/dedup_chain.py`) so ten agents finding one strategy on ten
    # repost sites produce ONE mechanism and nine provenance edges. The leg names are written
    # out rather than looped because the layer registry, the Tier-1 checker and the wiring
    # census all read the costed-leg literals out of THIS SOURCE: a leg composed at runtime is a
    # leg
    # those three cannot see, which is the same class of defect as not scheduling it at all.
    forests_out: dict[str, dict] = {}
    forests_out["forest_korea"] = _costed("forest_korea", lambda: _producer(
        "forest_korea", "research/forest_runner.py", "--forest", "korea", "--once",
        "--budget-s", "3000"))
    forests_out["forest_china"] = _costed("forest_china", lambda: _producer(
        "forest_china", "research/forest_runner.py", "--forest", "china", "--once",
        "--budget-s", "3000"))
    forests_out["forest_russia_cis"] = _costed("forest_russia_cis", lambda: _producer(
        "forest_russia_cis", "research/forest_runner.py", "--forest", "russia_cis", "--once",
        "--budget-s", "3000"))
    forests_out["forest_south_asia"] = _costed("forest_south_asia", lambda: _producer(
        "forest_south_asia", "research/forest_runner.py", "--forest", "south_asia", "--once",
        "--budget-s", "3000"))
    forests_out["forest_asean"] = _costed("forest_asean", lambda: _producer(
        "forest_asean", "research/forest_runner.py", "--forest", "asean", "--once",
        "--budget-s", "3000"))
    forests_out["forest_oceania"] = _costed("forest_oceania", lambda: _producer(
        "forest_oceania", "research/forest_runner.py", "--forest", "oceania", "--once",
        "--budget-s", "3000"))
    forests_out["forest_europe"] = _costed("forest_europe", lambda: _producer(
        "forest_europe", "research/forest_runner.py", "--forest", "europe", "--once",
        "--budget-s", "3000"))
    forests_out["forest_north_america"] = _costed("forest_north_america", lambda: _producer(
        "forest_north_america", "research/forest_runner.py", "--forest", "north_america",
        "--once", "--budget-s", "3000"))
    forests_out["forest_latam"] = _costed("forest_latam", lambda: _producer(
        "forest_latam", "research/forest_runner.py", "--forest", "latam", "--once",
        "--budget-s", "3000"))
    forests_out["forest_mena"] = _costed("forest_mena", lambda: _producer(
        "forest_mena", "research/forest_runner.py", "--forest", "mena", "--once",
        "--budget-s", "3000"))
    forests_out["forest_africa"] = _costed("forest_africa", lambda: _producer(
        "forest_africa", "research/forest_runner.py", "--forest", "africa", "--once",
        "--budget-s", "3000"))
    # The four GLOBAL-LAYER forests ride the `regions` resident: their ground is a layer of the
    # world rather than a place, and giving each a region resident would have them competing
    # with the twelve for the same sources.
    forests_out["forest_global_web"] = _costed("forest_global_web", lambda: _producer(
        "forest_global_web", "research/forest_runner.py", "--forest", "global_web", "--once",
        "--budget-s", "3000"))
    forests_out["forest_global_academic_code"] = _costed(
        "forest_global_academic_code", lambda: _producer(
            "forest_global_academic_code", "research/forest_runner.py", "--forest",
            "global_academic_code", "--once", "--budget-s", "3000"))
    forests_out["forest_global_physical_data"] = _costed(
        "forest_global_physical_data", lambda: _producer(
            "forest_global_physical_data", "research/forest_runner.py", "--forest",
            "global_physical_data", "--once", "--budget-s", "3000"))
    forests_out["forest_global_market_data"] = _costed(
        "forest_global_market_data", lambda: _producer(
            "forest_global_market_data", "research/forest_runner.py", "--forest",
            "global_market_data", "--once", "--budget-s", "3000"))
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
    # JUDGING THROUGHPUT (principal 2026-09-23: "tons of headroom ... maximum throughput"), and it
    # MUST run before the sweep it sizes. `external_gauntlet.py` is SEALED; its `_worker_count()`
    # and `_measured_budget_mb()` already read GAUNTLET_WORKERS / GAUNTLET_MEMORY_BUDGET_MB /
    # GAUNTLET_HEADROOM_CAP_MB from the environment, so this organ measures the box's free cores,
    # free physical memory and free COMMIT, writes the largest safe worker count to
    # data/judging_throughput.env.json, and `apply_env()` loads it into THIS process -- which is
    # the environment `_producer` hands the gauntlet subprocess. The plan is floored at what the
    # sealed file would pick unaided, so this can never throttle the judge, and the live terminal
    # always wins (it stands down to that floor, never below it).
    jth = _costed("judging_throughput", lambda: _producer(
        "judging_throughput", "research/judging_throughput.py", "--once", "--budget-s", "300"))
    try:
        from research.judging_throughput import apply_env as _apply_judging_env
        _apply_judging_env()
    except Exception as _exc:
        print(f"judging_throughput env not applied: {type(_exc).__name__}: {_exc}", flush=True)
    gt = _costed("external_gauntlet", lambda: _producer(
        "external_gauntlet", "scripts/external_gauntlet.py"))
    # EVERY CERTIFICATE GETS ITS CLOCK THE MOMENT IT EXISTS, with no quota and no waiting queue
    # (principal 2026-09-23: forward evidence is never rationed; forward clocks gather evidence
    # and deploy no capital, so the only thing a slot cap bought was a slower desk). AFTER the
    # judge, deliberately: a certificate minted by THIS hour's sweep is enrolled in THIS hour's
    # pass rather than the next one, which is what "immediately" has to mean on an hourly clock.
    fen = _costed("forward_enrolment", lambda: _producer(
        "forward_enrolment", "research/forward_enrolment.py", "--once", "--budget-s", "300"))
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
    # DID THE MONEY BRAIN ACTUALLY PRODUCE, PROVE AND PUBLISH -- and on what? (2026-09-23.) Runs
    # immediately after the solve, so the ages it publishes are the ages the pass ABOVE
    # conditioned on. It names every allocator output with its real path and its consumer, every
    # input with its age and whether the pass DECLARED it used, the heat against the floor, the
    # book's join to the live rows, and the last named stand-down. Report only; the fence is
    # `scripts/check_allocator_liveness.py`. Written because a probe read two paths the allocator
    # does not write to, found them absent, and concluded the allocator was dead while both real
    # artifacts were minutes old.
    alv = _costed("allocator_liveness", lambda: _producer(
        "allocator_liveness", "research/allocator_liveness.py", "--once", "--budget-s", "120"))
    # 24/7 AND NOT SLOW (principal 2026-09-23). The hourly solve above is the BACKSTOP; this
    # watches the artifacts that carry a state change -- a macro surprise, a regime transition, a
    # certificate arriving or dying, a fill, a cost or capacity revision -- and fires the same
    # solver the moment one moves, then publishes the event-to-allocation latency per trigger
    # kind. The hourly leg is the floor on how often it looks; the 24/7 resident
    # (`--resident`, desks/mt5/ops/box_tasks.manifest) is how it reacts in seconds.
    atg = _costed("allocator_trigger", lambda: _producer(
        "allocator_trigger", "research/allocator_trigger.py", "--once", "--budget-s", "300"))
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
    # THE MARKET DIGITAL TWIN (LAWS 5m): a posterior over latent simulator worlds calibrated
    # per hunt-universe instrument by ABC-SMC on the desk's own bars and ticks, posterior
    # predictive checks with a published calibration score, pre-registered effect sizes for
    # the canonical mechanisms, and every LIVE/STANDBY sleeve and the newest queued
    # candidates run across the SAME posterior worlds at zero/actual/doubled spread:
    # posterior-world robustness and counterfactual execution cost. It sizes nothing.
    # Execution department, 600 s; a rotation cursor covers the universe over passes.
    dtw = _costed("digital_twin", lambda: _producer("digital_twin", "research/digital_twin.py",
                                                     "--once", "--budget-s", "600"))
    # THE COLLATERAL / SETTLEMENT / BALANCE-SHEET LAYER and the Allocator-V2 evidence (LAWS 5m):
    # the live book's swaps paid, margin, funding by currency and rollover calendar; the three
    # stress scenarios; the named evidence vector per LIVE/STANDBY sleeve and for the book.
    # Writes data/allocator_evidence.json, which pf_allocator reads into its posterior on its
    # next pass, and reports/FINANCING_LAB.json. Execution department, 600 s.
    fin = _costed("financing_lab", lambda: _producer("financing_lab",
                                                      "research/financing_lab.py",
                                                      "--once", "--budget-s", "600"))
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
    ssm_leg = _costed("session_structure", session_structure)
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
    # THE PROPOSER SEAT (2026-09-23). An OPTIONAL external-model prior over which expression
    # skeletons and which mechanism names are worth a trial. It proposes candidates and never a
    # verdict: every proposal enters the population with provenance, is charged effective trials,
    # and is judged by the identical deterministic path. On a box with no panel it writes
    # UNMEASURED and every factory runs exactly as it does today.
    prs = _costed("proposer_seat", lambda: _producer(
        "proposer_seat", "libs/research/proposer_seat.py", "--once", "--budget-s", "300"))
    # KIMI'S ONLY CLOCK WAS A VPS TIMER (measured 2026-09-23). `quant-kimi-hunter.timer` fires
    # hourly on the VPS; the box that holds the credentials ran it never, so
    # `data/intelligence/kimi` was 240 hours stale on the trading box while deepseek -- whose
    # organ has the same shape and the same seat -- donated every hour. A seat that is dark for
    # want of a clock looks exactly like a seat that is dark for want of a key, and the two have
    # nothing in common as repairs. The hunter's routine invocation walks the free-tier chain
    # only, so the cadence spends nothing; a run with no credential records its own BLOCKER and
    # exits, which is a measurement rather than a failing leg.
    kh = _costed("kimi_hunt", lambda: _producer("kimi_hunt", "scripts/kimi_hunter.py"))
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
    # THE CONTROL PLANE'S OBSERVE PASS (principal 2026-09-17, LAWS.md 7). Desired state minus
    # observed state, for every component the desk declares: schedules, locks, progress
    # watermarks, freshness leases and the mandatory producer->consumer edges. It REPAIRS
    # nothing here -- the fifteen-minute MT5-ClockFixer task runs the same organ with --apply --
    # so a red invariant costs a report and never an hour of research.
    cp = _costed("control_plane", lambda: _producer(
        "control_plane", "research/control_plane.py", "--once", "--budget-s", "600"))
    # THE PLUMBING MAY NEVER STOP SILENTLY (principal 2026-09-23). The control plane above judges
    # the desk's COMPONENTS; this judges the PIPES they run through, and it proves each one by
    # observation rather than by a label: the adoption task exists, is enabled and runs inside the
    # hour; HEAD descends from the branch tip; the git-writer lock is TAKEN and released right
    # now; no orphaned pool worker is holding commit; every declared clock is present; every
    # producer/consumer pair agrees about its path; every registered fence has run. It also has a
    # fifteen-minute clock of its own (MT5-PlumbingWatchdog) -- this leg is the hourly witness so
    # the cycle's own record shows the plumbing was checked, and the fence
    # `scripts/check_plumbing_watchdog.py` wedges the law gate while a defect outlives its window.
    pwd_ = _costed("plumbing_watchdog", lambda: _producer(
        "plumbing_watchdog", "research/plumbing_watchdog.py", "--once", "--budget-s", "180"))
    # THE 24/7 MAXIMISER (principal 2026-09-23). Four standing bottlenecks measured every hour --
    # conversion debt, judging throughput, forward enrolment latency and plumbing defects -- one
    # of them named BINDING, and compute moved toward it through the budget machinery that
    # already exists (research_budget / the auction's factors / compute_policy's split). It
    # consumes the peer organs' artifacts and writes none of theirs.
    bka = _costed("bottleneck_attack", lambda: _producer(
        "bottleneck_attack", "research/bottleneck_attack.py", "--once", "--budget-s", "300"))
    # THE DASHBOARD'S ONE JOINED DOCUMENT (principal 2026-09-23). Canon, defects, live money,
    # producers, funnel, bottlenecks and the macro/news lane joined on the canonical identity
    # (symbol|family|selector) into `DESK_DASHBOARD_STATE.json` and merged into the payload the
    # page already fetches. Read-only: it writes no registry row and sizes nothing, so it cannot
    # change what the desk trades. Every value carries its source artifact and that artifact's
    # age; an absent measurement is UNMEASURED with its reason, never a zero.
    dds = _costed("desk_dashboard_state", lambda: _producer(
        "desk_dashboard_state", "research/desk_dashboard_state.py",
        "--once", "--budget-s", "120"))
    lc = _costed("layer_census", lambda: _producer("layer_census", "libs/research/layers.py"))
    oc = _costed("opportunity_cost", lambda: _producer(
        "opportunity_cost", "research/opportunity_cost.py"))
    # THE HOUR'S PRICES, REBUILT AND PUBLISHED (Tier-1 B27). The plan is already built lazily by
    # the first leg that asks for a budget; this leg exists so the artifact is written and
    # printed every pass even in an hour where nothing asked, and so the planned-versus-applied
    # record has a clock of its own rather than living as a side effect of another leg.
    cyp = _costed("cycle_pricing", lambda: _producer(
        "cycle_pricing", "research/cycle_pricing.py", "--once", "--budget-s", "120"))
    # THE INVARIANCE VERDICT PER JUDGED CELL (Tier-1 B16). The organ stops itself at its own
    # --budget-s and writes CAUSAL_INVARIANCE.json; the cycle's cap sits above it so it is never
    # cut at the same prefix every hour. Consumers: the candidate compiler's intake (priority),
    # forward_reconcile's published field, and missed_growth's `causal_invariance` rail line.
    civ = _costed("causal_invariance", lambda: _producer(
        "causal_invariance", "research/causal_invariance.py", "--once", "--budget-s", "600"))
    # THE CLOSED-LOOP ORGANS (Tier-1 B14-B25, 2026-09-23). Each stops itself at its own
    # --budget-s and writes its artifact, and each has a named consumer already wired:
    #   source_evig              -> asia_collector's fetch order (EVIG-priced acquisition)
    #   actor_pressure           -> the state vector's conditioning block (latent actors)
    #   destroyer_pool           -> falsifier_run's evolved attack (predators that reproduce)
    #   quantbench               -> the suite: the defect corpus, beaten whole or not at all
    #   evidence_chain           -> quantbench QB007: the hash chain over certificates and seeds
    #   clock_ledger             -> shadow_forward's writer: forward starts made immutable
    #   shortfall_model          -> execution_policy's cost term, refitted from realised fills
    #   counterfactual_timeframes-> the compiler's chart order, measured per trade at M1..H1
    #   meta_rnd                 -> falsifier_run's ordering policy (the process as a subject)
    sev = _costed("source_evig", lambda: _producer(
        "source_evig", "research/source_evig.py", "--once", "--budget-s", "120"))
    # THE DRAIN GUARANTEE (principal 2026-09-23): pricing the queue orders it and does not
    # drain it. This hands the top of the ranking to the collector every pass until the
    # backlog is empty, publishes the chain each source stands in, and ratchets two counts
    # that may only fall. It must run AFTER source_evig, whose ranking it consumes.
    sdr = _costed("source_drain", lambda: _producer(
        "source_drain", "research/source_drain.py", "--once", "--budget-s", "300"))
    # EVERY DATA PACK PRODUCES CELLS (principal 2026-09-23). `source_drain` prices and repairs the
    # chain and stops at a DISCOVERY; this turns each represented pack's stamped series into cells
    # through the one registry door and publishes CELLS EMITTED / CELLS JUDGED per pack. It must
    # run AFTER source_drain, whose chain state it reads and never edits.
    pkc = _costed("pack_cells", lambda: _producer(
        "pack_cells", "research/pack_cells.py", "--once", "--budget-s", "240"))
    # THE FRONT DOOR IS NOT THE GROUND (2026-09-23). 15 of the 121 document-holding grounds named
    # no instrument for ONE reason `pack_cells.resolve_ground` had already written: the documents
    # held are the landing page. This walks inside those grounds' own doors -- ranked links and
    # data endpoints from their held pages, captured through `moat_collectors` under the SAME
    # source_id -- so rung 3 of that ladder resolves them on the next pack_cells pass; a ground
    # whose deeper pages still name nothing gets a measured verdict with the shape that defeated
    # the reader, and the links it did not reach go to `world_frontier`. Information department,
    # information layer. It must run AFTER pack_cells, whose ladder decides its targets.
    gdp = _costed("ground_depth", lambda: _producer(
        "ground_depth", "research/ground_depth.py", "--once", "--budget-s", "600"))
    # THE SAME MECHANISM ON EVERY CHART (principal 2026-09-23). `counterfactual_timeframes`
    # measured M5 paying +0.869R and M15 +0.360R over the H1 replay on 222 real decisions while
    # the registry carried ZERO M5 and M1 cells. This re-mints every certified mechanism and every
    # strong docket family on M1/M5/M15/H1/H4 and charges the multiplicity through trial_ledger.
    tff = _costed("timeframe_fanout", lambda: _producer(
        "timeframe_fanout", "research/timeframe_fanout.py", "--once", "--budget-s", "240"))
    # THE LIVE ACCOUNT'S FILLS (principal 2026-09-23). `matched_fills` read 0 everywhere because
    # nothing had ever written the intent/deal join down; thirty real fills were on disk. This
    # records quote, ask, fill, latency, volume, spread and slippage (points and R) into the
    # corpus the execution twin and the shortfall model already read. Recording only.
    flr = _costed("fill_recorder", lambda: _producer(
        "fill_recorder", "research/fill_recorder.py", "--once", "--budget-s", "120"))
    apr = _costed("actor_pressure", lambda: _producer(
        "actor_pressure", "research/actor_pressure.py", "--once", "--budget-s", "300"))
    dpo = _costed("destroyer_pool", lambda: _producer(
        "destroyer_pool", "research/destroyer_pool.py", "--once", "--budget-s", "300"))
    qbn = _costed("quantbench", lambda: _producer(
        "quantbench", "research/quantbench.py", "--once", "--budget-s", "120"))
    evc = _costed("evidence_chain", lambda: _producer(
        "evidence_chain", "research/evidence_chain.py", "--once", "--budget-s", "120"))
    ckl = _costed("clock_ledger", lambda: _producer(
        "clock_ledger", "research/clock_ledger.py", "--once", "--budget-s", "60"))
    shm = _costed("shortfall_model", lambda: _producer(
        "shortfall_model", "research/shortfall_model.py", "--once", "--budget-s", "120"))
    ctf = _costed("counterfactual_timeframes", lambda: _producer(
        "counterfactual_timeframes", "research/counterfactual_timeframes.py",
        "--once", "--budget-s", "240"))
    mrd = _costed("meta_rnd", lambda: _producer(
        "meta_rnd", "research/meta_rnd.py", "--once", "--budget-s", "180"))
    ac = _costed("acceptance", lambda: _producer(
        "acceptance", "scripts/check_acceptance_properties.py"))
    # PRE-REGISTRATION COVERAGE (2026-09-23). The donation path pre-registered NOTHING for its
    # whole life -- 2,908 of 537,933 rows (0.54%) carried a hash -- because `register` raised on
    # a horizon it could not derive and a bare except swallowed it. The fix is upstream in
    # `proposer_common._preregister`; this is the leg that makes the coverage VISIBLE every hour,
    # feeds the `prereg_coverage` ratchet, and fails loudly on a row donated after the cutover
    # with no card. ~12 s over 8.9k contract files, so it belongs on the core clock.
    prg = _costed("preregistration", lambda: _producer(
        "preregistration", "scripts/check_preregistration.py"))
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
    # NO PRODUCER IS DARK (LAWS 7). Every seat, miner and organ the component registry knows,
    # with its clock, its last production and its verdict -- and the RELIGHT of every dark row
    # in the same pass, judged by the producer's own output moving, never by a zero exit code.
    prdc = _costed("producer_census", lambda: _producer(
        "producer_census", "scripts/check_seat_health.py",
        "--census", "--relight", "--budget-s", "240", "--max-repairs", "6"))
    # WHICH ORGANS EARN THEIR COMPUTE (external reviewer, 2026-09-23). `producer_census` above
    # proves every producer has a CLOCK; this one measures whether it produces CELLS -- the
    # eleven-stage funnel (sources -> documents -> claims -> mechanisms -> raw cells -> unique
    # cells -> submitted -> survivors -> certificates -> forward -> live), the four marginal
    # ratios, the region roll-up that answers "is the world crawler alpha or noise", and the list
    # of producers that burned compute for no unique cell, ranked by compute.
    prodc = _costed("productivity_census", lambda: _producer(
        "productivity_census", "research/productivity_census.py", "--once", "--budget-s", "300"))
    # THE BARS THE VERDICTS WERE MEASURED ON (Tier-1 item V16). The release seal pins the code a
    # verdict came from; this pins its inputs, so a re-run can tell a code change from a data one.
    iid = _costed("input_identity", lambda: _producer(
        "input_identity", "libs/data/input_identity.py"))
    scap = _costed("session_capital", lambda: _producer(
        "session_capital", "research/session_capital.py"))
    # THE FINAL RESEARCH DASHBOARD (Tier-5 mandate 162), here for the same reason `publish_state`
    # is: it JOINS the artifacts this pass wrote, so the dashboard is the hour that just ran and
    # not the one before it. It reports and never gates.
    rdh = _costed("research_dashboard", lambda: _producer("research_dashboard",
                                                          "research/research_dashboard.py",
                                                          "--once", "--budget-s", "300"))
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
                    "release_authority": rla, "regime_hierarchy": rgh, "residual_map": rsm,
                    "failure_prior": fpr, "scientist_standings": sst, "frontier_ceo": fce,
                    "research_tree": rtr, "representation_discovery": rpd,
                    "evig_acquisition": eva,
                    "axis_registry": axr, "breadth_ladder": bld, "forced_flow_calendar": ffc,
                    "novelty_gate": ngt, "hazard_engine": hze, "posterior_alpha": pal,
                    "semantic_memory": smm, "model_role_benchmark": mrb,
                    "live_system_state": lss, "tier1_scorecard": t1s, "wiring_ceo": wce,
                    "queue_census": qcn,
                    "research_departments": rdp, "qd_frontier": qdf, "blind_reviewer": bvr,
                    "evaluator_lab": evl, "synthetic_regimes": syr, "value_of_data": vod,
                    "research_api_status": rap,
                    "artifact_chain": acv, "residual_queue": rsq, "unseen_frontier": usf,
                    "attribution_reconcile": atr,
                    "macro_state_engine": mse,
                    "research_artifacts": rart,
                    "engine_registry": engr,
                    "counterfactual_attribution": cfat,
                    "trend_core": tcor,
                    "event_surprise": esur,
                    "counterexample_agent": cexa,
                    "search_paradigm_census": spc,
                    "source_registry": srg, "event_response_atlas": era, "world_lab": wlb,
                    "news_event_stream": nes, "event_sleeves": evs,
                    "causal_lab": clb, "event_graph_lab": egl,
                    "world_model": wmd, "residual_hunt": rhu, "residual_gate": rsg,
                    "representation_forge": rfg,
                    "registry_sync": rsy, "axis_proposer": axp,
                    "program_alpha_lane": pal, "trajectory_evolution": tev,
                    "research_os_archive": roa, "regime_router": rgr, "moat_series": mos,
                    "scout_roster": scr, "descendants": dsc, "forward_slot_ranker": fsr,
                    "analyst_pipeline": anp, "knowledge_graph": kng, "card_explosion": mce,
                    "alpha_lineage": mal, "graveyard_resurrection": mgr, "shadow_discovery": msd,
                    "forward_exploitation": mfe, "alpha_recombination": mar,
                    "unused_information": mui, "discovery_compiler": dcp,
                    "conversion_maximiser": cvm, "research_debt": rdb,
                    "ingestion_ledger": igl, "ingestion_exploitation": ige,
                    "macro_intelligence": mci, "market_constitution": mcc,
                    "mining_objective": mob, "research_gap_map": rgm,
                    "evidence_router": evr, "research_roi": rroi,
                    "coverage_tensor": cov, "coverage_drain": cdr, "judge_coverage": jcv,
                    "orthogonality_yield": oyz, "effective_trials": eft,
                    "gauntlet_backpressure": gbp, "miner_specialisation": msp,
                    "portfolio_bounty": pbt, "research_auction": rau,
                    "bottleneck_law": btl, "drawdown_alpha_miner": dam,
                    "trade_autopsy": tap, "research_latency": rlt,
                    "alpha_replenishment": arp, "research_dashboard": rdh,
                    "moat_collectors": mcl, "source_frontier": sfr, "scout_swarm": ssw,
                    "actor_atlas": aat, "understanding_seat": usd,
                    "netting_report": ntr, "execution_alpha": exa,
                    "paradigm_router": prr, "meta_controller": mtc, "lead_replication": lrp,
                    "experiment_spine": exs, "implementer": imp,
                    "research_evolution": rev, "compute_economics": cec,
                    "missed_trade_archaeologist": mta,
                    "replication_civilization": rpc,
                    "science_controller": scc,
                    "data_scout": dsc2, "japan_department": jpd, "global_research_os": gro,
                    "feature_compiler": fcp, "data_acquisition_scientist": daq,
                    "math_lab": mlb, "expression_factory": xpf, "physics_lab": phl,
                    "coevolution": cev, "model_search": mds,
                    "external_federation": xfd, "archaeology": arch, "sares": srs,
                    "certificate_truth": ctt, "runtime_attestation": rta,
                    "self_repair": slf,
                    "loop_liveness": llv, "clock_liveness": clk,
                    "fence_battery": fbt, "organ_battery": obt,
                    "federation_ops": fops, "sandbox_runner": sbr,
                    "sandbox_provision": sbp, "sandbox_roster": sbo,
                    "source_civilizations": svc, "evidence_watchtower": ewt,
                    "prediction_markets": pmk, "dislocation_lab": dsl,
                    "independence_intake": ind, "attribution_census": att,
                    "shadow_institutional": shi, "latent_actors": lat, "latency_lab": lab,
                    "feed_clock_lab": fcl, "impact_lab": imp, "net_edge": nee,
                    "cost_truth": ctr,
                    "macro_department": mcd, **forests_out,
                    "probation": prb, "standing_questions": sqs, "exposure_decomposition": exd,
                    "auto_legs": auto,
                    "sweep": sw, "compile": cc,
                    "execution_twin": et, "financing_lab": fin, "digital_twin": dtw,
                    "causal_graph": cg, "alpha_rl": arl,
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
                    "session_structure": ssm_leg,
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
                    "proposer_seat": prs, "kimi_hunt": kh,
                    "release_identity": ri, "burn_in": bi, "layer_census": lc,
                    "control_plane": cp, "plumbing_watchdog": pwd_,
                    "bottleneck_attack": bka, "desk_dashboard_state": dds,
                    "opportunity_cost": oc, "acceptance": ac, "opportunity_forecast": ofc,
                    "preregistration": prg,
                    "cycle_pricing": cyp, "causal_invariance": civ,
                    "source_evig": sev, "source_drain": sdr, "pack_cells": pkc,
                    "ground_depth": gdp,
                    "timeframe_fanout": tff, "fill_recorder": flr,
                    "actor_pressure": apr, "destroyer_pool": dpo,
                    "quantbench": qbn, "evidence_chain": evc, "clock_ledger": ckl,
                    "shortfall_model": shm, "counterfactual_timeframes": ctf, "meta_rnd": mrd,
                    "edge_reliability": erl, "arena": ar, "session_capital": scap,
                    "prosecutor": pc, "scaling_laws": slw,
                    "dead_architecture": dac, "producer_census": prdc,
                    "productivity_census": prodc, "input_identity": iid,
                    "publish_state": pub,
                    "enrol_clocks": ecl, "requeue_unrunnable": rq, "reclaim_disk": dd,
                    "miner_conversion": mc, "moat_miner": mo, "archive_tape": ta,
                    "moat_candidate_compiler": mcp, "algorithm_db": adb,
                    "judging_throughput": jth, "forward_enrolment": fen,
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
                    "pf_allocator": pa, "allocator_liveness": alv, "allocator_trigger": atg,
                    "promoter": pr,
                    "frontier_implementer": fi,
                    "smoke_release": smoke},
                   indent=1), encoding="utf-8")
    # THE PASS'S OWN ATTENDANCE RECORD, re-published now that the pass is complete: what actually
    # ran, what was rotated out (and therefore leads the next pass), and -- by name -- every leg
    # that has NEVER run. `scripts/check_leg_rotation.py` fences both lists.
    _rotation_publish()
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
