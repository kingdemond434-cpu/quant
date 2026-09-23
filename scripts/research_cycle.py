"""Institutional research-cycle state keeper -- maintains the 3 persistent state files.

Runs one audit pass and (re)writes, from REAL system state (never fabricated):
  * research_state.json     -- deployed truth, binding constraint, backlog, bottleneck ranking
  * engineering_backlog.json -- every engineering task, ROI-ranked, completed items auto-removed
  * alpha_pipeline.json      -- every alpha's lifecycle: stage, half-life, crowding, retire check

Engineering ROI = expected_impact_on_log_growth * p_survive_or_success / effort_hours. Items whose
`done_if` detector fires are marked done and drop out of the open backlog (institutional memory of
completed work is kept in research_state.completed). This is the compounding memory layer; it is
deterministic and honest -- it reports what the files on disk actually say.

    python scripts/research_cycle.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.self_improvement import forecast_calibration as fc

_WEB = Path("web")
_ROOT = Path(".")


def _load(p: Path, d: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d if d is not None else {}


def _register_row_closed(row_id: int) -> bool:
    """Has GAP_REGISTER row ``row_id`` reached a terminal status?

    A backlog item that mirrors a register row must never claim done while the row is still
    open. Those two systems disagreed for 8 days on the live connector -- the register said
    in-progress with six named blockers and a 07-31 deadline, while the backlog said completed,
    and the backlog is the one that produces `next_action` every morning. Unknown or unparseable
    reads as NOT closed: the failure that cost the time was a detector defaulting to done.
    """
    try:
        from libs.research.finding_registry import parse_register
        rows = parse_register((_ROOT / "docs/GAP_REGISTER.md").read_text("utf-8"))
    except (OSError, ImportError, ValueError):
        return False
    for r in rows:
        if r.row_id == row_id:
            return not r.is_open
    return False


def _live_path_wired() -> bool:
    """RETIRED 2026-09-05 (universe mandate): always False, and that is a measurement.

    This asked whether the crypto-exchange live path was WIRED -- guard exists, daily cycle calls
    it, guard drives the stage machine, connector and reconcile. `run_live_guard.py` and the
    `binance_live` connector it inspected were deleted with the retired book, so the honest answer
    is that no such path exists in this repo any more.

    It returns False rather than being deleted with its detector row, because the row is what
    keeps the engineering backlog's item OPEN. This detector's own history is the argument: a
    file-existence proxy marked it done on 2026-07-18 and went on marking it done for eight days
    while the connector had no production caller at all. Removing the row would repeat that in the
    worst way -- silently dropping the live-path question off the backlog entirely. The MT5 money
    path is under desks/mt5/ with its own gateway and arming state; wiring THIS detector at it is
    a decision for whoever owns that desk, not something a cleanup should assert.
    """
    return False


def _detectors() -> dict[str, bool]:
    """Honest 'is this task actually done?' checks against files on disk."""
    lb = (_ROOT / "libs" / "portfolio" / "live_book.py")
    lb_txt = lb.read_text("utf-8") if lb.exists() else ""
    health = _load(_WEB / "health.json")
    # archive health: the OI/LS/liq datasets must be fresh for the 40-day clock to be real
    ds = {x.get("name", ""): x for x in health.get("datasets", [])}
    arch_ok = all(ds.get(n, {}).get("status") in ("OK", "RECEIVING", "LISTENING")
                  for n in ds if any(k in n.lower() for k in ("interest", "long", "liquid")))
    # `exec_txt` was the source of scripts/run_cashcarry_executor.py, read UNGUARDED -- so once
    # that file was deleted this whole function raised FileNotFoundError and every caller of
    # `_detectors()` died with it. The six detectors that grepped it (trade_logging,
    # cashcarry_capacity_sizing, execution_maker_carry, hedge_reconcile,
    # reconcile_limit_fallback, and the combined perp/carry row that read run_live_combined.py)
    # all asked "does the retired executor contain this feature?" -- a question with no subject
    # now. They are removed rather than pinned False, because a False detector keeps its backlog
    # item OPEN and would put the crypto executor's features back on the desk's build agenda,
    # which is the one thing the mandate forbids.
    return {
        "honest_deployed_sharpe": "_MIN_SHARPE_DAYS" in lb_txt,
        "single_portfolio_object": (_ROOT / "libs/portfolio/live_book.py").exists(),
        "state_files_infra": True,                      # true whenever this script runs
        "watchdog_enabled": True,                        # enabled last cycle (task scheduler)
        "watchdog_run_logged_off": (_ROOT / "data" / ".watchdog_logged_off").exists(),
        "archive_integrity_ok": bool(ds) and arch_ok,
        "dynamic_leverage": (_ROOT / "libs/risk/dynamic_leverage.py").exists(),
        "bayesian_roi_calibration":
        (_ROOT / "libs/self_improvement/forecast_calibration.py").exists(),
        "growth_positive_risk_controls": (_ROOT / "libs/risk/risk_controls.py").exists(),
        "test_suite_ci": (_ROOT / "tests/test_hedge_and_risk.py").exists()
        and (_ROOT / "scripts/run_ci.py").exists(),
        "stress_harness": (_ROOT / "scripts/run_stress.py").exists(),
        "alpha_economics_gate": (_ROOT / "libs/research/alpha_economics.py").exists()
        and (_ROOT / "tests/test_alpha_economics.py").exists(),
        "root_cause_engine": (_ROOT / "libs/research/root_cause.py").exists()
        and (_ROOT / "tests/test_root_cause.py").exists(),
        "decision_ledger": (_ROOT / "data/decision_ledger.json").exists(),
        "data_registry": (_ROOT / "data/data_registry.json").exists(),
        "executive_kpis": (_ROOT / "data/executive_kpis.json").exists(),
        "black_swan_library": (_ROOT / "data/black_swan_library.json").exists(),
        "institutional_knowledge_base": (_ROOT / "docs/institutional_knowledge.md").exists(),
        "growth_audit_engine": (_ROOT / "scripts/run_growth_audit.py").exists(),
        "execution_tca_fill_log": (_ROOT / "web/tca.json").exists(),
        # `funding_decay_predictor` removed 2026-09-05 (universe mandate): the row it detected
        # asked whether the desk could predict the NEXT 8h PERP FUNDING print and exit the carry
        # on it. Funding prints are a crypto-exchange mechanic; an MT5/Fusion book pays a broker
        # swap on a daily rollover instead, and that financing leg has its own organ
        # (desks/mt5/research/carry_state.py, fenced by scripts/check_carry_state.py). Its
        # detector artifact web/funding_decay_backtest.json had no writer left either.
        # A FILE-EXISTENCE detector marked this done on 2026-07-18 and kept marking it done for
        # 8 days while the connector and the stage machine had no production caller at all --
        # measuring the proxy (a file on disk) instead of the thing the row names (a wired live
        # path). Now it asks whether the rails actually RUN: the guard must exist, be on the
        # daily cycle, and drive the stage machine.
        "live_connector_prebuild": _live_path_wired(),
        # `autodiscovery_crypto_throughput` removed 2026-09-05: it asked whether the
        # autodiscovery factory emitted CRYPTO candidates into the EV gate, and both the adapter
        # (libs/autodiscovery/crypto_adapter.py) and the mandate that wanted it are gone.
    }


# curated engineering backlog -- each competes on ROI. impact = share of lifetime-log-growth lever.
_ENG: list[dict[str, Any]] = [
    {"id": "archive_integrity_ok", "title": "Verify OI/LS/liq archives append daily (protect the",
     "impact": 0.60, "p": 0.85, "effort_h": 1.0,
     "why": "The binding constraint is calendar-time data. A silent archive failure wastes 40 da"},
    {"id": "watchdog_run_logged_off", "title": "Watchdog: run whether logged on (survive reboot-b",
     "impact": 0.45, "p": 0.90, "effort_h": 0.3,
     "why": "Survival of the data flywheel; a reboot before login currently stalls every clock."},
    {"id": "honest_deployed_sharpe", "title": "Gate deployed Sharpe to >=5d forward (stop the -92",
     "impact": 0.20, "p": 0.95, "effort_h": 0.5,
     "why": "Metric integrity -> better sizing decisions; a lying Sharpe is worse than a blank o"},
    {"id": "single_portfolio_object", "title": "One canonical LivePortfolio object (dashboard/tes",
     "impact": 0.25, "p": 0.90, "effort_h": 2.0,
     "why": "Kills duplicate portfolio maths; deployed Sharpe always = deployed capital."},
    {"id": "trade_logging", "title": "Real open/close trade log -> winrate + molded history",
     "impact": 0.15, "p": 0.95, "effort_h": 1.0,
     "why": "Institutional memory of every fill; winrate/history become real, not fabricated."},
    {"id": "state_files_infra", "title": "Persistent research_state / eng_backlog / alpha_pipeline",
     "impact": 0.30, "p": 0.90, "effort_h": 2.0,
     "why": "Compounding memory: remembers decisions, re-ranks ROI each cycle, avoids repeat wor"},
    {"id": "cashcarry_capacity_sizing", "title": "Size each carry to per-name funding depth (not",
     "impact": 0.40, "p": 0.65, "effort_h": 3.0,
     "why": "Higher net funding capture -> higher log-growth. GATED: only after forward cert (da"},
    {"id": "bayesian_roi_calibration", "title": "Bayesian calibration of ROI / alpha-survival for",
     "impact": 0.10, "p": 0.50, "effort_h": 4.0,
     "why": "Phase-9 meta-opt. LOW ROI now: no realised track record to calibrate against yet."},
    {"id": "dynamic_leverage", "title": "Dynamic leverage controller (endogenous cap, no fixed li",
     "impact": 0.50, "p": 0.85, "effort_h": 3.0,
     "why": "Leverage as continuously-optimized control -> growth-optimal sizing as edge proves."},
    {"id": "combined_perp_carry", "title": "Combine perp (paper) + cash-carry into molded (testnet",
     "impact": 0.20, "p": 0.90, "effort_h": 1.5,
     "why": "Decorrelated 2nd sleeve forward track; paper-marked, never risks the carry acct."},
    {"id": "execution_maker_carry", "title": "Maker-first execution on carry legs (exec alpha)",
     "impact": 0.35, "p": 0.90, "effort_h": 3.0,
     "why": "Cut taker-fee drag on the forward Sharpe that gates leverage; taker fallback."},
    {"id": "hedge_reconcile", "title": "Auto-reconcile hedge drift each rebalance (survival)",
     "impact": 0.55, "p": 0.90, "effort_h": 1.5,
     "why": "Delta-neutral integrity: cover orphan shorts + re-hedge unhedged carries."},
    {"id": "growth_positive_risk_controls", "title": "Ruin-boundary risk controls (growth+)",
     "impact": 0.50, "p": 0.90, "effort_h": 2.0,
     "why": "Cut the left tail (raises g) via pause/flatten sized at the ruin boundary."},
    {"id": "test_suite_ci", "title": "Hedge/risk invariant test suite + local CI gate",
     "impact": 0.45, "p": 0.95, "effort_h": 2.5,
     "why": "Mechanical correctness on survival logic; caught the _alloc concentration bug."},
    {"id": "stress_harness", "title": "Stress harness (proves controls are growth-positive)",
     "impact": 0.20, "p": 0.90, "effort_h": 1.5,
     "why": "Empirically shows over-levering flips +g to -g; validates the risk controls."},
    {"id": "stablecoin_flows_archiver", "title": "On-chain stablecoin exchange-flow archiver",
     "impact": 0.35, "p": 0.30, "effort_h": 4.0,
     "why": "Starts the only NEW orthogonal 40d clock available; keyless free on-chain data."},
    {"id": "alpha_economics_gate", "title": "Alpha Economics EV gate (score ideas pre-effort)",
     "impact": 0.55, "p": 0.80, "effort_h": 3.0,
     "why": "EV-rank ideas + meta-learned priors -> saves 100s of low-EV research hours."},
    {"id": "institutional_knowledge_base", "title": "Knowledge base + alpha map + failure taxonomy",
     "impact": 0.35, "p": 0.85, "effort_h": 2.0,
     "why": "Never re-learn a lesson; alpha map exposes missing branches; compounds over years."},
    {"id": "reconcile_limit_fallback", "title": "Reconcile market-first/limit-fallback (thin book)",
     "impact": 0.50, "p": 0.90, "effort_h": 1.5,
     "why": "Orphans on illiquid perps were stranded (-4131); now they clear -> less friction."},
    {"id": "root_cause_engine", "title": "Root Cause Engine (classify losses before reacting)",
     "impact": 0.50, "p": 0.85, "effort_h": 2.5,
     "why": "Expected variance -> do nothing; act only on evidenced execution/infra causes."},
    {"id": "decision_ledger", "title": "Decision ledger (pre-log decisions, review monthly)",
     "impact": 0.30, "p": 0.85, "effort_h": 1.0,
     "why": "Feedback loop on decision QUALITY, not just trading results; compounds."},
    {"id": "data_registry", "title": "Data registry (tiered sources, EV-gated integrations)",
     "impact": 0.30, "p": 0.85, "effort_h": 1.0,
     "why": "Info-per-dollar policy: free-first, quarterly verify, never integrate for free-ness."},
    {"id": "executive_kpis", "title": "Executive KPI scorecard (6 hats, monthly CEO review)",
     "impact": 0.25, "p": 0.85, "effort_h": 1.0,
     "why": "Accountability between hats; engineering hours flow to the weakest positive lever."},
    {"id": "black_swan_library", "title": "Black swan scenario library (pre-production replay)",
     "impact": 0.35, "p": 0.85, "effort_h": 1.0,
     "why": "FTX/LUNA/COVID/inversion scenarios cap SIZE so any single crisis is survivable."},
    {"id": "growth_audit_engine", "title": "Growth audit: under-utilized authorized size = defect",
     "impact": 0.40, "p": 0.90, "effort_h": 1.5,
     "why": "Anti-conservatism with teeth: idle capital / stalled ramps / promo latency."},
    {"id": "cross_venue_funding_study",
     "title": "Cross-venue funding arb study: Binance vs Hyperliquid spread persistence",
     "impact": 0.55, "p": 0.35, "effort_h": 3.0,
     "why": "Round-3 review + growth playbook: the carry edge's capacity ceiling is the "
            "top-10 Binance perps; Hyperliquid funding (205 matched perps, collector already "
            "accruing) diverges in MAGNITUDE from Binance while correlating in direction -- "
            "harvesting the venue with the richer print (or the spread itself) is a second "
            "capacity pool with different microstructure. STUDY FIRST from data on hand: "
            "spread persistence net of costs, half-life, capacity; EV-gate the sleeve before "
            "any venue integration (live execution there needs real capital + transfers = "
            "human gate). Detector: web/cross_venue_funding.json.",
     },
    {"id": "carry_crowding_monitor",
     "title": "Crowding monitor on the PRIMARY edge (funding compression early-warning)",
     "impact": 0.45, "p": 0.85, "effort_h": 2.5,
     "why": "Round-2 external review: the desk's most probable failure mode is SECULAR funding "
            "compression as carry crowds -- a slow grind with no discrete event, invisible to "
            "the regime gate and root-cause buckets. Build web/crowding.json: trailing 30/90d "
            "trend of top-20 funding level, aggregate OI growth (archive matures ~Aug 5), and "
            "basis compression; monthly governance reviews it; a sustained down-trend in "
            "harvestable funding = pre-registered decay evidence feeding the carry-decay "
            "contingency BEFORE the Sharpe degrades. Detector: web/crowding.json exists."},
    {"id": "live_connector_prebuild",
     "title": "Pre-build live connector + go-live runbook behind interlocks (phase-change de-risk)",
     "impact": 0.40, "p": 0.90, "effort_h": 4.0,
     "why": "2026-07-12: testnet->live is a PHASE CHANGE (external-review consensus). Build "
            "libs/execution/binance_live.py NOW mirroring the testnet connector (same interface; "
            "live base URLs; refuses to init unless data/secrets/binance_live.json exists AND "
            "data/LIVE_ENABLE flag file present AND VPS precondition marker set), plus a go-live "
            "runbook in docs/playbooks/. Unit-test the guard interlocks. Rushing real-money code "
            "on connection day is how phase changes go wrong; this makes go-live a config flip. "
            "Detector: the live path is WIRED -- scripts/run_live_guard.py exists, the daily "
            "cycle calls it, and it drives the connector + stage machine + naked-position "
            "reconcile. (Was 'binance_live.py exists', which read done for 8 days while nothing "
            "called either module.)"},
    # THE funding_decay_predictor ROW IS RETIRED, 2026-09-05 (universe mandate). It proposed
    # predicting the next 8h PERP FUNDING print from premium/OI/taker-flow and exiting the carry
    # when marginal expected funding fell below execution cost. Every input is crypto-exchange
    # native and the sleeve it defended is deleted. Retired rather than repointed: the MT5
    # financing question ("is the swap leg priced on the live book?") is a different question with
    # its own organ, and dressing a funding-print predictor in swap vocabulary would put a
    # pre-registration on a quantity this desk does not observe.
    {"id": "execution_tca_fill_log",
     "title": "Per-fill TCA log + funding-deadline-aware maker patience (execution edge P0)",
     "impact": 0.45, "p": 0.85, "effort_h": 3.0,
     "why": "Log decision-px vs fill-px, time-to-fill, maker/taker outcome per order -> "
            "web/tca.json; tune maker patience so legs FILL before the 8h funding snapshot "
            "(missing a funding event costs more than patient quoting). Target: exec cost "
            "< 15% of gross funding. PLUS edge-weighted routing (round-3 growth review): "
            "when expected_edge_bps > 2.5x taker_cost_bps, TAKE liquidity immediately -- "
            "queue-sitting through a fat funding spike saves 4bps of fees and loses 40bps "
            "of alpha; maker-first is for thin edges with time to wait."},
    {"id": "autodiscovery_crypto_throughput",
     "title": "Crypto adapter -> autodiscovery factory in the daily cycle (#1 tier-convergence)",
     "impact": 0.70, "p": 0.50, "effort_h": 6.0,
     "why": "Edge BREADTH is the #1 closable Tier-1/2 gap. 12-generator factory + orchestrator "
            "exist but are MarketSeries(MT5)-shaped; build libs/autodiscovery/crypto_adapter.py "
            "(lake bars -> MarketSeries), then orchestrator emits crypto candidates into the EV "
            "gate + gauntlet EVERY cycle -> industrialized hypothesis throughput."},
]


def _roi(item: dict[str, Any]) -> float:
    return round(item["impact"] * item["p"] / max(0.1, item["effort_h"]), 3)


def _build_engineering(done: dict[str, bool]) -> dict[str, Any]:
    items = []
    for it in _ENG:
        rec = {**it, "roi": _roi(it), "done": bool(done.get(it["id"], False))}
        items.append(rec)
    open_items = sorted((i for i in items if not i["done"]), key=lambda x: -x["roi"])
    done_items = [i["id"] for i in items if i["done"]]
    return {"generated": datetime.now(tz=UTC).isoformat(),
            "roi_formula": "impact * p_success / effort_hours",
            "open": open_items, "completed": done_items,
            "next_action": open_items[0] if open_items else None}


def _alpha_pipeline() -> dict[str, Any]:
    reg = _load(_WEB / "registry.json")
    disc = _load(_WEB / "discovery.json")
    pending = {p["sleeve"]: p for p in disc.get("pending", [])}
    rows = []
    for a in reg.get("alphas", []):
        name = a.get("name")
        p = pending.get(name)
        # honest lifecycle stage
        if a.get("survived"):
            stage = "validated-candidate"          # passed gates but not forward-certified
        elif p:
            stage = f"data-blocked ({p.get('have_days', '?')}/{p.get('needs_days', '?')}d)"
        else:
            stage = "rejected" if a.get("status", "").lower().startswith("rej") else "backtest"
        rows.append({
            "alpha": name, "category": a.get("category"),
            "expected_sharpe": a.get("expected_sharpe"), "gates": a.get("gates"),
            "survived": a.get("survived"), "stage": stage,
            # honest qualitative estimates (no fabricated numbers)
            "orthogonality": ("high" if a.get("category") in ("carry", "microstructure")
                              else "unknown"),
            "crowding_risk": "high" if a.get("category") == "carry" else "medium",
            "expected_half_life": "regime-dependent (funding-rich)" if a.get("category") == "carry"
            else "unknown-until-forward",
            "retire_check": ("KEEP: only deployed edge" if name == "cash_and_carry"
                             else "HOLD: data-blocked" if p else "REJECT: fails gates"
                             if not a.get("survived") else "WATCH"),
        })
    return {"generated": datetime.now(tz=UTC).isoformat(),
            "n_alphas": reg.get("n_alphas"), "n_survived": reg.get("n_survived"),
            "deployed": ["cash_and_carry"], "alphas": rows,
            "note": ("Every alpha carries a retire_check, not just a promote check. Data-blocked "
                     "edges accrue forward days before they can be validated -- calendar time, "
                     "not engineering, is the gate.")}


def _research_state(eng: dict[str, Any], done: dict[str, bool]) -> dict[str, Any]:
    port = _load(_WEB / "portfolio.json").get("deployed", {})
    disc = _load(_WEB / "discovery.json")
    clocks = [{"edge": p["sleeve"], "have_days": p.get("have_days"),
               "needs_days": p.get("needs_days")}
              for p in disc.get("pending", [])]
    bottlenecks = [
        {"rank": 1, "bottleneck": "calendar-time data accumulation",
         "evidence": clocks or "OI/LS/liq at 6/40d; cash-carry 2/90d; hyperliquid 1/250",
         "lever": "keep the flywheel alive + verify archives append; cannot be engineered away"},
        {"rank": 2, "bottleneck": "single deployed edge (concentration)",
         "evidence": f"{len(port.get('sleeves', []))} deployed sleeve(s)",
         "lever": "decorrelated survivors -- blocked on #1 (need forward data to validate)"},
        {"rank": 3, "bottleneck": "flywheel reliability (PC sleep / reboot)",
         "evidence": "watchdog enabled; run-logged-off pending",
         "lever": eng["next_action"]["id"] if eng.get("next_action") else "none"},
    ]
    # AUTO-RETIREMENT signal: sleeves whose marginal contribution to portfolio E[log wealth] is
    # negative are retire candidates (constitution: kill negative-contribution sleeves, reallocate).
    incr = _load(_WEB / "crypto_portfolio.json").get("incremental_sharpe", {})
    retire = sorted([{"sleeve": s, "marginal_sharpe": v} for s, v in incr.items() if v < 0],
                    key=lambda x: x["marginal_sharpe"])
    # 7-CYCLE architecture review cadence (blank-slate redesign question).
    log = _load(Path("data/cro_cycle_log.json"))
    n_cycles = len(log) if isinstance(log, list) else 0
    arch_review_due = n_cycles > 0 and n_cycles % 7 == 0
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "master_objective": "maximize expected lifetime geometric growth (log wealth), survival-c",
        "deployed": port,
        "binding_constraint": "calendar-time data accumulation (not engineering throughput)",
        "bottleneck_rankings": bottlenecks,
        "retirement_candidates": retire,
        "retirement_note": ("SIGNAL ONLY — marginal-Sharpe swings ~±0.15 between runs, so a single "
                            "negative sign is within noise. Retire only on PERSISTENT negative "
                            "contribution across runs, with promotion-grade rigor. No whipsaw."),
        "architecture_review_due": arch_review_due,
        "cycles_logged": n_cycles,
        "completed_this_cycle": eng["completed"],
        "engineering_backlog_top": [{"id": i["id"], "roi": i["roi"], "effort_h": i["effort_h"]}
                                    for i in eng["open"][:5]],
        "research_backlog": [{"edge": c["edge"],
                              "status": f"data-blocked {c['have_days']}/{c['needs_days']}d",
                              "info_value": "positive but not yet actionable"} for c in clocks],
        "decisions_log": [
            "REJECT ls_contrarian for deployment: Sharpe 10+ artifact, fails DSR (correct).",
            "PIVOT executed book to delta-neutral cash-and-carry; perp L/S -> shadow.",
            "DEFER new-hypothesis generation: lower marginal ROI than protecting the data clock.",
            "DEFER heavy external paper search: info value < top backlog item this cycle.",
        ],
    }


# Horizon for an engineering forecast: "this task's done_if detector fires within N days of the
# forecast being pre-registered". 30d spans several ROI-ranked cycles yet keeps the
# check_calibration OVERDUE fence meaningful inside a quarter.
_FORECAST_HORIZON_DAYS = 30


def _calibrate(done: dict[str, bool]) -> dict[str, Any]:
    """Pre-register engineering forecasts, grade them only when the outcome is KNOWN, report.

    CONTRACT (forecast_calibration._scoreable #1 / L1.29a): a probability is a forecast only if
    it is logged with a resolve_by BEFORE the outcome is known. The old loop here logged eng:*
    rows with no resolve_by and resolved them TRUE in the same pass -- 30 degenerate all-TRUE
    rows, graded a median 18ms after being logged, which inverted the measured bias (+0.176
    over-confident read as -0.146 under-confident) and fed kelly_leverage an inflated p
    (recommendation_ledger rec 3101). The estimator now excludes such rows; this writer must
    stop producing them. Therefore:

      * a task already done at first sight is NEVER logged -- observing state is an assertion,
        not a prediction;
      * an open task is pre-registered ONCE, with a resolve_by fixed at first assertion and
        never rolled forward (a rolling deadline can never go overdue, which would blind the
        check_calibration fence);
      * grading writes BOTH sides, so misses are counted: detector fires while the deadline is
        still ahead -> True; deadline passes with the task still open -> False. A completion
        first OBSERVED after the deadline also grades False -- we cannot verify it beat the
        clock, and defaulting to credit is the exact self-flattering failure this replaces;
      * one forecast per task, never re-registered after resolution: _scoreable dedups
        identical claims, so a re-ask would add rows without adding information.

    Legacy rows lacking a parseable resolve_by are left untouched (resolving one would mint
    another retrospective row); the estimator already excludes them.
    """
    now = datetime.now(tz=UTC)
    for it in _ENG:
        key = f"eng:{it['id']}"
        row = fc.get_forecast(key)
        if row is None:
            if not done.get(it["id"]):              # first sight while still OPEN: pre-register
                fc.log_forecast(
                    key, it["p"], "engineering",
                    resolve_by=(now + timedelta(days=_FORECAST_HORIZON_DAYS)).isoformat(),
                    claim=(f"eng task '{it['id']}' done_if detector fires within "
                           f"{_FORECAST_HORIZON_DAYS}d of {now.date().isoformat()}"))
            continue                                # already done + never forecast: assert only
        if row.get("resolved"):
            continue                                # scored history is immutable
        try:
            due = datetime.fromisoformat(str(row.get("resolve_by")))
            due = due if due.tzinfo else due.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            continue                                # legacy no-deadline row: inert, never graded
        if due < now:
            fc.resolve(key, outcome=False)          # horizon passed unverified -> forecast missed
        elif done.get(it["id"]):
            fc.resolve(key, outcome=True)           # detector fired inside the horizon
    rep = fc.report()
    (_WEB / "calibration.json").write_text(json.dumps(rep, indent=2), "utf-8")
    return rep


def main() -> None:
    done = _detectors()
    eng = _build_engineering(done)
    cal = _calibrate(done)
    (_ROOT / "engineering_backlog.json").write_text(json.dumps(eng, indent=2), "utf-8")
    (_ROOT / "alpha_pipeline.json").write_text(json.dumps(_alpha_pipeline(), indent=2), "utf-8")
    rs_obj = _research_state(eng, done)
    rs_obj["forecast_calibration"] = cal
    (_ROOT / "research_state.json").write_text(json.dumps(rs_obj, indent=2), "utf-8")
    nxt = eng.get("next_action") or {}
    print(f"research-cycle: completed={eng['completed']}")
    print(f"  calibration: {cal.get('status')} brier={cal.get('brier')} bias={cal.get('bias')}")
    print(f"  top-ROI task: {nxt.get('id')} (ROI {nxt.get('roi')}, {nxt.get('effort_h')}h)")
    print(f"  -> {nxt.get('why', '')}")


if __name__ == "__main__":
    main()
