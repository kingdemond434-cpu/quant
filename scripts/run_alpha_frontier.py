#!/usr/bin/env python3
"""Daily alpha-factory frontier, including the unified GPT practitioner mission output.

The network-facing hunters publish raw items; this organ deduplicates, measures and injects them
into research.  It does not pretend an unavailable transcript was read and never promotes an
external claim.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.alpha_frontier import (  # noqa: E402
    alpha_reproduction,
    crowding_hazard,
    edge_npv,
    family_reality_priors,
    mechanism_eligibility,
    mechanism_half_life,
    mechanism_transfer,
    multi_timescale_state,
    null_factory_calibration,
    online_strategy_population,
    practitioner_frontier,
    return_source_decomposition,
    strategy_dna,
    tail_complementarity,
    useful_disagreement,
    validation_evig,
)

OUT = ROOT / "data" / "intelligence" / "daily_alpha_frontier.json"


def _read(rel: str, default: Any) -> Any:
    try:
        return json.loads((ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _list(rel: str, key: str) -> list[dict[str, Any]]:
    value = _read(rel, {}).get(key, [])
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def build() -> dict[str, Any]:
    alpha_events = _list("data/alpha_events.json", "events")
    validation = _read("data/validation_queue.json", {})
    regime = _read("web/regime.json", {})
    population = _list("data/strategy_population.json", "strategies")
    crowding = _list("data/crowding_history.json", "history")
    nulls = _list("data/null_controls.json", "controls")
    reality = _list("data/family_reality_transitions.json", "transitions")
    reviews = _list("data/reviewer_history.json", "reviews")
    experiments = _list("data/experiment_history.json", "experiments")
    items = _list("data/intelligence/public_strategy_items.json", "items")
    transfers = _list("data/mechanism_transfer.json", "transfers")
    return_claims = _list("data/return_source_claims.json", "claims")
    ontology = _read("data/mechanism_board.json", {}).get("mechanisms", [])
    known = (
        [
            str(x.get("mechanism_id", x.get("id", ""))) if isinstance(x, dict) else str(x)
            for x in ontology
        ]
        if isinstance(ontology, list)
        else []
    )
    edges = _read("data/edge_history.json", {})
    tail = _read("data/tail_pairs.json", {})
    factory = {
        "alpha_reproduction": alpha_reproduction(alpha_events, window_days=30),
        "validation_evig": validation_evig(
            probability_changes_decision=float(validation.get("probability_changes_decision", 0.0)),
            economic_value_if_resolved=float(validation.get("economic_value_if_resolved", 0.0)),
            test_cost=float(validation.get("test_cost", 0.0)),
            delay_cost=float(validation.get("delay_cost", 0.0)),
        ),
        "mechanism_transfer": {
            "status": "MEASURED" if transfers else "UNMEASURED",
            "rows": [
                mechanism_transfer(
                    str(row.get("mechanism_id", "UNKNOWN")),
                    str(row.get("transfer_class", "UNIVERSAL")),
                    row.get("target", {}),
                    row.get("constraints", {}),
                )
                for row in transfers
            ],
        },
        "multi_timescale_state": multi_timescale_state(
            structural=regime.get("structural", {}),
            tactical=regime.get("tactical", {}),
            fast=regime.get("fast", {}),
            microstructure=regime.get("microstructure", {}),
            as_of=regime.get("as_of"),
        ),
        "return_source_decomposition": {
            "status": "MEASURED" if return_claims else "UNMEASURED",
            "rows": [
                return_source_decomposition(
                    total_return=float(row.get("total_return", 0.0)),
                    beta_return=float(row.get("beta_return", 0.0)),
                    leverage_multiplier=float(row.get("leverage_multiplier", 1.0)),
                    carry_return=float(row.get("carry_return", 0.0)),
                    concentration_return=float(row.get("concentration_return", 0.0)),
                    convexity_return=float(row.get("convexity_return", 0.0)),
                    external_flows=float(row.get("external_flows", 0.0)),
                )
                for row in return_claims
            ],
        },
        "mechanism_eligibility": mechanism_eligibility(
            regime.get("posterior", {}), _read("data/mechanism_conditional_economics.json", {})
        ),
        "mechanism_half_life": mechanism_half_life(edges.get("edge", []), edges.get("time", [])),
        "tail_complementarity": tail_complementarity(tail.get("left", []), tail.get("right", [])),
        "online_strategy_population": online_strategy_population(population),
        "crowding_observatory": crowding_hazard(crowding),
        "continuous_null_factory": null_factory_calibration(
            nulls,
            expected_false_positive_rate=float(
                _read("data/null_controls.json", {}).get("expected_rate", 0.01)
            ),
        ),
        "family_reality_priors": family_reality_priors(reality),
        "useful_disagreement": useful_disagreement(reviews),
        "strategy_dna": strategy_dna(experiments),
        "edge_npv": edge_npv(
            edge_per_period=float(edges.get("edge_per_period", 0.0)),
            capacity=float(edges.get("capacity", 0.0)),
            half_life_periods=float(edges.get("half_life_periods", 0.0)),
            implementation_periods=float(edges.get("implementation_periods", 0.0)),
            operating_cost_per_period=float(edges.get("operating_cost_per_period", 0.0)),
        ),
    }
    practitioner = practitioner_frontier(items, known)
    return {
        "watch_timestamp": datetime.now(tz=UTC).isoformat(),
        "authority": "EXTERNAL PRIOR / MEASUREMENT ONLY; ordinary validation remains mandatory",
        "factory": factory,
        "practitioner_frontier": practitioner,
        "high_priority_residuals": [
            name
            for name, value in factory.items()
            if isinstance(value, dict) and value.get("status") == "UNMEASURED"
        ],
    }


def main() -> int:
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    print(
        f"alpha-frontier: {len(report['practitioner_frontier']['new_mechanisms'])} new mechanisms; "
        f"{len(report['high_priority_residuals'])} unmeasured factory controls"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
