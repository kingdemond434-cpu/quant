"""THE SEVEN LAYERS, DECLARED: which organ does information, prediction, timing, sizing,
portfolio, execution or exit -- and what each layer costs.

MEASURED 2026-09-08 (Tier-1 programme item G14): six of the seven layers have a dedicated,
scheduled engine, so the separation exists de facto -- but nowhere is it declared. A new leg
lands in `hourly_cycle.py` under whatever name its author chose and joins no layer, so nobody
can ask "how many trials did the TIMING layer run this week, and what did they cost?", and the
one layer with no engine at all (EXIT: the exit study runs, nothing sizes or times an exit from
it) is invisible precisely because the taxonomy it is missing from does not exist.

THE REGISTRY IS THE DECLARATION, and the test enforces it: every `_costed("name", ...)` leg in
the hourly and daily cycles must appear here. A leg nobody assigned a layer to fails the suite
-- the taxonomy stays complete by construction rather than by memory.

`census` joins the registry onto the compute ledger (libs/ops/compute_ledger.cost_by_run), so
per-layer hours, runs and failure rates are the ledger's numbers grouped, never re-measured.
The EXIT layer's census reads zero hours against one leg; that zero is the finding.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "layer_census.json"

LAYERS = ("information", "prediction", "timing", "sizing", "portfolio", "execution", "exit",
          "meta")

#: leg name -> layer. `meta` is the machine that runs the machine: health, publishing, the
#: compute ledger itself. It is a layer of the desk, not of a strategy, and is listed so its
#: cost is visible next to the seven it serves.
LEG_LAYER: dict[str, str] = {
    # information: what the desk knows before it predicts anything
    "mine": "information", "moat_miner": "information", "world_crawler": "information",
    "deep_forest": "information", "market_intel": "information", "record_tape": "information",
    "archive_tape": "information", "refresh_bars": "information",
    "timeframe_coverage": "information", "frontier": "information",
    "frontier_ontology": "information", "frontier_unknowns": "information",
    "frontier_implementer": "information", "frontier_report": "information",
    "state_vector": "information", "causal_graph": "information",
    "input_identity": "information",
    # FIFTEEN LEGS LANDED WITHOUT A LAYER AND THIS TEST HAD BEEN RED FOR IT (2026-09-10). Nine
    # of them were added on 2026-09-10 itself and mapped nowhere: exactly the failure the
    # registry exists to prevent, committed by the session that wrote the registry's own fence.
    # A leg with no layer is an hour of compute that `opportunity_cost` cannot attribute, so
    # "what did the desk NOT test this hour" silently omits it.
    "futures_lead_lag": "information", "tape_features": "information",
    # prediction: turning information into a claim about returns
    "compile_candidates": "prediction", "merge_docket": "prediction", "search": "prediction",
    "sweep": "prediction", "hunt12": "prediction",
    "backtest": "prediction", "external_gauntlet": "prediction",
    "deepen": "prediction", "experiment_design": "prediction",
    "experiment_cache": "prediction", "ml_layer": "prediction", "model_league": "prediction",
    "model_skill": "prediction", "forecast_contract": "prediction",
    "graveyard_model": "prediction", "counterfactual_world": "prediction",
    "edge_confidence": "prediction", "adversaries": "prediction",
    "recertify_canon": "prediction", "publish_survivors": "prediction",
    "miner_conversion": "prediction", "opportunity_gap": "prediction",
    "research_org": "prediction", "queue_compact": "prediction",
    "requeue_unrunnable": "prediction", "falsifier_run": "prediction",
    "opportunity_forecast": "prediction", "edge_reliability": "prediction",
    "edges_macro_fusion_sweep": "prediction", "alpha_breadth": "prediction",
    "alpha_periodic_table": "prediction", "regime_coverage": "prediction",
    "arena": "meta", "prosecutor": "meta", "scaling_laws": "meta", "dead_architecture": "meta",
    # timing: when a claim becomes a trade
    "enrol_clocks": "timing", "heal_clocks": "timing", "promoter": "timing",
    "rebalance_trigger": "timing", "entry_timing": "timing",
    # WHICH HOURS the desk has an edge in is a TIMING question, not a sizing one -- this leg
    # measures and allocates nothing, and stacking it on pf_allocator would shrink twice.
    "session_allocation": "timing",
    # Generating a mechanism's other-session and other-chart equivalents is asking WHEN it works,
    # which is a timing question even though the output is a research candidate.
    "session_chart_expansion": "timing",
    # Whether an artifact's own stamp advances is a MEASUREMENT property of the desk, not a
    # property of any strategy -- it belongs with the other self-measurement legs.
    "stamp_freshness": "information",
    # Why an order filled or did not is an EXECUTION measurement, and it is the binding stage.
    "fill_attribution": "execution",
    # What a sleeve pays to trade belongs with execution too: it is a cost, not a signal.
    "cost_to_edge": "execution",
    # Whether a data endpoint still serves what it claims is an INFORMATION property -- it decides
    # whether any input exists at all, before any signal is derived from it.
    "source_routes": "information",
    # Per-sleeve return paths are what a PORTFOLIO view is computed from -- n_eff, covariance,
    # joint drawdown. Not a signal and not an execution fact.
    "strategy_paths": "portfolio",
    # THE FOUR ACTIVATION LEGS (2026-09-14). All four organs existed and NOTHING ran them, which
    # is III.16 exactly: built is not a status. `weak_signals` and `residual_factors` mint claims
    # about returns, so they are prediction. `markout` asks what the desk's own fills cost it
    # after the fact -- execution. `exogenous_search` is undirected hunting for inputs nobody has
    # a story for, which is information, and is only affordable because the trial count is sealed.
    "weak_signals": "prediction",
    "residual_factors": "prediction",
    "markout": "execution",
    "exogenous_search": "information",
    # `stop_reverse` asks what the desk's own orders did to it at the venue -- execution.
    "stop_reverse": "execution",
    # `forward_reconcile` keeps the forward lane's roster true -- which clock may accrue
    # evidence and which is an orphan. That is portfolio bookkeeping, not prediction.
    "forward_reconcile": "portfolio",
    # AND FIVE LEGS WERE STILL UNMAPPED WHEN THOSE FOUR LANDED (2026-09-14). The registry's own
    # comment records fifteen of these in 2026-09-10 and the same drift had recurred, so the test
    # this file exists to satisfy was red before this session touched it. Mapped by what each
    # actually does rather than by its name: `refresh_regime` (costed as `regime_monitor`)
    # conditions on a latent state, which is prediction; `orthogonality` measures tail dependence
    # BETWEEN sleeves, which only the portfolio layer can act on; `lake_promote` asks what share
    # of stored intelligence survives a point-in-time question, which is information about the
    # desk's own inputs; `research_exchange_score` scores which external source converts, likewise;
    # `alpha_rl` searches sequentially against the allocator's marginals, which is prediction.
    "alpha_rl": "prediction",
    "regime_monitor": "prediction",
    "orthogonality": "portfolio",
    "lake_promote": "information",
    "research_exchange_score": "information",
    # sizing: how much
    "capacity": "sizing", "ensemble_optimizer": "sizing",
    # portfolio: how the book is composed
    "pf_allocator": "portfolio",
    # execution: how the order reaches the venue
    "execution_resolver": "execution", "execution_twin": "execution",
    # What the venue charges and where that number came from is execution arithmetic, not
    # research: these three decide what every backtest is billed at the fill.
    "fusion_cost": "execution", "cost_construction": "execution",
    "spread_provenance": "execution", "microstructure_census": "execution",
    # exit: how a position ends
    "exit_study": "exit",
    # meta
    "health": "meta", "issue_board": "meta", "publish_dashboard": "meta",
    "publish_state": "meta", "release_identity": "meta", "smoke_release": "meta",
    "burn_in": "meta", "maintain_miners": "meta", "reclaim_disk": "meta", "daily": "meta",
    "layer_census": "meta", "opportunity_cost": "meta", "acceptance": "meta",
    "wiring_audit": "meta", "queue_cycle": "meta", "time_joins": "meta", "brain_ab": "meta",
    "session_capital": "portfolio",
}

_LEG_RE = re.compile(r'_costed\("([^"]+)"')


def scheduled_legs(root: Path = ROOT) -> set[str]:
    """Every costed leg the two cycles declare, read from the source."""
    legs: set[str] = set()
    for name in ("hourly_cycle.py", "daily_cycle.py"):
        src = root / "desks" / "mt5" / "research" / name
        if src.exists():
            legs |= set(_LEG_RE.findall(src.read_text("utf-8")))
    return legs


def unassigned(root: Path = ROOT) -> list[str]:
    """Legs that run but belong to no layer. The test pins this to []."""
    return sorted(scheduled_legs(root) - set(LEG_LAYER))


def census(cost_by_run: dict[str, dict[str, Any]], root: Path = ROOT) -> dict[str, Any]:
    """Per-layer hours/runs/failures from the compute ledger's per-run aggregate."""
    by_layer: dict[str, dict[str, Any]] = {
        L: {"legs": sorted(k for k, v in LEG_LAYER.items() if v == L),
            "runs": 0, "hours": 0.0, "failures": 0, "costed_legs": []} for L in LAYERS}
    for run, c in cost_by_run.items():
        layer = LEG_LAYER.get(run)
        if layer is None:
            continue
        b = by_layer[layer]
        b["runs"] += int(c.get("runs") or 0)
        b["hours"] += float(c.get("hours") or 0.0)
        b["failures"] += int(c.get("failures") or 0)
        b["costed_legs"].append(run)
    for b in by_layer.values():
        b["hours"] = round(b["hours"], 4)
        b["failure_rate"] = round(b["failures"] / b["runs"], 4) if b["runs"] else None
        b["dark_legs"] = sorted(set(b["legs"]) - set(b["costed_legs"]))
        b["costed_legs"].sort()
    total_h = sum(b["hours"] for b in by_layer.values())
    for b in by_layer.values():
        b["share_of_hours"] = round(b["hours"] / total_h, 4) if total_h else None
    starved = [L for L in LAYERS[:-1] if by_layer[L]["hours"] == 0.0]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "layers": by_layer, "total_hours": round(total_h, 4),
        "unassigned_legs": unassigned(root),
        "starved_layers": starved,
        "why": ("a layer with declared legs and zero costed hours is either never scheduled or "
                "its cost is unrecorded; either way the desk spends nothing on it"),
    }


def main(argv: list[str] | None = None) -> int:
    from libs.ops.compute_ledger import cost_by_run
    doc = census(cost_by_run())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"layer census: {doc['total_hours']}h over {len(LEG_LAYER)} legs; starved "
          f"{doc['starved_layers'] or 'none'}; unassigned {doc['unassigned_legs'] or 'none'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
