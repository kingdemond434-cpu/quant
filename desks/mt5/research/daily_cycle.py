"""daily_cycle: the three processes that actually move an edge toward capital.

    shadow_forward  ->  promoter  ->  markout

WHY THIS FILE HAD TO EXIST. `research_supervisor` restarts hunts and `hourly_cycle` checks health,
mines the web and writes a frontier report. Both work. Neither has ever run `shadow_forward`,
`promoter` or `markout` -- so nine validated candidates sat in `shadow_forward.SLEEVES` with
nothing to execute them, accruing no evidence, unable to promote, for as long as that remained
true. A pipeline that does not terminate in a decision is not a pipeline.

The supervisor could not have been the home for this. It is built around one-shot DONE markers: a
target runs until its marker exists and is never started again. That is right for a hunt and wrong
for anything daily, which is why these three were never added to it.

WHY DATE-STAMPED AND NOT CLOCK-TRIGGERED. The execution box is a laptop that sleeps. A task
scheduled for 22:00 simply never runs on a day the lid was shut at 21:30, and the failure is
silent -- the desk looks idle rather than broken. This runs the day's work on the FIRST invocation
of each UTC day and no-ops on every later one, so an hourly caller gets exactly one run per day
whenever the machine happens to be awake. `shadow_forward` is independently idempotent on the same
key, so a double call is safe even if this guard is bypassed.

    python research/daily_cycle.py            # from the hourly loop, or by hand
    python research/daily_cycle.py --force    # re-run today (after fixing a failure)
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import re
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "research"), str(BASE / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

STAMP = BASE / "data" / "daily_cycle_state.json"
LOG = BASE / "logs" / "daily_cycle.log"


def dlog(msg: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_stamp() -> dict:
    if not STAMP.exists():
        return {}
    try:
        return json.loads(STAMP.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def run_step(name: str, fn) -> dict:
    """Run one step, recording the outcome either way.

    A step that raises must NOT abort the cycle. Shadow needs a live MT5 terminal and will fail on
    a research box; the promoter and markout read files and do not. Stopping the whole cycle on the
    first failure would mean a closed laptop silently suppresses the execution measurement too --
    and an unmeasured failure is the thing this desk is least willing to have.
    """
    started = datetime.now(UTC)
    # THE WRITE-OR-EXPLAIN CONTRACT (2026-09-23), at the daily cycle's own leg boundary. This is
    # the second of the desk's two cycles and it is the one with a real runner loop, so a single
    # pair of calls here covers every step in `STEPS` -- see `libs/ops/write_or_explain.py`.
    _woe, _raised = _woe_before(name), ""
    try:
        fn()
        out = {"ok": True}
        dlog(f"{name}: ok")
    except (Exception, SystemExit) as exc:
        # SystemExit TOO (v1.2 nit). A step that calls sys.exit is a failed step, not the end of
        # the chain -- and an uncaught SystemExit(75) would leave this process with the exit code
        # the hourly leg reads as a stand-down, for a chain that in fact ran.
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        _raised = str(out["error"])
        dlog(f"{name}: FAILED -- {out['error']}")
        dlog(traceback.format_exc().rstrip())
    out["seconds"] = round((datetime.now(UTC) - started).total_seconds(), 1)
    _woe_after(name, _woe, out, raised=_raised, wall_s=float(out["seconds"]))
    return out


def _woe_before(name: str) -> dict:
    """Stat step `name`'s DECLARED artifact(s) before it runs. Never fails the step."""
    try:
        from libs.ops.write_or_explain import before_leg
        return before_leg(name)
    except Exception:
        return {}


def _woe_after(name: str, before: dict, out: object, *, raised: str = "",
               wall_s: float | None = None) -> None:
    """Did the step write what it declared, or say why not? Prints the defect; never raises."""
    try:
        from libs.ops.write_or_explain import DEFECTS, observe
        rec = observe(name, before, out, raised=raised, wall_s=wall_s)
        if str(rec.get("verdict")) in DEFECTS:
            dlog(f"  {rec['verdict']} {rec.get('detail', '')}")
    except Exception as exc:
        dlog(f"  write-or-explain not recorded for {name}: {type(exc).__name__}: {exc}")


def _scalp_gauntlet() -> None:
    """The scalp lane's ten-gate certificate, judged daily on the box's own M5/M15 bars BEFORE
    shadow, so the clock's row can name its certificate today. scripts/scalp_gauntlet.py builds
    one cell per scalp_shadow.CANDIDATES entry through external_gauntlet.run_gauntlet -- the one
    validator -- and writes reports/SCALP_GAUNTLET.json. rc=2 is UNMEASURED (no M5/M15 tape or
    no cost basis on this box): the honest answer off the desk box, never a cycle failure."""
    sys.path.insert(0, str(BASE / "scripts"))
    import scalp_gauntlet
    rc = scalp_gauntlet.main()
    if rc not in (0, 2):
        raise RuntimeError(f"scalp_gauntlet returned {rc}")


def _shadow() -> None:
    import shadow_forward
    shadow_forward.main()


def _qquant_shadow() -> None:
    import qquant_shadow
    qquant_shadow.main()


def _execution() -> None:
    """Reconstruct execution quality from the venue's own ticks BEFORE the promoter runs."""
    from mt5desk import shadow_execution
    shadow_execution.main()


def _recertify() -> None:
    """Re-judge every standing certificate under the CURRENT cost model, before the promoter
    reads the shadow verdicts. The audit never shrinks canon; the promoter refuses to fund a
    certificate the audit fails (BLOCKED_COST_REGRADE). Unscheduled until 2026-09-05 -- the
    audit existed, ran by hand once, and nothing read it."""
    import importlib.util
    path = BASE / "scripts" / "recertify_canon.py"
    spec = importlib.util.spec_from_file_location("recertify_canon", path)
    if spec is None or spec.loader is None:
        dlog("recertify: scripts/recertify_canon.py not present on this tree")
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()
    dlog(f"recertify: rc={rc} -> reports/recertification_audit.json")


def _promote() -> None:
    import promoter
    promoter.main()


def _weekly_hunt_refresh() -> None:
    """Keep the existing six-day research sweep off the gateway's order lock."""
    marker = BASE / "data" / "hunt7_state.json"
    try:
        last = float(json.loads(marker.read_text(encoding="utf-8")).get("last_sweep", 0))
    except (OSError, ValueError, TypeError):
        last = 0.0
    now = datetime.now(UTC).timestamp()
    if now - last <= 6 * 86400:
        return
    # Explicit imports make every member visible to the canonical wiring census.
    import fetch_universe
    import free_shadows
    import run_hunt7
    import run_hunt8
    import run_hunt9
    import run_hunt10
    import run_hunt12
    jobs = (("fetch_universe", fetch_universe.main), ("run_hunt7", run_hunt7.main),
            ("run_hunt8", run_hunt8.main), ("run_hunt9", run_hunt9.main),
            ("free_shadows", free_shadows.main), ("run_hunt10", run_hunt10.main),
            ("run_hunt12", run_hunt12.main))
    for module, runner in jobs:
        # These two CLIs parse sys.argv when called without an explicit argument list.
        # The daily step's own --step flag must never become a hunt argument.
        result = runner([]) if module in {"fetch_universe", "run_hunt12"} else runner()
        if isinstance(result, int) and result != 0:
            raise RuntimeError(f"{module} exited {result}; weekly stamp not advanced")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"last_sweep": now}), encoding="utf-8")
    dlog("weekly hunt7-12 + states sweep completed")


def _reconcile() -> None:
    import forward_reconcile
    forward_reconcile.main()


def _portfolio() -> None:
    """How many INDEPENDENT bets is the book -- before anything is sized as if it were new alpha."""
    import portfolio_evidence
    portfolio_evidence.main()


def _decay() -> None:
    import decay_monitor
    decay_monitor.main()


def _markout() -> None:
    from mt5desk.markout import compute, load_jsonl, render
    data = BASE / "data"
    from libs.ops.live_ledger_view import ledger_path as _audited_ledger_path
    m = compute(load_jsonl(data / "order_intents.jsonl"),
                load_jsonl(_audited_ledger_path(data / "live_ledger.jsonl")))
    for line in render(m).splitlines():
        dlog("  " + line)
    markout_path = BASE / "reports" / "markout.json"
    markout_path.parent.mkdir(parents=True, exist_ok=True)
    at = datetime.now(UTC).isoformat(timespec="seconds")
    markout_path.write_text(json.dumps({
        "at": at,
        "usable": m.usable, "n_matched": m.n_matched,
        "n_unfilled_intents": m.n_unfilled_intents,
        "n_unmatched_deals": m.n_unmatched_deals,
        "n_deals": m.n_deals, "attributed_deals": m.attributed_deals,
        "attributed_share": m.attributed_share,
        "mean_slip_quote": m.mean_slip_quote, "mean_slip_r": m.mean_slip_r,
        "edge_share": m.edge_share, "why": m.why,
    }, indent=2), encoding="utf-8")
    # THE CHAIN, MATERIALISED (2026-09-08). One row per deal the desk can walk back to its
    # intent -- release id, state vector, entry order, entry deal, close deal, realised R -- and
    # the share of all deals that have one. The programme's "no semantic breaks" property is
    # this file's `share`, and its target is 1.0.
    (BASE / "reports" / "attribution_chain.json").write_text(json.dumps({
        "at": at, "deals": m.n_deals, "attributed": m.attributed_deals,
        "share": m.attributed_share, "target": 1.0,
        "unmatched_deals": m.n_unmatched_deals, "chain": m.chain,
    }, indent=1, default=str), encoding="utf-8")


def _refresh_bars() -> None:
    """Extend every cached H1 parquet from the live terminal, before anything reads bars.

    NOTHING SCHEDULED THIS. `refresh_tail` globs the whole store, so its SCOPE was never the
    problem -- its output path was hardcoded to a third machine's home directory, so on the desk
    box it refreshed nothing and no task ran it. Measured 2026-08-27: of 295 parquets on that box
    only 49 had been written that day, 195 dated 08-26 and 51 dated 08-22, so the gauntlet was
    screening most of the universe on bars up to five days old.
    """
    import refresh_tail

    # BOUNDED, RESUMING (2026-10-29): one unbounded pass over the lake took 6h34m of MT5-Daily's
    # 10 h. The hourly `refresh_bars` leg runs the same refresher every hour, and both now resume
    # from refresh_tail's cursor (stalest series first, forward-blocked symbols before all).
    rc = refresh_tail.main(["--budget-s", f"{REFRESH_BARS_BUDGET_S:.0f}"])
    # rc=2 is "no terminal on this box", the honest answer everywhere but the desk box.
    if rc not in (0, 2):
        raise RuntimeError(f"refresh_tail returned {rc}")


#: The daily step's share of the bar refresh; the hourly leg refreshes every hour as well.
REFRESH_BARS_BUDGET_S = 1800.0


def _deepen_bars() -> None:
    """Widen every cached series back toward what the venue serves, PREPEND ONLY.

    `research/deepen_universe.py` was recovered from the trading box with no clock, so the depth
    of every parquet stayed frozen at whatever its first producer asked for. Its own cursor and
    `--recheck-hours 20` make a daily pass the natural cadence; it stands down inside a placement
    window by itself. Off the box `MetaTrader5` is absent and that is recorded, not raised.
    """
    try:
        import deepen_universe
    except ModuleNotFoundError:
        dlog("deepen_bars: research/deepen_universe.py not present on this tree")
        return
    try:
        rc = deepen_universe.main(["--budget-s", "1500"])
    except ModuleNotFoundError as exc:
        dlog(f"deepen_bars: no terminal on this box ({exc.name}); UNMEASURED")
        return
    dlog(f"deepen_bars: rc={rc}")


def _capacity_watch() -> None:
    """Two read-only readings a restart window needs, taken daily so neither goes stale.

    `scripts/restart_for_capacity.py` with no flag only measures its preconditions and the
    terminal's MaxBars into reports/CAPACITY_RESTART.json -- it never stops or restarts anything
    without `--stage`, which no clock passes. `scripts/check_after_reboot.py --verify` names any
    process or task that did not come back since the healthy baseline, into
    reports/REBOOT_VERIFY.json; rc 1 is that finding and rc 2 is "no baseline", both recorded.
    """
    import subprocess
    for script, args in (("scripts/restart_for_capacity.py", []),
                         ("scripts/check_after_reboot.py", ["--verify"])):
        path = BASE / script
        if not path.exists():
            dlog(f"capacity_watch: {script} not present on this tree")
            continue
        try:
            r = subprocess.run([sys.executable, str(path), *args], cwd=str(BASE),
                               capture_output=True, text=True, timeout=600, check=False)
            dlog(f"capacity_watch: {script} rc={r.returncode} "
                 f"{(r.stdout or r.stderr).strip().splitlines()[-1:] or ''}")
        except (OSError, subprocess.SubprocessError) as exc:
            dlog(f"capacity_watch: {script} failed to run ({type(exc).__name__}: {exc})")


def _cost_fields() -> None:
    """Fill `tick_value` for any registry symbol that lacks one, from the live terminal.

    RUNS FIRST BECAUSE EVERY LATER STEP PRICES SOMETHING. `tick_value` is the only field carrying
    a price in ACCOUNT currency, so a symbol without one has `spread_cost_per_lot == 0.0` and
    cannot clear gate 8 (stress_costs) however many bars it has. Measured 2026-08-27: 82 of 197
    registry rows had none, so 42% of the desk's own universe was structurally incapable of
    producing a certificate. Fill-only and merge-only, so it can never rewrite a live sleeve's
    cost basis mid-window -- `cost_hash` is part of sleeve identity.
    """
    import refresh_cost_fields

    rc = refresh_cost_fields.main()
    # rc=2 is "no terminal here", which is the honest answer on any box but the desk box and must
    # not fail the cycle; anything else is a real failure.
    if rc not in (0, 2):
        raise RuntimeError(f"refresh_cost_fields returned {rc}")


def _factor_residual() -> None:
    """Strip every instrument to its economic drivers and propose what the residual pays.

    RUNS RIGHT AFTER THE BARS AND THE COST FIELDS, because it needs both: the panel is built from
    the refreshed H1 parquets and every expectancy is scored against `Costs.from_symbol`, which is
    empty until `cost_fields` has filled `tick_value`.

    DAILY, NOT HOURLY, AND THAT IS A STATISTICAL CHOICE RATHER THAN A BUDGET ONE. The sweep takes
    seconds, so cadence is not about compute -- it is about multiplicity. Re-running 936 tests
    every hour would search 24x harder per day while charging the same deflation, which is the
    quiet way to manufacture a survivor. The inputs are H1 bars and driver relationships that move
    on a scale of weeks; once a day is as often as this has anything new to say.

    PROPOSES ONLY. The donation lands in data/intelligence/factor_residual/ and the ordinary
    hourly compiler admits it as EXACT_RECIPE, so every proposal still faces the ten gates.
    """
    from research import factor_residual_engine

    rep = factor_residual_engine.run()
    dlog(f"factor residual: {rep['hypotheses_measured']}/{rep['hypotheses_stated']} claims "
         f"measured, {rep['tests_run']} tests, {rep['cells_proposed']} proposed")


def _state_admission() -> None:
    """Re-judge every state dimension against the trades that have accrued since yesterday.

    RUNS BEFORE SHADOW, so the verdicts the allocator reads today are based on every trade closed
    up to yesterday rather than on a report from whenever someone last ran it by hand. The whole
    point of the test is that it moves as the evidence does: a dimension that is UNDERPOWERED at
    487 trades is not underpowered forever, and one that looks fine today can be measured worse
    next month. A verdict nobody refreshes is a verdict nobody should act on.
    """
    import state_admission_run

    doc = state_admission_run.run()
    dlog(f"state admission: {doc['n_trades']} trades, "
         f"{len(doc['admitted'])} allowed, {len(doc['graveyard'])} in the graveyard"
         + (f" ({', '.join(doc['graveyard'])})" if doc["graveyard"] else ""))


#: THE DAILY PROPOSERS, in their declared order. Module-level so the census
#: (`scripts/check_producer_yield.py`) and the liveness check (`libs/ops/seat_clocks.py`) read
#: ONE list -- a list that can drift from the runner reports on organs nobody runs.
PROPOSERS: tuple[str, ...] = (
    "plumbing_miner", "transition_alpha", "weak_signal_compiler",
    "fund_playbook", "microstructure_miner", "alpha_evolution",
    "style_premia_sweep", "cross_asset_graph", "anomaly_factory",
    "tail_alpha_search", "survivor_distiller", "factor_model_coevolution",
    # Reflective factor timing (IBK 2026 design): publishes its own admission
    # contract, desks/mt5/reports/REFLECTIVE_TIMING.json. Sizes nothing.
    "reflective_timing_contract",
    # Text-derived indices (event/policy factors from collected news, JP/KR/CN
    # retail blog attention and mood): the gain test against a shuffled-date
    # placebo, then the pre-declared exogenous_conditioner cells through the donor
    # door. Writes desks/mt5/reports/NLP_SOCIAL_CELLS.json.
    "nlp_social_cells",
    # Learned GNN/attention miners (numpy): cells, forecast axes and allocation
    # intel. Daily, on their own budget, so no hourly organ's share shrinks.
    "learned_miners",
    # THE NEGATIVE HALF OF EXPERIENCE (Tier-1 Q17). `survivor_distiller` was
    # already here and `negative_knowledge` -- the model of what KILLS a cell --
    # ran on no clock at all, which is the classic defect: the organ existed and
    # produced nothing. Its report feeds the experience split.
    "negative_knowledge",
    # THE REGIME SPLIT (2026-09-30): every price-only family searched inside one
    # control-room regime at a time, purged walk-forward as the kill, survivors
    # donated as family `regime_split` to the same gauntlet.
    "regime_split_miner",
    # THE PUBLIC TRADER GENOME WITH ITS GRAVEYARD (2026-10-06, audit row 35): the
    # own-book forensics plus the alive+dead genome, its base rates, failure memory,
    # crowding prior and style-analogue cells through the donor door.
    "book_forensics",
)

#: Per-proposer memory across passes: when each was last STARTED, how it ended, and the UTC day
#: it last finished an attempt. The rotation below is read from here.
PROPOSER_STATE = BASE / "data" / "daily_proposers_state.json"
#: Published after EVERY proposer, so a pass killed partway still says what it did.
PROPOSER_REPORT = BASE / "reports" / "DAILY_PROPOSERS.json"
#: The bandit-scaled budget each proposer is handed is unchanged from before 2026-10-29:
#: base (its own `run(budget_s=...)` default, 1,200 s when it declares none) x arm weight,
#: clipped to [300, 3,600] s.
PROPOSER_MIN_BUDGET_S = 300.0
PROPOSER_MAX_BUDGET_S = 3600.0
PROPOSER_DEFAULT_BUDGET_S = 1200.0
#: How long past its OWN budget a proposer may run before its child is killed. Half its budget
#: again, never under five minutes: a sweep checks its clock between cells and a cell can be slow.
#: This is a bound on a proposer that ignores its own budget, not a cut to one that honours it.
PROPOSER_GRACE_FLOOR_S = 300.0
#: A proposer whose `run()` takes no budget: bounded at the larger of this and 1.5x its last
#: measured complete run, so a slow-but-finishing organ is never killed for being slow.
UNBUDGETED_BOUND_S = 5400.0
#: A proposer KILLED at its bound records no wall time, so its bound would never grow and it
#: could be killed at the same bound every day (fund_playbook, reflective_timing_contract,
#: 2026-10-29). Each kill raises the next bound by this factor, capped: past the cap it is still
#: deferred -- keeping its place -- and goes RED by name at 48h (seat_clocks.red_proposers).
PROPOSER_BOUND_GROWTH = 1.5
PROPOSER_BOUND_CAP_S = 2 * UNBUDGETED_BOUND_S
#: The child's stdout line that carries its report back to the chain.
PROPOSER_RESULT_PREFIX = "PROPOSER_RESULT "
#: Outcomes that FINISH a proposer's attempt for the day (a kill or a deferral does not).
PROPOSER_FINISHED = frozenset({"OK", "FAILED", "ABSENT"})


def _read_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(p: Path, doc: dict) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(p, json.dumps(doc, indent=1, default=str))
    except OSError as exc:
        dlog(f"  could not write {p.name}: {type(exc).__name__}: {exc}")


def proposer_order(state: dict, today: str,
                   names: tuple[str, ...] = PROPOSERS) -> list[str]:
    """The proposers still owed an attempt today, LEAST-RECENTLY-STARTED first.

    THE STARVATION THIS REMOVES (2026-10-29). `_proposers` ran nineteen proposers in one fixed
    order inside ONE chain step, and a step is stamped only when it ends. MT5-Daily was terminated
    at its time limit (last result 0x41306, 10/28 22:50 local) somewhere inside that step, so the
    step was never stamped; every later pass -- the hourly `daily` leg, killed at 900 s -- began
    the step again at `plumbing_miner` and died in the first organ or two. The tail of the list
    (anomaly_factory, tail_alpha_search, survivor_distiller, ...) could not be reached on any
    clock, and PRODUCER_YIELD read every one DEAD.

    Ordering by when each was last STARTED (not finished) is what makes it rotate: a proposer
    that was started and then killed goes to the BACK, so the slowest organ is never first twice
    running, and the ones that waited longest go first. Never-started proposers lead, in declared
    order. A proposer that already finished an attempt today is not repeated.
    """
    todo = [n for n in names if str((state.get(n) or {}).get("done_day") or "") != today]
    return sorted(todo, key=lambda n: (str((state.get(n) or {}).get("last_started_at") or ""),
                                       names.index(n)))


def proposer_bound(budget_s: float | None, st: dict | None = None) -> float:
    """Seconds a proposer's child may run before it is killed (see PROPOSER_GRACE_FLOOR_S), raised
    to PROPOSER_BOUND_GROWTH x the bound it was last KILLED at, capped at PROPOSER_BOUND_CAP_S."""
    killed = float((st or {}).get("killed_at_bound_s") or 0.0)
    grown = min(PROPOSER_BOUND_CAP_S, PROPOSER_BOUND_GROWTH * killed) if killed else 0.0
    if budget_s is not None:
        return max(float(budget_s) + max(PROPOSER_GRACE_FLOOR_S, 0.5 * float(budget_s)), grown)
    last_ok = float((st or {}).get("last_ok_wall_s") or 0.0)
    return max(UNBUDGETED_BOUND_S, 1.5 * last_ok, grown)


def _proposer_absent(name: str, exc: ModuleNotFoundError) -> bool:
    """True only when the module that could not be found IS the proposer itself (PR #524 audit).

    A ModuleNotFoundError raised while importing a proposer that is on this tree -- its own
    `import scipy`, say -- names the dependency, not the proposer: that proposer is FAILED."""
    missing = str(getattr(exc, "name", "") or "")
    if missing:
        return missing == name or name.startswith(missing + ".")
    import importlib.util
    try:
        return importlib.util.find_spec(name) is None
    except (ImportError, ValueError):
        return False


def _missing_dep_error(name: str, exc: ModuleNotFoundError) -> str:
    return (f"{name} is present but its import failed: ModuleNotFoundError: "
            f"{getattr(exc, 'name', None) or exc}: {exc}")[:400]


def _proposer_budget(name: str) -> float | None:
    """The bandit-scaled budget for `name`, exactly as the in-process loop computed it; None
    when its `run()` takes no budget. Raises ModuleNotFoundError when it is not on this tree."""
    import inspect
    try:
        from libs.research.bandit import arm_weight
    except Exception:
        def arm_weight(source, kind=None):                        # type: ignore[misc]
            return 1.0
    mod = __import__(name)
    params = inspect.signature(mod.run).parameters
    if "budget_s" not in params:
        return None
    base = float(params["budget_s"].default or PROPOSER_DEFAULT_BUDGET_S)
    return float(min(PROPOSER_MAX_BUDGET_S, max(PROPOSER_MIN_BUDGET_S, base * arm_weight(name))))


def _proposer_child(name: str, budget_s: float | None) -> int:
    """Child mode: run ONE proposer in this process and print its result line."""
    t0 = time.monotonic()
    try:
        mod = __import__(name)
        rep = mod.run(**({"budget_s": float(budget_s)} if budget_s is not None else {}))
    except ModuleNotFoundError as exc:
        if not _proposer_absent(name, exc):
            # A proposer that IS on this tree but cannot import a dependency is broken, not
            # absent: ABSENT is skipped by the liveness check, so it would read OK forever.
            traceback.print_exc()
            print(PROPOSER_RESULT_PREFIX + json.dumps(
                {"status": "FAILED", "error": _missing_dep_error(name, exc)}), flush=True)
            return 1
        print(PROPOSER_RESULT_PREFIX + json.dumps({"status": "ABSENT", "error": str(exc)}),
              flush=True)
        return 3
    except Exception as exc:
        traceback.print_exc()
        print(PROPOSER_RESULT_PREFIX + json.dumps(
            {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"[:400]}), flush=True)
        return 1
    out: dict = {"status": "OK", "wall_s": round(time.monotonic() - t0, 1)}
    if isinstance(rep, dict):
        for k in ("tests_run", "cells_proposed", "donated_rows"):
            if isinstance(rep.get(k), int | float) and not isinstance(rep.get(k), bool):
                out[k] = rep[k]
    print(PROPOSER_RESULT_PREFIX + json.dumps(out, default=str), flush=True)
    return 0


def _run_proposer(name: str, budget_s: float | None, bound_s: float) -> dict:
    """Run `name` in its own child, killed (whole tree) at `bound_s`. Never raises."""
    cmd = [sys.executable, "-u", "-W", "ignore", str(Path(__file__).resolve()),
           "--proposer", name, "--budget-s", "none" if budget_s is None else f"{budget_s:.0f}"]
    root = str(BASE.parent.parent)
    if root not in sys.path:
        sys.path.append(root)
    try:
        from libs.ops.proctree import run as _run
    except Exception:
        import subprocess
        _run = subprocess.run                                        # type: ignore[assignment]
    import subprocess
    t0 = time.monotonic()
    try:
        r = _run(cmd, capture_output=True, text=True, timeout=bound_s, check=False,
                 cwd=str(BASE))
    except subprocess.TimeoutExpired:
        return {"status": "KILLED_AT_BOUND", "wall_s": round(time.monotonic() - t0, 1),
                "why": f"ran past its bound of {bound_s:.0f}s (budget "
                       f"{'none' if budget_s is None else f'{budget_s:.0f}s'} + grace)"}
    except Exception as exc:
        return {"status": "FAILED", "wall_s": round(time.monotonic() - t0, 1),
                "error": f"could not start: {type(exc).__name__}: {exc}"[:400]}
    text = (r.stdout or "") + (r.stderr or "")
    res: dict = {}
    for line in reversed(text.splitlines()):
        if line.startswith(PROPOSER_RESULT_PREFIX):
            with contextlib.suppress(ValueError):
                res = json.loads(line[len(PROPOSER_RESULT_PREFIX):])
            break
    if not res:
        res = {"status": "OK" if r.returncode == 0 else "FAILED",
               "error": "" if r.returncode == 0 else f"exit {r.returncode}: {text[-300:]}"}
    res["wall_s"] = round(time.monotonic() - t0, 1)
    res["rc"] = r.returncode
    return res


def _publish_proposers(rows: dict, order: list[str], today: str) -> None:
    left = _time_left_s()
    _write_json(PROPOSER_REPORT, {
        "at": datetime.now(UTC).isoformat(timespec="seconds"), "day": today,
        "order": order, "proposers": rows,
        "deadline": {"basis": _DEADLINE["basis"], "seconds": _DEADLINE["seconds"],
                     "left_s": None if left is None else round(left, 1)},
        "done": sorted(n for n, r in rows.items() if r.get("status") in PROPOSER_FINISHED),
        "deferred": sorted(n for n, r in rows.items()
                           if r.get("status") == "DEFERRED_NO_TIME"),
        "killed": sorted(n for n, r in rows.items() if r.get("status") == "KILLED_AT_BOUND"),
        "rule": ("each proposer runs in its own child, bounded at its own budget + grace; one "
                 "that does not fit the pass's remaining time is DEFERRED, never cut; order is "
                 "least-recently-started first, so a killed or deferred proposer never blocks "
                 "the same tail twice"),
    })


def _proposers() -> None:
    """The proposer sweeps that hand the gauntlet cells it would never otherwise see.

    Each is a PROPOSER in the `factor_residual_engine` sense: it runs a family over the desk's
    bars, scores against cost, deflates by its own search, and donates survivors into the miner
    contract. None admits anything. Daily, because cadence is multiplicity. A failure in one
    must not cost the others their run, so each is fenced.

    NO PROPOSER CAN SILENCE ANOTHER (2026-10-29). Each runs in its OWN child process, killed at
    its own bound (`proposer_bound`), in least-recently-started order (`proposer_order`), and a
    proposer whose bound does not fit what is left of this pass's deadline is DEFERRED -- left
    for the next pass, at the front -- instead of being started and killed by the task limit.
    Budgets are exactly what they were: the bandit sets them and nothing here shrinks one.
    Progress is published to PROPOSER_REPORT after every proposer.
    """
    # THE BANDIT SETS THE BUDGETS. Each proposer belongs to a research direction; its time budget
    # is the base budget scaled by that direction's share (uniform = 1.0), clipped so no arm is
    # ever starved to zero -- the exploration floor is what keeps a cold arm alive.
    today = _utc_today()
    state = _read_json(PROPOSER_STATE)
    order = proposer_order(state, today)
    rows: dict[str, dict] = {}
    for name in order:
        st = state.setdefault(name, {})
        try:
            budget = _proposer_budget(name)
        except ModuleNotFoundError as exc:
            if _proposer_absent(name, exc):
                dlog(f"{name}: not present on this tree")
                rows[name] = {"status": "ABSENT"}
                st.update({"last_status": "ABSENT", "done_day": today})
            else:
                # Present but broken (a missing dependency): FAILED, with its cause, so the
                # liveness check names it RED instead of skipping it as ABSENT forever.
                err = _missing_dep_error(name, exc)
                dlog(f"{name} FAILED (non-fatal): {err}")
                now_iso = datetime.now(UTC).isoformat(timespec="seconds")
                rows[name] = {"status": "FAILED", "error": err}
                st.update({"last_status": "FAILED", "last_error": err, "last_at": now_iso,
                           "done_day": today})
            _write_json(PROPOSER_STATE, state)
            _publish_proposers(rows, order, today)
            continue
        except Exception as exc:
            budget = None
            dlog(f"{name}: budget unreadable ({type(exc).__name__}: {exc}); running unbudgeted")
        bound = proposer_bound(budget, st)
        left = _research_left_s()
        if left is not None and bound > left:
            dlog(f"{name}: DEFERRED -- bound {bound:.0f}s does not fit the {left:.0f}s left "
                 f"before this pass's deadline ({_DEADLINE['basis']}); it leads the next pass")
            rows[name] = {"status": "DEFERRED_NO_TIME", "bound_s": round(bound),
                          "left_s": round(left)}
            st["last_deferred_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            _write_json(PROPOSER_STATE, state)
            _publish_proposers(rows, order, today)
            continue
        st["last_started_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        _write_json(PROPOSER_STATE, state)
        res = _run_proposer(name, budget, bound)
        res["budget_s"] = None if budget is None else round(budget)
        res["bound_s"] = round(bound)
        rows[name] = res
        status = str(res.get("status"))
        st.update({"last_status": status, "last_wall_s": res.get("wall_s"),
                   "last_at": datetime.now(UTC).isoformat(timespec="seconds")})
        if status == "OK":
            st["last_ok_at"] = st["last_at"]
            st["last_ok_wall_s"] = res.get("wall_s")
            st.pop("killed_at_bound_s", None)
        elif status == "KILLED_AT_BOUND":
            st["killed_at_bound_s"] = round(bound)
        if status in PROPOSER_FINISHED:
            st["done_day"] = today
        _write_json(PROPOSER_STATE, state)
        _publish_proposers(rows, order, today)
        if status == "OK":
            dlog(f"{name}: {res.get('tests_run', '?')} tests, "
                 f"{res.get('cells_proposed', res.get('donated_rows', '?'))} proposed"
                 + (f" (budget {budget:.0f}s)" if budget is not None else "")
                 + f" in {res.get('wall_s')}s")
        else:
            dlog(f"{name} {status} (non-fatal): {res.get('error') or res.get('why') or ''}")
    _publish_proposers(rows, order, today)


def _world_miners() -> None:
    """Public systems and the deep forest, read for MECHANISM CLAIMS before the proposers run.

    The repo miner reads watched repositories (GitHub and Gitee) and the deep-forest miner reads
    Chinese practitioner ground -- competition records, trader interviews, platform communities,
    Q&A/blog/social, code hosts, video transcripts -- by search-engine and platform routes the
    link-following crawler cannot reach. Both emit deepening tasks (repo_mechanism,
    story_mechanism) and the deep-forest miner feeds every URL it finds into the crawler's
    frontier, so the ground keeps growing between runs. Off the box the network is absent; each
    records that and rebuilds its queue from its ledger.
    """
    for name, kwargs in (("repo_miner", {}), ("deep_forest_miner", {"budget_s": 900.0})):
        try:
            mod = __import__(name)
            rep = mod.run(**kwargs)
            dlog(f"{name}: " + (f"network={rep.get('network')} tasks="
                                 f"{rep.get('tasks_queued', rep.get('tasks', '?'))} "
                                 f"claims_new={rep.get('claims_new', '-')}"
                                 if isinstance(rep, dict) else "ran"))
        except ModuleNotFoundError:
            dlog(f"{name}: not present on this tree")
        except Exception as exc:
            dlog(f"{name} FAILED (non-fatal): {type(exc).__name__}: {exc}")


def _research_bandit() -> None:
    """Which research directions earn the next unit of compute -- written before the proposers
    and the deepening worker read it."""
    try:
        import research_bandit
        d = research_bandit.run()
        research_bandit.publish(d)
        top = sorted(d["shares"].items(), key=lambda kv: -kv[1])[:3]
        dlog("research bandit: " + ", ".join(f"{a}={s:.0%}" for a, s in top))
    except Exception as exc:
        dlog(f"research_bandit FAILED (non-fatal): {type(exc).__name__}: {exc}")


def _state_research_feedback() -> None:
    """Coverage map -> research instructions; prospector -> acquisition queue; resurrection;
    the live manifest; research-productivity metrics. Every one reads artifacts the earlier steps
    have just refreshed, which is why they run late in the cycle."""
    for name in ("excursions", "counterfactual_markout", "action_counterfactuals",
                 "exit_accounts", "alpha_genome", "opportunity_curve",
                 "regime_coverage",
                 # THE BREADTH LANE, after the coverage map because they read the same shadow
                 # ledgers it has just re-read and write into the same deepening queue: how many
                 # INDEPENDENT bets the book is against how many labels it has, what pays inside
                 # the book's own worst periods, and which states of a surviving edge deserve
                 # capital. None conditions capital; each queues research keyed on its own source.
                 "alpha_breadth", "drawdown_alpha", "survivor_neighbourhood",
                 "data_prospector", "resurrection", "research_productivity",
                 "research_pnl", "mutation_yield", "drift_monitor", "revival_engine",
                 # THE COUNTERFACTUAL WORLD runs BEFORE missed_growth on purpose: it writes
                 # VETO_ALPHA, which is the veto rails' evidence, and a rail judged against
                 # yesterday's report is a rail judged a day late.
                 "counterfactual_replay",
                 "missed_growth", "capital_modifier_score", "execution_intelligence",
                 # The nine-term growth decomposition and the portfolio gap: both existed and
                 # ran on nobody's clock (found 2026-09-05). They read every term's own ledger,
                 # which is why they run after the engines that write those ledgers.
                 "allocator_attribution", "portfolio_gap",
                 # THE WAREHOUSE'S FEEDBACK ARM. It reads the conditioning ledger, RESEARCH_PNL's
                 # share_of_heat and allocator_attribution's state term, so it runs after all
                 # three; it writes a lifecycle status onto every feature sidecar, which is what
                 # stops the desk spending compute on features that do not contribute.
                 "feature_roi",
                 "live_manifest",
                 # THE TIMING LAYER AND THE CARTOGRAPHER'S MAP (Tier-1 audit G18/G15,
                 # 2026-09-08). All three existed and ran on nobody's clock. `hour_surface`
                 # measures expected R by UTC hour from the trades themselves and `hour_prior`
                 # turns it into the bounded allocator prior `pf_allocator` already looks for --
                 # the desk's sharpest measured miss (a +0.164R hour at t=+12.9 holding 0.04% of
                 # heat beside a -0.032R hour holding 8.53%). `alpha_periodic_table` is the
                 # mechanism x axis white-space map, whose empty cells are research targets.
                 # In this order because hour_prior reads the artifact hour_surface writes; all
                 # three are pure readers -- no network, no terminal -- and none conditions
                 # capital.
                 "hour_surface", "hour_prior", "alpha_periodic_table"):
        try:
            mod = __import__(name)
            if hasattr(mod, "run"):
                out = mod.run()
            elif hasattr(mod, "write"):
                out = mod.write()
            else:
                out = {"rc": mod.main()}
            if name == "live_manifest":
                v = mod.verify()
                dlog(f"live manifest: chain ok={v.get('ok')} entries={v.get('entries')}")
            elif isinstance(out, dict):
                dlog(f"{name}: " + ", ".join(f"{k}={out[k]}" for k in
                                             ("n_uncovered", "n_hibernated", "bottleneck")
                                             if k in out))
        except Exception as exc:
            dlog(f"{name} FAILED (non-fatal): {type(exc).__name__}: {exc}")


def _research_memory() -> None:
    """THE TYPED RESEARCH MEMORY, rebuilt from the artifacts the feedback step just refreshed.

    Its own STEP, not a trailing try/except (2026-09-08). It sat at the tail of
    `_state_research_feedback` inside a bare except that logged one line and moved on, and
    measured on this tree its output directory `desks/mt5/data/memory` had never been created:
    the deepening worker's prompt carried doctrine and lessons but no graveyard or certificate
    retrieval, and nothing said so. As a named step its failure is recorded in the chain and the
    stamp like any other, so "never ran" and "ran and failed" stop reading identically.
    Idempotent -- a re-run adds nothing.
    """
    from libs.research.memory import build_from_artifacts
    m = build_from_artifacts()
    if not isinstance(m, dict):
        raise RuntimeError(f"build_from_artifacts returned {type(m).__name__}, not a report")
    failed = {k: v for k, v in (m.get("inputs") or {}).items()
              if isinstance(v, str) and v.startswith("FAILED")}
    dlog(f"research memory: added={m.get('added')} seen={m.get('seen')} "
         f"inputs={m.get('inputs')}")
    if failed and len(failed) == len(m.get("inputs") or {}):
        raise RuntimeError(f"every memory input failed: {failed}")


def _futures_curves() -> None:
    """Accrue real contract curves so roll/calendar hypotheses stop remaining prose-blocked."""
    import fetch_futures_curves

    rc = fetch_futures_curves.main([])
    if rc not in (0, 2):
        raise RuntimeError(f"fetch_futures_curves returned {rc}")


def _curve_strategies() -> None:
    """Test causal HP/trend/contrarian descendants immediately after refreshing curves."""
    import curve_strategy_screen

    curve_strategy_screen.main()


def _conservation() -> None:
    """Fast-filter/full-gauntlet conservation ledger (read-only reconciliation).

    The multiplicity denominator owed to every gate is the FULL grid. This step
    reconciles the hunt reports against the signal gate and the gauntlet so a
    shrinking denominator -- the silent way a filter weakens the gates downstream
    of it -- is visible the same day instead of at the next external audit.
    """
    import conservation_ledger
    rc = conservation_ledger.main()
    if rc != 0:
        raise RuntimeError(f"conservation_ledger returned {rc}")


def _export_aurum() -> None:
    """Re-export the findings Aurum's absorption channel reads.

    ABSORPTION WAS A ONE-SHOT SCRIPT AND THEREFORE IDLE BY DEFAULT. Aurum's
    step_absorb runs daily and reads inbox/quant_findings.jsonl; nothing on
    this side wrote it until export_aurum_findings.py existed, and a script
    that only runs when a human remembers is the same defect one step later --
    the channel reports "0 new findings" and that is indistinguishable from
    this desk having learned nothing.

    Runs LAST, after shadow and the promoter, so any finding derived from
    today's forward evidence is exported the same day it is produced rather
    than a cycle behind. The exporter appends and content-hashes, and Aurum's
    Absorber dedups by claim, so a repeat run is a no-op rather than a
    duplicate -- which is what makes it safe to run unconditionally, every
    day, forever.
    """
    import export_aurum_findings
    rc = export_aurum_findings.main()
    # rc 2 means NO SWEEP ARTEFACTS, which is a real state and not a failure of
    # this step: reports/ is gitignored and lives on whichever host ran the
    # hunts. Raising on it would make the whole cycle report FAILED every day
    # on a clone that legitimately has no reports.
    if rc not in (0, 2):
        raise RuntimeError(f"export_aurum_findings returned {rc}")


def _module_rent() -> None:
    """WHAT EVERY COMPONENT IS WORTH, from the ledgers the steps above have just refreshed.

    ModuleRent = E[log W] with it minus E[log W] without it. It NAMES a component whose rent is
    negative; a person retires it. A gate that failed the build on a rent verdict would make the
    ledger unwritable, which is how a measurement stops being taken. `libs.ops.module_rent` is
    not a `research/` module, so it gets its own step rather than a name in the feedback tuple.
    """
    from libs.ops import module_rent
    out = module_rent.run(BASE.parent.parent)
    named = list((out or {}).get("retire") or {})
    dlog(f"module rent: {len((out or {}).get('modules') or {})} component(s) priced"
         + (f"; NAMED for retirement: {', '.join(named[:6])}" if named else ""))


def _module_rent_research() -> None:
    """Every research module pays rent in measured downstream research (M22); report only."""
    import module_rent
    rc = module_rent.main(["--budget-s", "240"])
    if rc != 0:
        raise RuntimeError(f"module_rent returned {rc}")


def _build_allocator() -> None:
    """The daily build allocator ranks machinery improvements by expected orthogonal yield
    over build + maintenance + complexity, files non-replacing subsystems as LAB (M22)."""
    import build_allocator
    rc = build_allocator.main(["--top", "20"])
    if rc != 0:
        raise RuntimeError(f"build_allocator returned {rc}")


def _simplifier() -> None:
    """Weekly architecture consolidation (Sundays): overlaps, unifiable helpers, duplicate
    registries, services, dead machinery -- proposed, never applied (M22)."""
    from datetime import UTC, datetime
    if datetime.now(tz=UTC).weekday() != 6:
        return
    import simplifier
    rc = simplifier.main(["--budget-s", "300"])
    if rc != 0:
        raise RuntimeError(f"simplifier returned {rc}")


def _research_gap_map() -> None:
    """The day opens with the map: every valid cell of the breadth grid in one state, the
    highest-value holes named (M21, principal 2026-09-17)."""
    import research_gap_map
    rc = research_gap_map.main(["--budget-s", "300"])
    if rc != 0:
        raise RuntimeError(f"research_gap_map returned {rc}")


def _daily_research_os() -> None:
    """The day closes with the one canonical loop: observe, diagnose, prioritise, allocate,
    run, measure, learn, and the release train row (M20, principal 2026-09-17)."""
    import daily_research_os
    rc = daily_research_os.main(["--once"])
    if rc != 0:
        raise RuntimeError(f"daily_research_os returned {rc}")


def _wiring_ceo() -> None:
    """Every build on a clock: the wiring hunter, daily (principal 2026-09-16)."""
    import wiring_ceo
    rc = wiring_ceo.main(["--apply"])
    if rc != 0:
        raise RuntimeError(f"wiring_ceo returned {rc}")


def _probation() -> None:
    """Exercise unwired-but-safe organs in rotation so 'built' becomes 'runs'."""
    import probation_runner
    rc = probation_runner.main(["--per-pass", "12"])
    if rc != 0:
        raise RuntimeError(f"probation_runner returned {rc}")


def _zentech() -> None:
    root = BASE.parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import build_zentech_state
    build_zentech_state.main()


def _six_event_trace() -> None:
    """Is the system real? The principal's six-event test (2026-09-30), re-derived from recorded
    artifacts: a source mined into a cell, a preregistered cell, a logged REJECT, a survivor
    forward-observed, a reconciled live fill, a decay retirement. Read-only; writes
    reports/six_event_trace.json for the CRO pass (STEP 4C) to route every non-PROVEN event."""
    from libs.ops import six_event_trace
    rc = six_event_trace.main([])
    if rc != 0:
        raise RuntimeError(f"six_event_trace returned {rc}")


#: Ceiling on the box identity check run by `_vector_families_check`. It measured 14-65 s on the
#: build containers; a run that hangs past this is UNMEASURED, never a verdict.
VECTOR_CHECK_TIMEOUT_S = 900


def _run_vector_check(script: Path, out: Path) -> int:
    """Run `scripts/check_vector_families.py` in its own interpreter (audit v1.3 should-fix 2).

    The check patches `mt5desk.families_vector` while it measures (engagement wrappers, the
    switch, the proving flag); a child process means none of that can outlive it in the cycle.
    The repo's convention for daily legs (`_capacity_watch`): `sys.executable`, cwd `BASE`, a
    timeout. Not `-I`: that also drops user site-packages, and a box whose pandas lives there
    would read UNMEASURED forever. Raises `subprocess.TimeoutExpired` / `OSError` to the caller.
    """
    import subprocess
    r = subprocess.run([sys.executable, str(script), "--out", str(out), "--quiet"],
                       cwd=str(BASE), capture_output=True, text=True,
                       timeout=VECTOR_CHECK_TIMEOUT_S, check=False)
    tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
    dlog(f"vector_families_check: child rc={r.returncode} {tail[0][:300] if tail else ''}")
    return int(r.returncode)


def _vector_families_check() -> None:
    """DRIFT MONITOR AND FAIL-CLOSED SWITCH for the judge's speed path (`MT5_VECTOR_FAMILIES`).

    `mt5desk.families_vector` makes the costliest families fast and must return the original
    loops' Signal lists exactly -- on the live gateway's signal path too -- under whatever pandas
    and numpy this box has today. `scripts/check_vector_families.py` re-proves that here, daily,
    on real parquets, in a SUBPROCESS with a timeout, READ-ONLY apart from its report
    reports/VECTOR_FAMILIES_CHECK.json (versions, the switch's mode, per-family engagement).

    FAIL CLOSED (v1.4): the verdict drives `families_vector.MARKER`
    (data/VECTOR_FAMILIES_MISMATCH.json), which `families_vector.enabled()` reads:

        MISMATCH    marker written with the evidence -> every process takes the original loops
        IDENTICAL   marker removed                   -> the fast path is back
        UNMEASURED  marker left exactly as it was (a crash, a timeout, a stale or unreadable
                    report, no parquets: no measurement either way)

    A MISMATCH is only ever read from a report this run wrote (`generated_at` after the start);
    the child's rc alone is not trusted, because 1 is also Python's code for an uncaught raise.

    Still a SHADOW LEG: it never fails the cycle. IDENTICAL is quiet; anything else is a loud log
    line and a `vector_families_drift` event on the event bus.
    """
    from mt5desk import families_vector
    script = BASE / "scripts" / "check_vector_families.py"
    out = BASE / "reports" / "VECTOR_FAMILIES_CHECK.json"
    verdict, rc, detail, doc = "UNMEASURED", 2, "", {}
    started = datetime.now(UTC)
    try:
        # Imported for its path and REPORT only (importing patches nothing; `run()` does, in
        # the child). The import is also the edge the component registry reads as this clock.
        import check_vector_families
        script = Path(check_vector_families.__file__).resolve()
        out = check_vector_families.REPORT
        rc = _run_vector_check(script, out)
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            made = datetime.fromisoformat(str(doc.get("generated_at")))
            if made < started:
                raise ValueError(f"stale report (generated_at {made.isoformat()})")
            verdict = str(doc.get("verdict") or verdict)
            detail = "; ".join(str(x) for x in (doc.get("unmeasured_because") or []))
            if doc.get("mismatches"):
                detail = f"{len(doc['mismatches'])} mismatch(es); " + detail
        except (OSError, ValueError, TypeError) as exc:
            verdict, doc = "UNMEASURED", {}
            detail = f"report unusable: {type(exc).__name__}: {exc}"
    except Exception as exc:  # a crash or timeout in the monitor is a loud event, never a failure
        verdict, rc, detail = "UNMEASURED", 2, f"check did not finish: {type(exc).__name__}: {exc}"
    if verdict not in ("IDENTICAL", "MISMATCH"):
        verdict = "UNMEASURED"
    marker = "unchanged"
    try:
        if verdict == "MISMATCH":
            families_vector.write_mismatch_marker({
                "written_at": datetime.now(UTC).isoformat(), "verdict": verdict, "rc": rc,
                "report": str(out), "generated_at": doc.get("generated_at"),
                "host": doc.get("host"), "python": doc.get("python"),
                "pandas": doc.get("pandas"), "numpy": doc.get("numpy"),
                "cases": doc.get("cases"), "signals": doc.get("signals"),
                "mismatches": (doc.get("mismatches") or [])[:50],
                "cleared_by": "the next IDENTICAL daily_cycle:vector_families_check"})
            marker = "written"
        elif verdict == "IDENTICAL":
            marker = "cleared" if families_vector.clear_mismatch_marker() else "absent"
    except OSError as exc:
        marker = f"marker update failed: {type(exc).__name__}: {exc}"
    if verdict == "IDENTICAL" and not marker.startswith("marker update failed"):
        dlog(f"vector_families_check: IDENTICAL (marker {marker})")
        return
    dlog(f"vector_families_check: !!! {verdict} (rc={rc}) -- {detail} -- marker {marker} -- "
         + ("the fast families are FAILED CLOSED on this box until an IDENTICAL check"
            if verdict == "MISMATCH" else "fail-closed state left as it was"))
    try:
        from libs.ops import events
        events.emit("vector_families_drift", verdict=verdict, rc=rc, detail=detail[:500],
                    report=str(out), marker=marker)
    except Exception as exc:  # the event bus being down must not fail the cycle either
        dlog(f"vector_families_check: event emit failed: {type(exc).__name__}: {exc}")


#: ORDER IS LOAD-BEARING. The promoter reads the state shadow has just written, so running it
#: first would decide today on yesterday's evidence. Markout runs last-but-one and
#: unconditionally: it reads the live ledger, so it reports on the armed book whether or not
#: shadow could reach a terminal. The Aurum export runs after all of them, so it can carry
#: anything today's cycle produced.
def _control_room_module(name: str) -> object:
    """Each control-room organ by an explicit import, so the component registry sees this step
    as the clock that fires it (a name passed to `__import__` is invisible to it)."""
    if name == "control_room":
        import control_room as mod
    elif name == "regime_allocation_contract":
        import regime_allocation_contract as mod
    elif name == "control_room_mechanisms":
        import control_room_mechanisms as mod
    elif name == "bench_bridge":
        import bench_bridge as mod
    elif name == "practitioner_processes":
        import practitioner_processes as mod
    else:
        raise ModuleNotFoundError(name)
    return mod


def _control_room() -> None:
    """THE LIVE CONTROL ROOM (2026-09-30): regime now, its admission contract, the bench bridge.

    Five artifacts, each fenced so one failure costs only itself:
      control_room               reports/CONTROL_ROOM.json -- every traded instrument's
                                 vol / trend-range / liquidity state and the live sleeves in it
      regime_allocation_contract reports/REGIME_ALLOCATION_CONTRACT.json -- walk-forward, the live
                                 solver with and without the per-instrument regime kernel; the
                                 allocator consumes the kernel only on GAIN. Re-run weekly: 65
                                 monthly re-solves do not change inside a week.
      control_room_mechanisms    reports/CONTROL_ROOM_MECHANISMS.json -- the reverse-engineered
                                 regime-first gap and index/VIX divergence screens
      bench_bridge               reports/BENCH_BRIDGE.json -- certified -> forward -> live ->
                                 funded, scored by dE[log W], missed growth listed first
      practitioner_processes     reports/PRACTITIONER_PROCESSES.json -- each cited practitioner's
                                 whole loop, stage by stage, and its bottleneck (runs last: it
                                 reads the three artifacts above)
      operator digest            reports/OPERATOR_DIGEST.md -- the one page the operator reads
                                 (scripts/context.py; never writes under context/, which is code)
    Sizes nothing; publishes.
    """
    import runpy
    import time as _t
    failed = []
    contract = BASE / "reports" / "REGIME_ALLOCATION_CONTRACT.json"
    jobs = [("control_room", []), ("control_room_mechanisms", []), ("bench_bridge", []),
            ("practitioner_processes", [])]
    if not contract.exists() or _t.time() - contract.stat().st_mtime > 7 * 86400:
        jobs.insert(1, ("regime_allocation_contract", ["--worlds", "256", "--rows", "384"]))
    for name, args in jobs:
        try:
            rc = _control_room_module(name).main(args)  # type: ignore[attr-defined]
            dlog(f"{name}: rc={rc}")
        except Exception as exc:
            failed.append(name)
            dlog(f"{name} FAILED (non-fatal): {type(exc).__name__}: {exc}")
    try:
        ctx = runpy.run_path(str(BASE.parent.parent / "scripts" / "context.py"))
        ctx["digest"](20, BASE / "reports" / "OPERATOR_DIGEST.md")
        dlog("operator digest written")
    except Exception as exc:
        failed.append("operator_digest")
        dlog(f"operator digest FAILED (non-fatal): {type(exc).__name__}: {exc}")
    if len(failed) == len(jobs) + 1:
        raise RuntimeError(f"every control-room artifact failed: {failed}")


STEPS = (("weekly_hunt_refresh", _weekly_hunt_refresh),
         ("research_gap_map", _research_gap_map),
         ("refresh_bars", _refresh_bars), ("deepen_bars", _deepen_bars),
         ("cost_fields", _cost_fields),
         ("factor_residual", _factor_residual), ("research_bandit", _research_bandit),
         ("world_miners", _world_miners), ("proposers", _proposers),
         ("futures_curves", _futures_curves), ("curve_strategies", _curve_strategies),
         ("state_admission", _state_admission),
         ("reconcile", _reconcile), ("scalp_gauntlet", _scalp_gauntlet),
         ("shadow", _shadow), ("qquant_shadow", _qquant_shadow),
         ("execution", _execution), ("recertify", _recertify),
         ("promoter", _promote), ("markout", _markout),
         ("portfolio", _portfolio), ("control_room", _control_room), ("decay", _decay),
         ("state_research_feedback", _state_research_feedback),
         ("research_memory", _research_memory),
         ("module_rent", _module_rent), ("zentech", _zentech), ("conservation", _conservation),
         ("wiring_ceo", _wiring_ceo), ("probation", _probation),
         ("module_rent_research", _module_rent_research), ("build_allocator", _build_allocator),
         ("simplifier", _simplifier), ("capacity_watch", _capacity_watch),
         ("six_event_trace", _six_event_trace),
         ("vector_families_check", _vector_families_check),
         ("export_aurum", _export_aurum), ("daily_research_os", _daily_research_os))

#: THIS PASS'S DEADLINE (2026-10-29): seconds from the start of `main`, and where the number came
#: from. MT5-Daily was terminated at its Task Scheduler ExecutionTimeLimit (0x41306) mid-chain, so
#: the chain now learns the limit it runs under and stops STARTING work it cannot finish inside
#: it. Unstamped steps resume on the next pass (the hourly `daily` leg) exactly as before; a
#: proposer that does not fit is deferred to the front of the next pass. None = no deadline known,
#: which is the old behaviour.
_DEADLINE: dict = {"t0": None, "seconds": None, "basis": "not started"}
#: Room left under the hourly `daily` leg's kill (DAILY_CYCLE_HOURLY_BUDGET_SEC in hourly_cycle).
HOURLY_DEADLINE_MARGIN_S = 60.0
#: Room left under MT5-Daily's own ExecutionTimeLimit: 5% of it, never under fifteen minutes.
TASK_DEADLINE_MARGIN_FLOOR_S = 900.0
TASK_DEADLINE_MARGIN_FRACTION = 0.05
#: The scheduled task whose limit a plan-less pass runs under. Its XML lives on the box only:
#: desks/mt5/ops/box_tasks.manifest declares MT5-Daily with installer="NONE".
DAILY_TASK_NAME = "MT5-Daily"
_ISO_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def parse_iso_duration(text: str) -> float | None:
    """`PT72H` -> 259200.0. None for an empty, unparseable or zero (= unlimited) duration."""
    m = _ISO_DURATION.match(str(text or "").strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, se = (float(g) if g else 0.0 for g in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + se
    return total if total > 0 else None


def _decode_schtasks(raw: bytes) -> str:
    """schtasks /xml writes UTF-16 (with a BOM) on most Windows builds and the console code page
    on others; decoding it as text=True read every NUL-interleaved byte and matched nothing."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if len(raw) >= 4 and raw[1:2] == b"\x00" and raw[3:4] == b"\x00":
        return raw.decode("utf-16-le", "replace")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", "replace")
    return raw.decode("utf-8", "replace")


def _task_limit_s(task: str = DAILY_TASK_NAME, runner: Any = None) -> float | None:
    """The task's ExecutionTimeLimit, read from Task Scheduler (Windows only; read-only query).

    NEVER RAISES, AND NEVER SWALLOWS SILENTLY: any failure -- not only OSError/SubprocessError --
    is logged with its cause before the pass falls back to "no deadline known"."""
    if os.name != "nt" and runner is None:
        return None
    import subprocess
    run = runner or subprocess.run
    try:
        r = run(["schtasks", "/query", "/tn", task, "/xml"], capture_output=True,
                timeout=20, check=False)
        out = r.stdout or b""
        text = out if isinstance(out, str) else _decode_schtasks(out)
        m = re.search(r"<ExecutionTimeLimit>([^<]+)</ExecutionTimeLimit>", text)
        if not m:
            dlog(f"{task}: no ExecutionTimeLimit in schtasks output (rc={r.returncode}, "
                 f"{len(text)} chars) -- no deadline known")
            return None
        return parse_iso_duration(m.group(1))
    except Exception as exc:  # a deadline read must never crash the chain
        dlog(f"{task}: ExecutionTimeLimit unreadable ({type(exc).__name__}: {exc}) -- "
             f"no deadline known")
        return None


def _resolve_deadline() -> tuple[float | None, str]:
    env = str(os.environ.get("DAILY_CYCLE_DEADLINE_S", "") or "").strip()
    if env:
        with contextlib.suppress(ValueError):
            if float(env) > 0:
                return float(env), "DAILY_CYCLE_DEADLINE_S"
    if str(os.environ.get("HOURLY_PLAN", "") or "").strip():
        b = max(60.0, float(os.environ.get("DAILY_CYCLE_HOURLY_BUDGET_SEC", "900") or 900))
        return max(30.0, b - HOURLY_DEADLINE_MARGIN_S), "hourly daily leg budget"
    lim = _task_limit_s()
    if lim:
        margin = max(TASK_DEADLINE_MARGIN_FLOOR_S, TASK_DEADLINE_MARGIN_FRACTION * lim)
        return max(60.0, lim - margin), f"{DAILY_TASK_NAME} ExecutionTimeLimit {lim:.0f}s"
    return None, "no deadline known"


def _start_deadline() -> None:
    secs, basis = _resolve_deadline()
    _DEADLINE.update({"t0": time.monotonic(), "seconds": secs, "basis": basis})


def _time_left_s() -> float | None:
    """Seconds left before this pass's deadline; None when it has none."""
    if _DEADLINE.get("seconds") is None or _DEADLINE.get("t0") is None:
        return None
    return float(_DEADLINE["seconds"]) - (time.monotonic() - float(_DEADLINE["t0"]))


#: THE STEPS THAT MOVE AN EDGE TOWARD CAPITAL, ON THEIR OWN BUDGET (2026-10-29). MT5-Daily's log
#: read "36 step(s) of 37 never did" every day: research steps ahead of these (research_gap_map
#: 2h20m, refresh_bars 6h34m) spent the 10-hour limit and the task was killed before `shadow`.
#: The declared ORDER is unchanged; what changed is that a non-critical step only STARTS when,
#: by its last measured wall, it leaves room for every critical step still owed this pass. One
#: that does not fit is deferred (left unstamped) and the critical steps run now.
CRITICAL_STEPS: frozenset[str] = frozenset({
    "reconcile", "shadow", "qquant_shadow", "execution", "recertify", "promoter", "markout",
    "portfolio", "control_room", "decay", "build_allocator", "probation"})
#: Reserve for a critical step with no measured wall yet.
CRITICAL_DEFAULT_S = 300.0
#: Steps that bound THEMSELVES to what is left (or to a fixed budget): their expected wall is
#: this, not their history -- `proposers` adapts to `_research_left_s()` per proposer.
STEP_EXPECTED_CAP_S: dict[str, float] = {"proposers": 0.0, "refresh_bars": 1920.0,
                                          "deepen_bars": 1620.0}
#: Per-step memory across days: last outcome, last completed run, last wall. Read by the RED
#: check (`libs/ops/seat_clocks.red_daily_steps`): a step with no completed run in two days.
STEP_HISTORY_NAME = "daily_step_history.json"
_RESERVE: dict = {"s": 0.0}


def _research_left_s() -> float | None:
    """Time left for a NON-critical step: the deadline minus the critical steps' reserve."""
    left = _time_left_s()
    return None if left is None else left - float(_RESERVE.get("s") or 0.0)


def _expected_s(name: str, hist: dict) -> float:
    measured = float((hist.get(name) or {}).get("last_seconds") or 0.0)
    cap = STEP_EXPECTED_CAP_S.get(name)
    return measured if cap is None else min(measured, cap)


def critical_reserve_s(names: list[str], hist: dict) -> float:
    """Seconds the critical steps among `names` are expected to need."""
    return sum(_expected_s(n, hist) if n in hist else CRITICAL_DEFAULT_S
               for n in names if n in CRITICAL_STEPS)


def _record_step(hist: dict, name: str, out: dict) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    h = hist.setdefault(name, {})
    h.update({"last_at": now, "last_ok": bool(out.get("ok")),
              "last_seconds": out.get("seconds")})
    if out.get("ok"):
        h["last_ok_at"] = now
        h.pop("last_error", None)
    else:
        h["last_error"] = str(out.get("error") or "")[:300]
    _write_json(_step_history_path(), hist)


def _step_history_path() -> Path:
    """Beside the day's stamp (data/), so whatever relocates the stamp relocates this too."""
    return STAMP.with_name(STEP_HISTORY_NAME)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--proposer" in argv:
        # CHILD MODE (2026-10-29): one proposer, in this process, for `_run_proposer`. No lock,
        # no stamp: the parent chain owns both.
        i = argv.index("--proposer")
        name = argv[i + 1] if i + 1 < len(argv) else ""
        b = argv[argv.index("--budget-s") + 1] if "--budget-s" in argv else "none"
        return _proposer_child(name, None if b == "none" else float(b))
    _start_deadline()
    # ONE STEP ON ITS OWN CLOCK (2026-09-30). `markout` sits behind research steps this box has
    # measured at 9,056 s, under a 900 s hourly budget, so `reports/markout.json` stood at
    # 2026-09-08 with n_matched=0 while the live book kept filling. `--step NAME` runs that one
    # step now, through the same `run_step`, and leaves the day's stamp alone: the chain still
    # runs it in order, and an hourly leg can give a live-truth step the cadence it needs.
    if "--step" in argv:
        i = argv.index("--step")
        want = argv[i + 1] if i + 1 < len(argv) else ""
        fns = dict(STEPS)
        if want not in fns:
            dlog(f"--step {want!r}: no such step; known: {', '.join(fns)}")
            return 2
        return 0 if run_step(want, fns[want])["ok"] else 1
    force = "--force" in argv
    # ONE CHAIN AT A TIME (2026-10-22). Taken BEFORE the stamp is read, so a caller admitted after
    # another chain ends sees every step that chain stamped. See `_chain_lock`.
    lock = _chain_lock()
    if lock is None:
        # A HUNG HOLDER IS A FAILURE, NOT A NO-OP (v1.3, audit should-fix 2). Past
        # HOLDER_MAX_WAIT_S -- above a full ~9.4 h chain -- a holder that still has the lock is
        # hung, and standing down behind it as a verdict would mute this leg for as long as it
        # hangs. So the leg exits EXIT_HOLDER_HUNG, which `hourly_cycle` names as a failure.
        # v1.4: the age is the holder's LAST PROGRESS (refreshed after every step), not when it
        # took the lock, so a long chain that is still stepping is never called hung; and only a
        # sidecar whose process is measured ALIVE speaks for the holder -- a stale sidecar left
        # by a dead or reused pid (a failed sidecar write, or the gap before the first one) is
        # not evidence about the process that holds the lock now.
        # v1.5: "alive" also means the OS lists that pid as the lock's holder where it can say
        # (Linux /proc/locks), and a progress time from a fast clock is no age: then the age is
        # how long waiters have SEEN this holder hold the lock, by wall clock.
        if _holder_health() == "alive":
            age, basis = _holder_age_s(), "made no progress"
            if age is None:
                age, basis = _observed_hold_s(), "been seen holding the lock (times unusable)"
            if age is not None and age > HOLDER_MAX_WAIT_S:
                dlog(f"HOLDER HUNG: the chain-lock holder has {basis} for {age / 3600:.1f}h, past "
                     f"the {HOLDER_MAX_WAIT_S / 3600:g}h ceiling; standing down as a FAILURE")
                return EXIT_HOLDER_HUNG
        # A DISTINCT EXIT, NOT 0 (v1.1). `hourly_cycle` declares it a VERDICT exit of the `daily`
        # leg (VERDICT_EXITS) with a named no-op reason, so a pass that ran nothing is neither
        # recorded as a pass that ran the chain nor as a failure.
        print(f"WRITE_OR_EXPLAIN: NO_OP {STOOD_DOWN_REASON}", flush=True)
        return EXIT_STOOD_DOWN
    try:
        return _run_chain(force, lock)
    finally:
        lock.close()


#: The exit of a bounded caller that stood down behind another chain. 75 is EX_TEMPFAIL ("try
#: again later"), which is exactly what it means. Only `main` returns it: a STEP that raises
#: SystemExit(75) is caught by `run_step` and recorded as that step's failure (v1.2), so it can
#: never be mistaken for a stand-down.
EXIT_STOOD_DOWN = 75
#: The exit of a bounded caller that stood down behind a holder older than HOLDER_MAX_WAIT_S
#: (v1.3): a named FAILURE of the `daily` leg (hourly_cycle.NAMED_FAILURE_EXITS), never a verdict.
EXIT_HOLDER_HUNG = 76
#: The exit of a pass that ran nothing because the stamp could not be READ (v1.6): a named
#: failure, `exit_code=77:STAMP_UNREADABLE`, distinct from a failed step's 1.
EXIT_STAMP_UNREADABLE = 77
#: The same, once it has persisted past STAMP_UNREADABLE_MAX_PASSES consecutive passes: the
#: escalation, `exit_code=78:STAMP_UNREADABLE_PERSISTENT` (mirrors fail-to-build v1.5's ratchet).
EXIT_STAMP_UNREADABLE_PERSISTENT = 78
STAMP_UNREADABLE_MAX_PASSES = 3
STOOD_DOWN_REASON = ("another daily chain holds the lock; this bounded caller ran nothing -- the "
                     "holder runs the same steps and the next pass re-reads the stamp")


def _lock_path() -> Path:
    """The chain lock, beside the stamp it guards: `data/.job_locks/` is gitignored with every
    other per-machine lock, and deriving it from STAMP keeps a test's chain off the box's lock."""
    return STAMP.parent / ".job_locks" / "daily_cycle.lock"


def _owner_path() -> Path:
    """Who holds the lock: pid and process start time, written by the holder beside the lock.

    A SIDECAR, NOT THE LOCK FILE, because on Windows `msvcrt.locking` locks byte 0 of the lock
    file and a waiter cannot read it (audit nit, v1.1). The sidecar is what lets a waiter tell a
    HEALTHY holder (alive) from a dead or unknown one."""
    return _lock_path().with_name("daily_cycle.owner.json")


class LockUnavailable(OSError):
    """The lock FILE could not be opened or locked for a reason other than another holder: a
    permission, path or disk fault. It is never read as contention (v1.1): a caller that stood
    down on it would stand down on every pass, run nothing and leave no artifact."""


#: The errnos a non-blocking lock attempt raises when ANOTHER process holds the lock: flock
#: gives EWOULDBLOCK/EAGAIN, msvcrt.locking gives EACCES or EDEADLOCK. Anything else is a fault.
_HELD_ERRNOS = frozenset(e for e in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES,
                                     getattr(errno, "EDEADLOCK", errno.EDEADLK), errno.EDEADLK))


def _try_lock(path: Path) -> IO[str] | None:
    """Non-blocking OS lock on `path`: the open handle, or None while another process holds it.
    Raises LockUnavailable when the file itself cannot be opened or locked. The kernel releases
    the lock when the holder dies, so a killed chain never leaves a stale lock."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "a+", encoding="utf-8")  # noqa: SIM115 -- held for the whole chain
    except OSError as exc:
        raise LockUnavailable(f"cannot open {path}: {type(exc).__name__}: {exc}") from exc
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fh.close()
        if exc.errno in _HELD_ERRNOS:
            return None
        raise LockUnavailable(f"cannot lock {path}: {type(exc).__name__}: {exc}") from exc
    return fh


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` through a temp file and `os.replace`, so a reader sees the old
    file or the new one and never a torn one (v1.2, audit should-fix 2). On Windows `os.replace`
    fails with PermissionError while another process has the target open for reading; that is
    transient, so it is retried briefly before the error is raised."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            with contextlib.suppress(OSError):
                os.fsync(fh.fileno())
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(REPLACE_RETRY_S)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


REPLACE_RETRIES = 20
REPLACE_RETRY_S = 0.05


def _process_start(pid: int) -> float | None:
    try:
        import psutil
        return float(psutil.Process(pid).create_time())
    except Exception:
        return None


def _holder_health() -> str:
    """"alive", "dead" or "unmeasured" for the process the owner sidecar names.

    alive       the named pid exists AND started when the sidecar says it did (pid reuse cannot
                pass for the holder);
    dead        the sidecar is readable and its process is gone or is another process;
    unmeasured  no readable sidecar, no usable `create_time` in it (v1.3: a null start time
                cannot rule out pid reuse, so a live pid alone is never "alive"), psutil
                cannot answer, or -- where the OS says who holds the lock (v1.5) -- the named
                live process is NOT the lock's holder: a stale sidecar naming some other live
                process says nothing about the holder. Unmeasured is never read as alive.
    """
    try:
        doc = json.loads(_owner_path().read_text(encoding="utf-8"))
        pid, started = int(doc["pid"]), doc.get("create_time")
    except (OSError, ValueError, KeyError, TypeError):
        return "unmeasured"
    try:
        import psutil
    except ImportError:
        return "unmeasured"
    try:
        proc = psutil.Process(pid)
        if not proc.is_running():
            return "dead"
        if started is None:
            return "unmeasured"
        if abs(float(proc.create_time()) - float(started)) > 1.0:
            return "dead"
        holders = _lock_holder_pids()
        if holders is not None and pid not in holders:
            return "unmeasured"
        return "alive"
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchProcess", "ZombieProcess"):
            return "dead"
        return "unmeasured"


def _lock_holder_pids() -> set[int] | None:
    """The pids the OS reports as holding the chain lock, or None where it cannot say.

    Linux only, from /proc/locks (FLOCK rows on the lock file's device and inode; blocked
    waiters, "->" rows, are skipped). Elsewhere -- the Windows box, where msvcrt byte locks are
    not listed -- None, and the sidecar's pid plus create_time is the whole identity check."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        st = os.stat(_lock_path())
        want = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
        rows = Path("/proc/locks").read_text(encoding="ascii", errors="replace").splitlines()
    except OSError:
        return None
    pids: set[int] = set()
    for row in rows:
        f = row.split()
        if len(f) < 6 or f[1] == "->" or f[1] != "FLOCK":
            continue
        if f[5] == want:
            with contextlib.suppress(ValueError):
                pids.add(int(f[4]))
    return pids


def _parse_at(value: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    return at.replace(tzinfo=UTC) if at.tzinfo is None else at


#: How far ahead of this machine's clock a sidecar time may be before it is a clock error.
CLOCK_SKEW_S = 300.0


def _holder_age_s() -> float | None:
    """Seconds since the holder last made PROGRESS, from the owner sidecar: its `last_progress`
    heartbeat (refreshed by `_write_stamp` after every step, v1.4), else `at` (when it took the
    lock), whichever is later. None when neither can be read.

    A time more than CLOCK_SKEW_S AHEAD of now was written on a fast clock and is not an age
    (v1.5): read as one it would be "fresh" forever and mute a later hang. It is dropped, and
    with nothing left the age is None -- unmeasured -- so `_observed_hold_s` takes over."""
    try:
        doc = json.loads(_owner_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    now = datetime.now(UTC)
    stamps = [t for t in (_parse_at(doc.get("at")), _parse_at(doc.get("last_progress")))
              if t is not None and (t - now).total_seconds() <= CLOCK_SKEW_S]
    if not stamps:
        return None
    return (now - max(stamps)).total_seconds()


def _seen_path() -> Path:
    return _lock_path().with_name("daily_cycle.seen.json")


def _observed_hold_s() -> float | None:
    """How long the CURRENT holder has been seen holding the lock by the callers that stood down
    behind it, by wall clock (v1.5). The first caller to see a holder (pid + create_time from the
    sidecar) records `first_seen`; later callers age from it. A new holder, or a `first_seen`
    beyond the clock, restarts it. None when the holder cannot be identified or nothing can be
    written. This is the fallback when the holder's own times are unusable (in the future), so a
    hang after a clock jump still surfaces once the lock has been held past the ceiling."""
    try:
        side = json.loads(_owner_path().read_text(encoding="utf-8"))
        ident = [int(side["pid"]), side.get("create_time")]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    now = datetime.now(UTC)
    try:
        text = _seen_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    except OSError:
        # UNREADABLE IS NOT ABSENT (v1.6 nit): replacing it would reset `first_seen` on every
        # pass and the fallback could never reach the ceiling. Keep it; unmeasured this pass.
        return None
    try:
        seen = json.loads(text) if text else {}
        first = _parse_at(seen.get("first_seen")) if seen.get("holder") == ident else None
    except (ValueError, AttributeError):
        first = None
    if first is None or (first - now).total_seconds() > CLOCK_SKEW_S:
        try:
            _atomic_write(_seen_path(), json.dumps({
                "holder": ident, "first_seen": now.isoformat(timespec="seconds")}))
        except OSError:
            return None
        return 0.0
    return (now - first).total_seconds()


#: How long a caller with no deadline waits for a holder whose health it cannot measure (no
#: sidecar, no psutil). The bounded caller (the hourly `daily` leg) is killed at
#: DAILY_CYCLE_HOURLY_BUDGET_SEC, 900 s by default, so this outlasts it twice over.
UNBOUNDED_WAIT_S = 1800.0
#: The absolute ceiling on waiting for a holder measured ALIVE. A chain runs ~9.4 h (MT5-Daily,
#: 2026-10-21), so this is above one full chain; past it a hung-but-alive holder no longer
#: blocks the day, and the run proceeds unlocked, recorded as such in the stamp.
HOLDER_MAX_WAIT_S = 16 * 3600.0
LOCK_POLL_S = 15.0


class ChainLock:
    """This process's standing with the chain lock: `held`, `contended` or `unavailable`.

    `held` means one chain. The other two run UNLOCKED, and every stamp write records it
    (`chain_lock` and `unlocked_steps`, v1.2 should-fix 4), so a reader of the stamp -- not only
    of the log -- can see that a day's steps ran without the guarantee."""

    def __init__(self) -> None:
        self.handle: IO[str] | None = None
        self.state = "contended"
        self.error = ""
        self.waited_s = 0.0
        self.unlocked_steps: list[str] = []
        self._started: float | None = None
        self._at = ""

    @property
    def held(self) -> bool:
        return self.handle is not None

    def try_acquire(self) -> bool:
        """One non-blocking attempt; on success write the owner sidecar."""
        if self.handle is not None:
            return True
        try:
            fh = _try_lock(_lock_path())
        except LockUnavailable as exc:
            if self.state != "unavailable":
                dlog(f"chain lock UNAVAILABLE ({exc}); running without it, recorded in the stamp")
            self.state, self.error = "unavailable", str(exc)
            return False
        if fh is None:
            if self.state != "unavailable":
                self.state = "contended"
            return False
        self.handle, self.state, self.error = fh, "held", ""
        self._started = _process_start(os.getpid())
        self._at = datetime.now(UTC).isoformat(timespec="seconds")
        self._write_owner()
        return True

    def _write_owner(self, last_progress: str | None = None) -> None:
        doc: dict[str, object] = {"pid": os.getpid(), "create_time": self._started,
                                  "at": self._at}
        if last_progress:
            doc["last_progress"] = last_progress
        with contextlib.suppress(OSError):
            _atomic_write(_owner_path(), json.dumps(doc))

    def heartbeat(self) -> None:
        """Record progress in the owner sidecar (v1.4): a waiter ages the holder from here, so a
        chain that is still finishing steps is never read as hung however long it runs."""
        if self.handle is not None:
            self._write_owner(datetime.now(UTC).isoformat(timespec="seconds"))

    def wait(self, *, ceiling_s: float) -> bool:
        """Wait while the lock is held by a HEALTHY holder; True once it is ours.

        Stops waiting (False) when the lock file is faulty, when the holder is dead or
        unmeasured and UNBOUNDED_WAIT_S has passed, or at `ceiling_s` whatever the holder's
        health. A holder that dies releases the lock in the kernel, so the next poll takes it."""
        while not self.try_acquire():
            if self.state == "unavailable":
                return False
            health = _holder_health()
            if self.waited_s >= ceiling_s:
                dlog(f"chain lock still held after {self.waited_s:.0f}s (holder {health}); "
                     f"running without it, recorded in the stamp")
                return False
            if health != "alive" and self.waited_s >= UNBOUNDED_WAIT_S:
                dlog(f"chain lock still held after {self.waited_s:.0f}s and the holder is "
                     f"{health}; running without it, recorded in the stamp")
                return False
            time.sleep(LOCK_POLL_S)
            self.waited_s += LOCK_POLL_S
        if self.waited_s:
            dlog(f"chain lock acquired after {self.waited_s:.0f}s")
        return True

    def record(self) -> dict:
        rec: dict[str, object] = {"state": self.state, "pid": os.getpid()}
        if self.error:
            rec["error"] = self.error[:300]
        if self.unlocked_steps:
            rec["unlocked_steps"] = list(self.unlocked_steps)
        return rec

    def close(self) -> None:
        if self.handle is not None:
            with contextlib.suppress(OSError):
                _owner_path().unlink()
            with contextlib.suppress(OSError):
                self.handle.close()
            self.handle = None


def _chain_lock() -> ChainLock | None:
    """Admit this process to the chain, or say why it stands down. None means stand down.

    WHAT TWO CHAINS AT ONCE COST, read from the schedule. `MT5-Daily` runs this chain at 23:50
    box time with no deadline, and it runs for hours (9.4 h observed 2026-10-21): seventeen
    proposers on 300-3,600 s budgets each, then the rest. Meanwhile the `forward` department
    resident runs the hourly `daily` leg on every pass, which starts this same file under a 900 s
    kill. Nothing stopped the two overlapping, so each such pass:
      * re-ran, from its beginning, the very step `MT5-Daily` was executing (a step is stamped
        only when it ends), then was killed before it could stamp it -- 900 s of a core spent to
        produce nothing that survives; and
      * after 00:00 UTC started the NEW day's chain from step one while `MT5-Daily` was still
        finishing the old one -- and every step `MT5-Daily` completed rewrote the stamp with the
        OLD date, so the next pass saw the new day as unstarted and began it again from the top.
    One chain at a time removes both. No step is skipped and none runs less often: the chain that
    holds the lock runs every step it would have run, and a step already stamped today is still
    never repeated.

    WHO WAITS AND WHO LEAVES. A caller that runs under a cycle plan (`HOURLY_PLAN` is set -- the
    hourly leg, killed at its budget) stands down at once. A caller with no plan (the `MT5-Daily`
    task, or a hand run) has no deadline and WAITS: for as long as the holder is measured ALIVE
    (up to HOLDER_MAX_WAIT_S), or UNBOUNDED_WAIT_S when its health cannot be measured. It then
    re-reads the stamp, so a short hourly run that happened to hold the lock at 23:50 can never
    cost the day its long steps. If it must run unlocked, it waits again BETWEEN steps whenever a
    healthy holder appears (v1.2 should-fix 1), so it never runs the step a live holder is on.

    A FAULTY LOCK FILE IS NOT A HOLDER. If the file cannot be opened or locked for any reason
    other than contention, every caller runs, unlocked, and the stamp records it.
    """
    lock = ChainLock()
    if lock.try_acquire() or lock.state == "unavailable":
        return lock
    if str(os.environ.get("HOURLY_PLAN", "") or "").strip():
        dlog(f"STOOD_DOWN: {STOOD_DOWN_REASON} (holder {_holder_health()})")
        return None
    dlog(f"another daily chain holds the lock (holder {_holder_health()}); waiting for it, then "
         f"re-reading the stamp")
    lock.wait(ceiling_s=HOLDER_MAX_WAIT_S)
    return lock


def _read_stamp() -> tuple[dict, str]:
    """(doc, state). state is one of:

    ok          parsed to a dict;
    absent      no file;
    unreadable  the READ failed (any OSError but FileNotFoundError: a permission error, a Windows
                sharing violation from a scanner or a reader). The bytes on disk may be a valid,
                finished stamp -- it is "don't know", and is never moved aside or replaced
                (v1.5, audit of f18726a56: v1.4 read this as unparseable and quarantined a VALID
                stamp, pruning a real quarantine copy and restarting the day from step one);
    torn        read, but not JSON or not a dict (ValueError / non-dict) -- the only state that
                can be corruption.
    Unlike `_load_stamp`, which reads all of these as {}, a writer must tell them apart."""
    try:
        text = STAMP.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, "absent"
    except OSError:
        return {}, "unreadable"
    try:
        doc = json.loads(text)
    except ValueError:
        return {}, "torn"
    return (doc, "ok") if isinstance(doc, dict) else ({}, "torn")


#: Re-reads of a stamp that read UNREADABLE or TORN before anything acts on it: one pass of
#: these is what `_write_stamp` and the quarantine both require (v1.5).
STAMP_REREADS = 2
STAMP_REREAD_S = 0.1


def _read_stamp_settled() -> tuple[dict, str]:
    """`_read_stamp`, re-read up to STAMP_REREADS times while it is unreadable or torn."""
    doc, state = _read_stamp()
    for _ in range(STAMP_REREADS):
        if state not in ("unreadable", "torn"):
            break
        time.sleep(STAMP_REREAD_S)
        doc, state = _read_stamp()
    return doc, state


def _utc_today() -> str:
    return datetime.now(UTC).date().isoformat()


def _write_stamp(today: str, steps: dict[str, dict], lock: ChainLock | None = None) -> bool:
    """Write today's stamp, merged with whatever is on disk NOW. True when written.

    THREE RULES ON THE DATE (v1.1 + v1.2 must-fix):
      * a stamp dated AFTER the current UTC date is a CLOCK ERROR -- a run on a misset clock
        wrote it. It is overwritten, and the correction is recorded in `clock_corrections`; it
        never blocks a run (v1.1 refused it, so every corrected pass re-ran the whole chain and
        stamped nothing: the 2026-09-13 no-resume outage, again);
      * a stamp for a LATER day that is not in the future (this chain began before 00:00 UTC
        and is still running) wins: this write is refused, so last_run never moves backwards;
      * a stamp for the SAME day is merged step by step; an older or absent one is replaced.
    NEVER OVER A FILE IT CANNOT READ OR PARSE (v1.2 should-fix 2, v1.5). Writes are atomic, so a
    torn read cannot come from this module; an unreadable or torn stamp is re-read
    (`_read_stamp_settled`), then left alone and logged, because reading it as {} and replacing
    it is how a finished chain's steps were erased.
    """
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")
    if lock is not None:
        # THE HEARTBEAT (v1.4, audit SF-A), before any refusal below: a held chain records that
        # it is progressing even when this particular stamp write is refused.
        lock.heartbeat()
    doc, state = _read_stamp_settled()
    if state == "unreadable":
        dlog(f"stamp NOT written: {STAMP.name} exists but cannot be READ; it is left as it is")
        return False
    if state == "torn":
        dlog(f"stamp NOT written: {STAMP.name} exists but cannot be parsed; it is left as it is")
        return False
    on_disk = str(doc.get("last_run") or "")
    corrections = list(doc.get("clock_corrections") or [])[-19:]
    if on_disk and on_disk > _utc_today():
        dlog(f"stamp records {on_disk}, AFTER today's UTC date {_utc_today()}: a clock error; "
             f"overwriting it")
        corrections.append({"from": on_disk, "to": today, "pid": os.getpid(),
                            "at": datetime.now(UTC).isoformat(timespec="seconds")})
        on_disk, doc = "", {k: v for k, v in doc.items() if k not in ("steps", "last_run")}
    elif on_disk > today:
        dlog(f"stamp NOT written: it already records {on_disk}, later than this chain's {today}; "
             f"last_run never moves backwards")
        return False
    merged = {**(doc.get("steps") or {}), **steps} if on_disk == today else dict(steps)
    new = {**doc, "last_run": today, "steps": merged}
    if corrections:
        new["clock_corrections"] = corrections
    new["last_progress"] = {"at": now_iso, "pid": os.getpid()}
    if lock is not None:
        new["chain_lock"] = lock.record()
    _atomic_write(STAMP, json.dumps(new, indent=2))
    return True


#: How many quarantined `.corrupt-<ts>` stamps are kept (v1.3): enough evidence to diagnose a
#: recurring corruption, bounded so a corruption loop cannot fill the disk.
CORRUPT_KEEP = 5


_CORRUPT_SEQ = re.compile(r"\.corrupt-(\d{6})-")


def _corrupt_copies() -> list[Path]:
    return list(STAMP.parent.glob(f"{STAMP.name}.corrupt-*"))


def _corrupt_seq(p: Path) -> int | None:
    m = _CORRUPT_SEQ.search(p.name)
    return int(m.group(1)) if m else None


def _next_corrupt_name() -> Path:
    """`<stamp>.corrupt-<seq>-<UTC ts>`. The SEQUENCE, not the clock, orders the copies (v1.5):
    under the held chain lock there is one writer, so seq is the true quarantine order whatever
    the clock said -- a clock set back or forward cannot reorder them."""
    seqs = [q for q in (_corrupt_seq(p) for p in _corrupt_copies()) if q is not None]
    return STAMP.with_name(f"{STAMP.name}.corrupt-{(max(seqs) + 1) if seqs else 1:06d}-"
                           f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}")


def _prune_corrupt(just_kept: Path) -> None:
    """Keep CORRUPT_KEEP quarantined stamps: `just_kept` always, plus the newest others.

    NEWEST BY SEQUENCE, NEVER BY THE CLOCK (v1.5, audit of f18726a56). v1.4 ordered by the UTC
    stamp in the name and sorted a name after `just_kept`'s as "future"; on a clock set BACK that
    pruned every correctly dated newer copy first and kept the old ones. Copies written since v1.5
    carry a sequence number and are ordered by it; legacy copies (no sequence) are older than any
    of them and are ordered among themselves by file mtime, then name. So a copy written on a
    fast clock is pruned in its turn and holds no slot forever.

    Called ONLY after `os.replace` moved a torn stamp aside (v1.5). Removes only these quarantine
    copies of the stamp -- declared in libs/ops/reference_freshness.DESTRUCTIVE_PATHS."""
    def age_key(p: Path) -> tuple[int, int, float, str]:
        seq = _corrupt_seq(p)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (0 if seq is None else 1, seq or 0, mtime, p.name)

    others = sorted((p for p in _corrupt_copies() if p != just_kept), key=age_key)
    for old in others[:max(0, len(others) - (CORRUPT_KEEP - 1))]:
        with contextlib.suppress(OSError):
            old.unlink()


def _unreadable_path() -> Path:
    return _lock_path().with_name("daily_cycle.unreadable.json")


def _unreadable_pass() -> int:
    """Count one more consecutive pass on which the stamp could not be read; the new count.

    A count file that exists but cannot be read or parsed is read as AT THE LIMIT, so the next
    unreadable pass escalates rather than restarting at 1 (fail-to-build v1.5, S1)."""
    try:
        prev = int(json.loads(_unreadable_path().read_text(encoding="utf-8"))["passes"])
    except FileNotFoundError:
        prev = 0
    except (OSError, ValueError, KeyError, TypeError):
        prev = STAMP_UNREADABLE_MAX_PASSES
    n = prev + 1
    with contextlib.suppress(OSError):
        _atomic_write(_unreadable_path(), json.dumps({
            "passes": n, "at": datetime.now(UTC).isoformat(timespec="seconds")}))
    return n


def _stamp_readable_again() -> None:
    with contextlib.suppress(FileNotFoundError, OSError):
        _unreadable_path().unlink()


def _run_chain(force: bool, lock: ChainLock | None = None) -> int:
    today = _utc_today()
    stamp, state = _read_stamp_settled()
    if state == "unreadable":
        # DON'T KNOW (v1.5). The file may be a valid stamp that names steps already run today; a
        # scanner or reader holding it open is the usual cause on Windows. It is never moved, and
        # no step runs on a guess -- running all of them would repeat finished hours of work, and
        # `_write_stamp` could record none of it. The pass fails by NAME (v1.6): 77, and 78 once
        # it has lasted past STAMP_UNREADABLE_MAX_PASSES passes in a row.
        n = _unreadable_pass()
        dlog(f"{STAMP.name} cannot be READ (after {STAMP_REREADS} re-reads); it is left as it is "
             f"and no step runs this pass ({n} consecutive)")
        if n > STAMP_UNREADABLE_MAX_PASSES:
            dlog(f"ESCALATED: {STAMP.name} has been unreadable for {n} consecutive passes, past "
                 f"{STAMP_UNREADABLE_MAX_PASSES}; the daily chain has not run since")
            print(f"STAMP_UNREADABLE_PERSISTENT: {n} consecutive passes", flush=True)
            return EXIT_STAMP_UNREADABLE_PERSISTENT
        print(f"STAMP_UNREADABLE: {n} consecutive pass(es)", flush=True)
        return EXIT_STAMP_UNREADABLE
    _stamp_readable_again()
    if state == "torn" and not (lock is not None and lock.held):
        # TORN AND NOT OURS TO MOVE (v1.6): without the lock another chain may be mid-write, and
        # running against {} would repeat every finished step while `_write_stamp` refuses to
        # record any of them -- each pass the whole chain again. Fail closed, like unreadable.
        dlog(f"{STAMP.name} could not be parsed and this chain does not hold the lock to move it "
             f"aside; no step runs this pass")
        return 1
    if state == "torn":
        # Under the lock nobody else writes the stamp, so a file that still does not parse after
        # the re-reads is corruption, not a torn read. It is moved aside as evidence -- never
        # deleted -- or no pass could ever stamp again and the chain would re-run from step one
        # every hour. The prune runs only once the move succeeded (v1.5).
        aside = _next_corrupt_name()
        try:
            os.replace(STAMP, aside)
        except OSError as exc:
            # FAIL CLOSED (v1.6, audit SF2, probe P1d): running every step against {} while the
            # torn file blocks every stamp write is the double-run loop, every pass.
            dlog(f"{STAMP.name} could not be parsed and could not be moved aside "
                 f"({type(exc).__name__}: {exc}); nothing was pruned and no step runs this pass")
            return 1
        else:
            dlog(f"{STAMP.name} could not be parsed; kept as {aside.name}, starting a new stamp")
            _prune_corrupt(aside)
    if str(stamp.get("last_run") or "") > today:
        dlog(f"stamp records {stamp.get('last_run')}, AFTER today's UTC date {today}: a clock "
             f"error; its steps are not trusted and the next write overwrites it")
        stamp = {}

    # THE DAY'S STAMP MAY NOT OUTRANK THE CHAIN (gap-fixer 2026-08-28). The stamp recorded THAT
    # the day ran, never WHAT ran, so a step added to STEPS after today's tick was suppressed
    # until midnight by a stamp the previous version of this file had written. MEASURED that day:
    # the box's stamp named six steps -- futures_curves, curve_strategies, shadow, promoter,
    # markout, export_aurum -- while HEAD's STEPS held fourteen. The eight newer ones had shipped
    # to the box (the drift fence read "all 50 match HEAD on both boxes") and still could not run,
    # so execution_quality.json sat 43.1h stale against a 36h limit with the PROMOTION GATE as its
    # consumer, decay_live.json 43.1h against 26h, and forward_reconcile.json 39.1h -- three reds
    # on the freshness fence and a readiness gate held at rung 0, all from a skip that was correct
    # about the date and wrong about the work.
    #
    # So the skip is now step-aware: a day already stamped runs exactly the steps the stamp does
    # not name, in their declared order, and merges the outcomes. This weakens nothing -- a step
    # that ALREADY ran today is still not re-run -- and it means any future extension of the chain
    # self-heals on the next hourly tick instead of waiting for a midnight that a stale stamp
    # would have poisoned again anyway.
    prior: dict[str, dict] = {}
    todo = STEPS
    if stamp.get("last_run") == today and not force:
        prior = dict(stamp.get("steps") or {})
        todo = tuple((n, f) for n, f in STEPS if n not in prior)
        if not todo:
            dlog(f"daily cycle already ran {today}; skip (--force to re-run)")
            return 0
        dlog(f"daily cycle already ran {today}, but {len(todo)} step(s) of {len(STEPS)} never "
             f"did: {', '.join(n for n, _ in todo)} -- running those now")
    else:
        dlog(f"daily cycle {today} starting")
    # THE STAMP IS WRITTEN AFTER EVERY STEP, NOT ONLY AT THE END (2026-09-16). This chain ran
    # under a 900 s hourly budget and a daily task that was terminated, and the stamp was only
    # written when the whole chain finished -- so a pass killed on step six started again at
    # step one the next hour, forever. Measured: last_run stuck at 2026-09-13 for three days
    # while every hour spent its full budget re-running the same first steps. Stamping each step
    # makes a killed pass RESUME: the next hour runs only what has not run today.
    results: dict[str, dict] = {}
    if _DEADLINE.get("seconds") is not None:
        dlog(f"pass deadline {float(_DEADLINE['seconds']):.0f}s ({_DEADLINE['basis']})")
    hist = _read_json(_step_history_path())
    deferred: list[str] = []
    for i, (name, fn) in enumerate(todo):
        left = _time_left_s()
        if left is not None and left <= 0:
            # PAST THE DEADLINE, START NOTHING (2026-10-29). Being terminated by the task limit
            # mid-step costs the step it was on AND reports the task FAILING (0x41306); stopping
            # here leaves every unstamped step for the next pass, which runs them in order.
            rest = [n for n, _ in todo[i:]]
            dlog(f"DEADLINE ({_DEADLINE['basis']}): {len(rest)} step(s) left for the next "
                 f"pass: {', '.join(rest)}")
            break
        _RESERVE["s"] = 0.0
        if left is not None and name not in CRITICAL_STEPS:
            reserve = critical_reserve_s([n for n, _ in todo[i + 1:]], hist)
            if left - _expected_s(name, hist) < reserve:
                dlog(f"{name}: DEFERRED -- its last wall {_expected_s(name, hist):.0f}s would "
                     f"leave under the {reserve:.0f}s the critical steps need of the "
                     f"{left:.0f}s left; it runs on a later pass")
                deferred.append(name)
                continue
            _RESERVE["s"] = reserve
        if lock is not None and not lock.held:
            # RUNNING UNLOCKED (v1.2 should-fix 1). Before every step: take the lock if it is
            # free; if a HEALTHY holder has it, wait for that holder rather than run the step it
            # may be on. Then never repeat a step the stamp on disk now names for today.
            lock.wait(ceiling_s=HOLDER_MAX_WAIT_S)
            if not force:
                now, _st = _read_stamp()
                if now.get("last_run") == today and name in (now.get("steps") or {}):
                    dlog(f"{name}: already stamped today by another chain; not repeated")
                    continue
            if not lock.held:
                lock.unlocked_steps.append(name)
        results[name] = run_step(name, fn)
        _record_step(hist, name, results[name])
        _write_stamp(today, {**prior, **results}, lock)

    # THE STAMP RECORDS THE ATTEMPT, NOT A SUCCESS. Marking the day done only on a clean run would
    # make a broken step retry every hour, and a step that fails at 09:00 because the terminal is
    # shut fails identically at 10:00 -- turning one honest failure into a log full of them. The
    # per-step outcome is kept alongside so the failure stays visible and `--force` is the explicit
    # way to try again. Merge, never replace: a catch-up pass must not erase the outcomes of the
    # steps that ran earlier today, or the next tick would read them as never-run and loop on them
    # forever (`_write_stamp` merges with the stamp as it stands on disk at this moment).
    _write_stamp(today, {**prior, **results}, lock)

    failed = [n for n, r in results.items() if not r["ok"]]
    if deferred:
        dlog(f"deferred to a later pass (critical steps first): {', '.join(deferred)}")
    dlog(f"daily cycle {today} done" + (f" -- FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
