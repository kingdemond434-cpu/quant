"""Publish the one dynamic research-conversion plan consumed by every reasoning controller.

This composes existing organs; it does not create another research factory.  Counts come from the
authoritative candidate store and downstream admission/forward artifacts.  The plan has no target
candidate or survivor count.  It points work at the weakest measured transition, preserves the
portfolio promotion rails, and uses the tracked 50/50 research prior until realised two-sided
economic value/cost evidence earns a bounded change.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.alpha_factory.research_budget import adaptive_portfolios  # noqa: E402
from libs.research.alpha_state import AlphaStateLedger, ORDER  # noqa: E402

DEFAULT_OUT = ROOT / "web/conversion_control.json"


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _count_rows(value: Any, *keys: str) -> int | None:
    if isinstance(value, list):
        return len(value)
    if not isinstance(value, dict):
        return None
    for key in keys:
        item = value.get(key)
        if isinstance(item, list):
            return len(item)
        if isinstance(item, int) and item >= 0:
            return item
    return None


def _candidate_counts(db_path: Path) -> tuple[int | None, int | None, int | None]:
    if not db_path.is_file():
        return None, None, None
    try:
        with sqlite3.connect(db_path) as db:
            tested = int(db.execute("SELECT COUNT(*) FROM research_candidates").fetchone()[0])
            screened = int(db.execute(
                "SELECT COUNT(*) FROM research_candidates WHERE survived = 1 "
                "AND status != 'archived'"
            ).fetchone()[0])
            durable = int(db.execute(
                "SELECT COUNT(*) FROM research_candidates WHERE survived = 1 "
                "AND status != 'archived' AND COALESCE(capacity_usd, 0) > 0 "
                "AND COALESCE(rejection_reason, '') NOT LIKE '%UNMEASURED:%' "
                "AND COALESCE(rejection_reason, '') NOT LIKE 'failed:%'"
            ).fetchone()[0])
            return tested, screened, durable
    except sqlite3.Error:
        return None, None, None


def _canonical_stages(path: Path) -> list[dict[str, Any]]:
    """Cumulative rung counts from one identity-preserving ledger only."""
    try:
        records = AlphaStateLedger(path).records.values()
    except ValueError:
        return [{"stage": state, "count": None, "source": str(path),
                 "status": "UNMEASURED: malformed canonical ledger"} for state in ORDER]
    rows: list[dict[str, Any]] = []
    for index, state in enumerate(ORDER):
        count = sum(
            1 for rec in records
            if rec.state in ORDER and ORDER.index(rec.state) >= index
        )
        rows.append({"stage": state, "count": count, "source": str(path),
                     "status": "MEASURED"})
    return rows


def weakest_transition(stages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Lowest measured adjacent conversion rate; unknown never masquerades as zero."""
    measured: list[dict[str, Any]] = []
    for upstream, downstream in pairwise(stages):
        a, b = upstream["count"], downstream["count"]
        if not isinstance(a, int) or not isinstance(b, int) or a <= 0:
            continue
        rate = min(1.0, b / a)
        measured.append({
            "from": upstream["stage"], "to": downstream["stage"],
            "upstream": a, "downstream": b, "conversion": rate,
            "stranded": max(0, a - b),
        })
    return min(measured, key=lambda row: (row["conversion"], -row["stranded"])) \
        if measured else None


def build(root: Path = ROOT) -> dict[str, Any]:
    tested, screen_valid, durable = _candidate_counts(root / "data/sor_crypto.sqlite")
    ledger_path = root / "data/alpha_state_ledger.jsonl"
    stages = _canonical_stages(ledger_path)
    legacy_inventory = {
        "candidate_store": {"tested": tested, "screen_survivors": screen_valid,
                            "fully_measured_survivors": durable,
                            "source": "data/sor_crypto.sqlite"},
        "portfolio_rows": _count_rows(_json(root / "data/portfolio_admission.json"),
                                      "admitted", "eligible", "rows"),
        "shadow_rows": _count_rows(_json(root / "data/paper_sleeve_queue.json"),
                                   "active", "sleeves", "rows"),
        "promotion_rows": _count_rows(_json(root / "data/promotion_queue.json"),
                                      "eligible", "capital_eligible", "promotions"),
        "rule": ("inventory only until joined by the same alpha_id through alpha_state_ledger; "
                 "never use unrelated counts as adjacent funnel stages"),
    }

    outcomes_doc = _json(root / "data/research_portfolio_outcomes.json")
    outcomes: dict[str, tuple[float, float]] = {}
    if isinstance(outcomes_doc, dict):
        for name in ("exploitation", "exploration"):
            row = outcomes_doc.get(name)
            if isinstance(row, dict):
                value, cost = row.get("validated_economic_value"), row.get("measured_cost")
                if isinstance(value, (int, float)) and isinstance(cost, (int, float)):
                    outcomes[name] = (float(value), float(cost))
    allocation = adaptive_portfolios(outcomes)
    bottleneck = weakest_transition(stages)

    return {
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "authority": "research work allocation only; no promotion, risk-limit or capital authority",
        "canonical_ladder": [row["stage"] for row in stages],
        "stages": stages,
        "legacy_inventory_not_conversion": legacy_inventory,
        "binding_transition": bottleneck,
        "research_portfolios": {
            "weights": allocation.weights,
            "evidence_used": allocation.evidence_used,
            "reason": allocation.reason,
            "policy": "ops/research_allocation_policy.json",
            "exploitation_work": (
                "convert the nearest-to-money measured backlog; repair/falsify near-survivors; "
                "mutate descendants only when a real survivor exists; improve portfolio fit, "
                "execution and forward evidence without weakening any bar"
            ),
            "exploration_work": (
                "search uncovered mechanisms, data, participants, markets, distant domains and "
                "search methods; preregister and test; feed all results into the same ladder"
            ),
        },
        "controller_rule": (
            "Every controller and miner reads this artifact fresh, works its assigned portfolio "
            "and binding transition, writes entity-level outputs to durable shared state, and "
            "recomputes next cycle. Never optimize raw candidates/tests/commits or use fixed "
            "throughput targets. Unknown is not zero. Preserve all validation and survival rails."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out or (root / DEFAULT_OUT.relative_to(ROOT))
    report = build(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    tmp.replace(out)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
