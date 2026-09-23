"""The hourly discovery pass: every miner, proposer and data organ, every hour, on a budget.

THE PRINCIPAL'S ORDER (2026-09-05): "all miners etc should be hourly minimum or 24/7 -- for
maximum datasets, moats and edge discoveries, for max geometric growth potential." Until now
the world miners and the twelve proposer sweeps ran once a day inside `daily_cycle`, so a
mechanism claim found at 03:00 waited until the next day's cycle to become a cell, and a
proposer that died at 02:10 did not run again for twenty-four hours. Discovery is the top of
the funnel; a funnel fed once a day has a daily ceiling on everything below it.

WHAT THIS DOES. One pass an hour (the `quant-hourly-discovery.timer` unit on the VPS): the
organs below are run one at a time, each in its own subprocess with its own wall-clock budget,
in order of how long it has been since each last ran to completion. An organ that overruns is
killed at its budget and costs nothing else; an organ that cannot get memory is DEFERRED with
that reason (the box is a swapless 4 GB machine -- `scripts/memory_guard.py` waits for headroom
rather than racing the OOM killer); an organ that raises is recorded with its traceback tail.
Nothing here decides anything: every organ still donates through the proposer contract into
the intelligence intake, and the hourly pipeline compiles that intake into cells for the
gauntlet on its own clock. The daily cycle keeps its full-budget runs; this pass makes sure
no organ ever waits a day.

BUDGETS ARE THE RESEARCH BANDIT'S. Each organ's share of the hour follows
`libs.research.bandit.arm_weight` -- the same allocation the daily cycle uses -- floored so an
arm the bandit has cooled still runs, and capped so one arm cannot take the hour. Per-cell
caches inside the sweeps mean a short budget advances the search rather than restarting it.

    python3 research/hourly_discovery.py [--budget-s 2700] [--only name,name] [--dry-run]
    python3 research/hourly_discovery.py --organ NAME --budget-s N     # one organ, in-process
"""
from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "side_channels"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "HOURLY_DISCOVERY.json"
STATE = BASE / "data" / "hourly_discovery_state.json"
MEMORY_GUARD = ROOT / "scripts" / "memory_guard.py"

#: Total wall-clock an hourly pass may spend. The timer fires at :35; the external pipeline
#: fires at :05 and compiles whatever this pass donated.
TOTAL_BUDGET_S = 2700.0
MIN_ORGAN_S = 60.0
MAX_ORGAN_S = 900.0
#: Grace after an organ's own budget before the subprocess is killed: sweeps check their clock
#: between cells, and a cell can take a minute.
KILL_GRACE_S = 120.0
NEED_MB = 600
MEMORY_WAIT_S = 120
#: `memory_guard.py` exits 75 (EX_TEMPFAIL) when the box never had headroom -- deferred, not dead.
EX_TEMPFAIL = 75

#: WHAT AN HOUR PRODUCED, BY NAME. "Ran" is not a yield (principal 2026-09-05: "actual
#: candidates must be produced -- valuable datasets, moats and candidates -- not wasting time
#: like the old crawler"). Every organ's report carries some of these counters; the child prints
#: them on one YIELD line and the pass keeps a rolling total per organ, so the report says how
#: many cells, claims, tasks, endpoints and datasets each hour bought, and an organ that runs and
#: yields nothing reads as exactly that.
#: `stages_measured` and `cell_types` are the MEASUREMENT organs' yield. Without them a pass that
#: measured the whole funnel reads as `organs_with_zero_yield`, which is how an organ that
#: produces knowledge rather than cells eventually gets cut for producing nothing.
YIELD_KEYS = ("cells_proposed", "donated_rows", "proposals", "claims_new", "tasks_queued",
              "tasks", "endpoints", "acquired", "targets", "discovered", "candidates",
              "cases_joined", "symbols_calibrated", "symbols_unmeasured",
              "stages_measured", "cell_types")
YIELD_PREFIX = "YIELD "

#: name -> (how to call it). "run_budget" = run(budget_s=...); "run" = run(); "main" = main().
#: Ordered cheap-to-heavy within each group; the pass itself re-orders by staleness.
ORGANS: dict[str, str] = {
    # MEASUREMENT, and cheap: 4s and 1s against the full 47k-card docket, measured 2026-09-05.
    # The funnel ledger names the binding stage; the allocator turns the same measurement into
    # the trial budget. The proposers below call `trial_allocator.observed()` themselves rather
    # than reading its artifact, so nothing here depends on the pass order -- these two exist on
    # the roster so the measurement is refreshed every hour and its report never goes stale while
    # the thing it measures moves. Neither proposes a cell, neither touches a gate, both are
    # read-only.
    "conversion_ledger": "run",
    "trial_allocator": "run",
    # world miners: mechanism claims from public ground
    "repo_miner": "run",
    "deep_forest_miner": "run_budget",
    "world_crawler": "crawl_budget",
    # data organs: datasets and moats
    "data_prospector": "run",
    "acquire_datasets": "main",
    "fetch_futures_curves": "main",
    # proposers: families over the desk's bars, deflated by their own search
    "plumbing_miner": "run",
    "transition_alpha": "run_budget",
    "weak_signal_compiler": "run_budget",
    "fund_playbook": "run",
    "microstructure_miner": "run_budget",
    "alpha_evolution": "run_budget",
    "style_premia_sweep": "run_budget",
    "cross_asset_graph": "run_budget",
    "world_causal_graph": "run_budget",
    "anomaly_factory": "run_budget",
    "tail_alpha_search": "run_budget",
    "survivor_distiller": "run_budget",
    "factor_model_coevolution": "run_budget",
    # execution: the digital twin of every live intent (reads the gateway's ledgers; cheap)
    "execution_twin": "run_budget",
}


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _weight(name: str) -> float:
    try:
        from libs.research.bandit import arm_weight
        w = float(arm_weight(name))
        return w if w > 0 else 1.0
    except Exception:
        return 1.0


def plan(state: dict[str, Any], total_s: float = TOTAL_BUDGET_S,
         only: set[str] | None = None) -> list[tuple[str, float]]:
    """(organ, budget_s) in run order: the organ that has waited longest goes first, and the
    hour is shared by bandit weight between floor and cap. Sums to at most `total_s`."""
    names = [n for n in ORGANS if not only or n in only]
    if not names:
        return []
    weights = {n: _weight(n) for n in names}
    wsum = sum(weights.values())
    shares = {n: min(MAX_ORGAN_S, max(MIN_ORGAN_S, total_s * weights[n] / wsum)) for n in names}
    # the floor can overspend a small hour; scale back proportionally, never below the floor
    excess = sum(shares.values()) - total_s
    if excess > 0:
        flexible = {n: s - MIN_ORGAN_S for n, s in shares.items() if s > MIN_ORGAN_S}
        room = sum(flexible.values())
        for n, f in flexible.items():
            shares[n] -= excess * (f / room) if room > 0 else 0.0

    def staleness(n: str) -> tuple[float, float]:
        last = str((state.get(n) or {}).get("last_ok_at") or "")
        try:
            ts = datetime.fromisoformat(last).timestamp()
        except ValueError:
            ts = 0.0
        return (ts, -weights[n])

    return [(n, round(shares[n], 1)) for n in sorted(names, key=staleness)]


def run_organ(name: str, budget_s: float) -> dict[str, Any]:
    """One organ, in this process, by its declared calling convention. Returns its report."""
    how = ORGANS[name]
    mod = __import__(name)
    if how == "crawl_budget":
        return {"result": mod.crawl(run_budget_s=int(budget_s))}
    if how == "run_budget":
        params = inspect.signature(mod.run).parameters
        kwargs = {"budget_s": float(budget_s)} if "budget_s" in params else {}
        return {"result": mod.run(**kwargs)}
    if how == "run":
        return {"result": mod.run()}
    return {"rc": int(mod.main() or 0)}


def yield_of(result: Any) -> dict[str, int]:
    """The integer yield counters an organ's report carries, by name; empty when it says none."""
    if not isinstance(result, dict):
        return {}
    out: dict[str, int] = {}
    for k in YIELD_KEYS:
        v = result.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, int | float):
            out[k] = int(v)
        elif isinstance(v, list | dict):
            out[k] = len(v)
    return out


def parse_yield(tail: str) -> dict[str, int]:
    for line in reversed(tail.splitlines()):
        if line.startswith(YIELD_PREFIX):
            try:
                d = json.loads(line[len(YIELD_PREFIX):])
                return {str(k): int(v) for k, v in d.items()} if isinstance(d, dict) else {}
            except (ValueError, TypeError):
                return {}
    return {}


def _child_cmd(name: str, budget_s: float) -> list[str]:
    inner = [sys.executable, str(Path(__file__).resolve()), "--organ", name,
             "--budget-s", f"{budget_s:.0f}"]
    if MEMORY_GUARD.exists():
        return [sys.executable, str(MEMORY_GUARD), "--label", f"hourly_discovery:{name}",
                "--need-mb", str(NEED_MB), "--max-wait-s", str(MEMORY_WAIT_S), "--", *inner]
    return inner


def run_pass(total_s: float = TOTAL_BUDGET_S, only: set[str] | None = None, *,
             runner: Any = None, write: bool = True) -> dict[str, Any]:
    """The hourly pass. `runner(cmd, timeout_s) -> (rc, tail)` is injectable for tests."""
    state = _read(STATE)
    started = time.monotonic()
    rows: dict[str, Any] = {}
    for name, budget in plan(state, total_s, only):
        left = total_s - (time.monotonic() - started)
        if left < MIN_ORGAN_S:
            rows[name] = {"status": "SKIPPED_NO_TIME", "budget_s": budget}
            continue
        budget = min(budget, left)
        cmd = _child_cmd(name, budget)
        t0 = time.monotonic()
        try:
            if runner is not None:
                rc, tail = runner(cmd, budget + KILL_GRACE_S)
            else:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=budget + KILL_GRACE_S, check=False)
                rc, tail = r.returncode, ((r.stdout or "") + (r.stderr or ""))[-600:]
        except subprocess.TimeoutExpired as exc:
            rc, tail = None, f"killed at budget {budget:.0f}s + grace: " + str(
                (exc.stdout or b"")[-300:] if isinstance(exc.stdout, bytes) else exc.stdout
            )[-300:]
        secs = round(time.monotonic() - t0, 1)
        if rc == 0:
            status = "OK"
        elif rc == EX_TEMPFAIL:
            status = "DEFERRED_MEMORY"
        elif rc is None:
            status = "KILLED_AT_BUDGET"
        else:
            status = "FAILED"
        got = parse_yield(tail) if status == "OK" else {}
        rows[name] = {"status": status, "rc": rc, "seconds": secs, "budget_s": budget,
                      "yield": got, "tail": tail}
        st = state.setdefault(name, {})
        tot = st.setdefault("yield_total", {})
        for k, v in got.items():
            tot[k] = int(tot.get(k) or 0) + v
        st["last_yield"] = got
        st["runs"] = int(st.get("runs") or 0) + 1
        st["seconds_total"] = round(float(st.get("seconds_total") or 0.0) + secs, 1)
        st["last_status"] = status
        st["last_at"] = datetime.now(tz=UTC).isoformat()
        if status == "OK":
            st["last_ok_at"] = st["last_at"]
    report = {"at": datetime.now(tz=UTC).isoformat(), "total_budget_s": total_s,
              "spent_s": round(time.monotonic() - started, 1), "organs": rows,
              "yield": {k: sum(int((r.get("yield") or {}).get(k) or 0) for r in rows.values())
                        for k in YIELD_KEYS
                        if any(k in (r.get("yield") or {}) for r in rows.values())},
              "organs_with_zero_yield": sorted(n for n, r in rows.items()
                                               if r.get("status") == "OK"
                                               and not any((r.get("yield") or {}).values())),
              "ok": sum(1 for r in rows.values() if r.get("status") == "OK"),
              "deferred": sum(1 for r in rows.values() if r.get("status") == "DEFERRED_MEMORY"),
              "failed": sum(1 for r in rows.values() if r.get("status") == "FAILED")}
    if write:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), "utf-8")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=TOTAL_BUDGET_S)
    ap.add_argument("--only", default="", help="comma-separated organ names")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    ap.add_argument("--organ", default="", help="child mode: run ONE organ in-process")
    a = ap.parse_args()
    if a.organ:
        if a.organ not in ORGANS:
            print(f"unknown organ {a.organ!r}", flush=True)
            return 2
        rep = run_organ(a.organ, a.budget_s)
        res = rep.get("result")
        summary = (json.dumps(res, default=str)[:800] if isinstance(res, dict)
                   else f"rc={rep.get('rc')}")
        print(f"{a.organ}: {summary}", flush=True)
        print(YIELD_PREFIX + json.dumps(yield_of(res)), flush=True)
        return int(rep.get("rc") or 0)
    only = {s.strip() for s in a.only.split(",") if s.strip()} or None
    if a.dry_run:
        for name, b in plan(_read(STATE), a.budget_s, only):
            print(f"{name:28s} {b:7.1f}s", flush=True)
        return 0
    rep = run_pass(a.budget_s, only)
    print(f"HOURLY DISCOVERY  ok={rep['ok']} deferred={rep['deferred']} failed={rep['failed']} "
          f"spent={rep['spent_s']}s of {rep['total_budget_s']:.0f}s -> {REPORT}", flush=True)
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
