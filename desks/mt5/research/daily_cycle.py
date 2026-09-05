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

import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

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
    try:
        fn()
        out = {"ok": True}
        dlog(f"{name}: ok")
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        dlog(f"{name}: FAILED -- {out['error']}")
        dlog(traceback.format_exc().rstrip())
    out["seconds"] = round((datetime.now(UTC) - started).total_seconds(), 1)
    return out


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
    m = compute(load_jsonl(data / "order_intents.jsonl"),
                load_jsonl(data / "live_ledger.jsonl"))
    for line in render(m).splitlines():
        dlog("  " + line)
    markout_path = BASE / "reports" / "markout.json"
    markout_path.parent.mkdir(parents=True, exist_ok=True)
    markout_path.write_text(json.dumps({
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "usable": m.usable, "n_matched": m.n_matched,
        "n_unfilled_intents": m.n_unfilled_intents,
        "n_unmatched_deals": m.n_unmatched_deals,
        "mean_slip_quote": m.mean_slip_quote, "mean_slip_r": m.mean_slip_r,
        "edge_share": m.edge_share, "why": m.why,
    }, indent=2), encoding="utf-8")


def _refresh_bars() -> None:
    """Extend every cached H1 parquet from the live terminal, before anything reads bars.

    NOTHING SCHEDULED THIS. `refresh_tail` globs the whole store, so its SCOPE was never the
    problem -- its output path was hardcoded to a third machine's home directory, so on the desk
    box it refreshed nothing and no task ran it. Measured 2026-08-27: of 295 parquets on that box
    only 49 had been written that day, 195 dated 08-26 and 51 dated 08-22, so the gauntlet was
    screening most of the universe on bars up to five days old.
    """
    import refresh_tail

    rc = refresh_tail.main()
    # rc=2 is "no terminal on this box", the honest answer everywhere but the desk box.
    if rc not in (0, 2):
        raise RuntimeError(f"refresh_tail returned {rc}")


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


def _proposers() -> None:
    """The proposer sweeps that hand the gauntlet cells it would never otherwise see.

    Each is a PROPOSER in the `factor_residual_engine` sense: it runs a family over the desk's
    bars, scores against cost, deflates by its own search, and donates survivors into the miner
    contract. None admits anything. Daily, because cadence is multiplicity. A failure in one
    must not cost the others their run, so each is fenced.
    """
    # THE BANDIT SETS THE BUDGETS. Each proposer belongs to a research direction; its time budget
    # is the base budget scaled by that direction's share (uniform = 1.0), clipped so no arm is
    # ever starved to zero -- the exploration floor is what keeps a cold arm alive.
    import inspect
    try:
        from libs.research.bandit import arm_weight
    except Exception:
        def arm_weight(source, kind=None):                        # type: ignore[misc]
            return 1.0
    for name in ("plumbing_miner", "transition_alpha", "weak_signal_compiler",
                 "fund_playbook", "microstructure_miner", "alpha_evolution",
                 "style_premia_sweep", "cross_asset_graph", "anomaly_factory",
                 "tail_alpha_search", "survivor_distiller", "factor_model_coevolution"):
        try:
            mod = __import__(name)
            kwargs = {}
            if "budget_s" in inspect.signature(mod.run).parameters:
                base = float(inspect.signature(mod.run).parameters["budget_s"].default or 1200.0)
                kwargs["budget_s"] = float(min(3600.0, max(300.0, base * arm_weight(name))))
            rep = mod.run(**kwargs)
            dlog(f"{name}: " + (f"{rep.get('tests_run', '?')} tests, "
                                 f"{rep.get('cells_proposed', rep.get('donated_rows', '?'))} "
                                 "proposed" + (f" (budget {kwargs['budget_s']:.0f}s)"
                                               if kwargs else "")
                                 if isinstance(rep, dict) else "ran"))
        except ModuleNotFoundError:
            dlog(f"{name}: not present on this tree")
        except Exception as exc:
            dlog(f"{name} FAILED (non-fatal): {type(exc).__name__}: {exc}")


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
                 "regime_coverage", "data_prospector", "resurrection", "research_productivity",
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
                 "live_manifest"):
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
    # THE TYPED RESEARCH MEMORY is rebuilt from the artifacts the steps above refreshed, so the
    # deepening worker's next prompt carries today's failures, survivors and methods (idempotent;
    # a re-run adds nothing).
    try:
        from libs.research.memory import build_from_artifacts
        m = build_from_artifacts()
        dlog(f"research memory: {m.get('added', m)}" if isinstance(m, dict)
             else "research memory built")
    except Exception as exc:
        dlog(f"research memory FAILED (non-fatal): {type(exc).__name__}: {exc}")


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


def _zentech() -> None:
    root = BASE.parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import build_zentech_state
    build_zentech_state.main()


#: ORDER IS LOAD-BEARING. The promoter reads the state shadow has just written, so running it
#: first would decide today on yesterday's evidence. Markout runs last-but-one and
#: unconditionally: it reads the live ledger, so it reports on the armed book whether or not
#: shadow could reach a terminal. The Aurum export runs after all of them, so it can carry
#: anything today's cycle produced.
STEPS = (("refresh_bars", _refresh_bars), ("cost_fields", _cost_fields),
         ("factor_residual", _factor_residual), ("research_bandit", _research_bandit),
         ("world_miners", _world_miners), ("proposers", _proposers),
         ("futures_curves", _futures_curves), ("curve_strategies", _curve_strategies),
         ("state_admission", _state_admission),
         ("reconcile", _reconcile), ("scalp_gauntlet", _scalp_gauntlet),
         ("shadow", _shadow), ("qquant_shadow", _qquant_shadow),
         ("execution", _execution), ("recertify", _recertify),
         ("promoter", _promote), ("markout", _markout),
         ("portfolio", _portfolio), ("decay", _decay),
         ("state_research_feedback", _state_research_feedback),
         ("module_rent", _module_rent), ("zentech", _zentech), ("conservation", _conservation),
         ("export_aurum", _export_aurum))

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    today = datetime.now(UTC).date().isoformat()
    stamp = _load_stamp()

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
    results = {name: run_step(name, fn) for name, fn in todo}

    # THE STAMP RECORDS THE ATTEMPT, NOT A SUCCESS. Marking the day done only on a clean run would
    # make a broken step retry every hour, and a step that fails at 09:00 because the terminal is
    # shut fails identically at 10:00 -- turning one honest failure into a log full of them. The
    # per-step outcome is kept alongside so the failure stays visible and `--force` is the explicit
    # way to try again.
    stamp["last_run"] = today
    # Merge, never replace: a catch-up pass must not erase the outcomes of the steps that ran
    # earlier today, or the next tick would read them as never-run and loop on them forever.
    stamp["steps"] = {**prior, **results}
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps(stamp, indent=2), encoding="utf-8")

    failed = [n for n, r in results.items() if not r["ok"]]
    dlog(f"daily cycle {today} done" + (f" -- FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
