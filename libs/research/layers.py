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
    # prediction: turning information into a claim about returns
    "compile_candidates": "prediction", "merge_docket": "prediction", "search": "prediction",
    "sweep": "prediction", "backtest": "prediction", "external_gauntlet": "prediction",
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
    # timing: when a claim becomes a trade
    "enrol_clocks": "timing", "heal_clocks": "timing", "promoter": "timing",
    "rebalance_trigger": "timing",
    # sizing: how much
    "capacity": "sizing", "ensemble_optimizer": "sizing",
    # portfolio: how the book is composed
    "pf_allocator": "portfolio",
    # execution: how the order reaches the venue
    "execution_resolver": "execution", "execution_twin": "execution",
    # exit: how a position ends
    "exit_study": "exit",
    # meta
    "health": "meta", "issue_board": "meta", "publish_dashboard": "meta",
    "publish_state": "meta", "release_identity": "meta", "smoke_release": "meta",
    "burn_in": "meta", "maintain_miners": "meta", "reclaim_disk": "meta", "daily": "meta",
    "layer_census": "meta", "opportunity_cost": "meta", "acceptance": "meta",
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
