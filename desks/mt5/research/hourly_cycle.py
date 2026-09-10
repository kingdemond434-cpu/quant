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
        except Exception as exc:                                        # noqa: BLE001
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
    except Exception as exc:                                            # noqa: BLE001
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


#: The admission scan's own cadence is the supervisor's hourly heavy pass; twice that is "the
#: supervisor has missed a pass", which is the condition this roster steps in on.
ADMISSION_SCAN_MAX_AGE_S = 2 * 3600.0


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
    try:
        from libs.ops.compute_ledger import close_run, open_run
    except Exception:                                                   # noqa: BLE001
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
    except BaseException as exc:                                        # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        if close_run and run is not None:
            close_run(run, outcome=detail[:200])
        print(f"  LEG FAILED {name}: {detail}", flush=True)
        _emit_leg(name, detail[:200])
        return {"error": detail[:300], "status": "LEG_FAILED",
                "at": datetime.now(UTC).isoformat()}
    if close_run and run is not None:
        close_run(run, outcome="ok")
    _emit_leg(name, "ok")
    return out


def _emit_leg(name: str, outcome: str) -> None:
    """THE EVENT LOG (Tier-1 item I2, 2026-09-09): every leg's end is an event, and the legs
    that mark a domain transition (DATA_UPDATED, GAUNTLET_SWEPT, ALLOCATION_DECIDED, ...)
    emit that transition too, so a consumer can ask what happened since it last looked instead
    of inferring it from the clock. Never fails the leg; an absent `libs` means no event."""
    try:
        from libs.ops.events import leg_events
        leg_events(name, outcome)
    except Exception as exc:                                            # noqa: BLE001
        print(f"  event for {name} not recorded: {type(exc).__name__}: {exc}", flush=True)


#: Wall clock a search leg may spend inside the cycle. The two searches are the desk's own
#: hypothesis SOURCES, so starving them starves the docket -- but a search that overran the hour
#: would push the deepening worker, the miners and the marker out of the pass entirely. Twelve
#: minutes each leaves the 40-minute deepening budget and the remaining legs their time inside the
#: hour, and a search that needs longer is one that should be given its own task on the box.
SEARCH_BUDGET_SEC = 720


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
    wa = _costed("wiring_audit", wiring_audit)
    ab = _costed("brain_ab", brain_ab)
    cm = _costed("alpha_breadth", coverage_map)
    rc = _costed("regime_coverage", regime_coverage)
    pt = _costed("alpha_periodic_table", periodic_table)
    mx = _costed("microstructure_census", microstructure_census)
    sp = _costed("spread_provenance", spread_provenance)
    tf = _costed("tape_features", tape_features)
    fll = _costed("futures_lead_lag", futures_lead_lag)
    tj = _costed("time_joins", time_joins)
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
    rc = _costed("recertify_canon", lambda: _producer(
        "recertify_canon", "scripts/recertify_canon.py"))
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
                    "deepening": dp, "heal_clocks": hc, "mine": m,
                    "search": se, "sweep": sw, "compile": cc,
                    "execution_twin": et, "causal_graph": cg, "model_skill": ms,
                    "frontier": fr, "refresh_bars": rb, "deep_forest": df,
                    "maintain_miners": mm, "publish_survivors": ps,
                    "forecast_contract": fcx, "model_league": mz, "adversaries": ad,
                    "publish_dashboard": pd_, "opportunity_gap": og, "experiment_cache": xc, "ml_layer": mll, "market_intel": mi, "experiment_design": xd, "research_org": ro, "edge_confidence": ec, "rebalance_trigger": rt, "queue_compact": qc, "issue_board": ib,
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
                    "alpha_periodic_table": pt, "queue_cycle": qcy,
                    "microstructure_census": mx, "entry_timing": ety,
                    "spread_provenance": sp, "tape_features": tf,
                    "futures_lead_lag": fll, "time_joins": tj,
                    "recertify_canon": rc, "pf_allocator": pa, "promoter": pr,
                    "frontier_implementer": fi,
                    "smoke_release": smoke},
                   indent=1), encoding="utf-8")
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
