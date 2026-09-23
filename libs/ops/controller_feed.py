"""Make the research controller's allocation the thing that actually fills the work queue.

WHY THIS EXISTS (2026-09-04)

`run_research_loop` computes an EXPLORE/REFINE split, a UCB over branches, an action (EXPLOIT,
EXPLORE, FALSIFY, MUTATE, CROSSOVER, ACQUIRE) and a per-family trial allocation -- 22 families,
`calendar_month: 65`, `cot_positioning: 29`, `cross_asset_residual: 2` -- and wrote it to JSON.
The forever supervisor then filled its queue from `lake_campaign_specs(lake, families=ARGS)`, a
static list typed on the command line.

So the desk had a controller and a fleet of workers and NO WIRE BETWEEN THEM. Every posterior
update, every fertility measurement, every UCB bound steered a report rather than a single unit of
compute. This is the gap RD-Agent(Q) closes with its feedback stage and bandit scheduler, and it
is the difference between frontier machinery and frontier machinery that does something.

WEIGHTED, NOT FILTERED. The allocation is a budget, not a whitelist: a family granted 65 trials
and one granted 2 must not appear equally often in the queue, or the allocation has been reduced
to set membership and the ranking is discarded. Families are repeated in proportion.

STALENESS IS REFUSED, LOUDLY. A controller artifact older than MAX_AGE_H is a posterior from
before the last few hundred experiments, and steering compute by it is worse than not steering:
it spends the fleet on a ranking the evidence has already moved past. The caller falls back to its
static list and the reason is returned, never swallowed -- absence is not permission.

THE EXPLORATION FLOOR SURVIVES CONTRACTION. `MIN_SHARE_FAMILIES` of the queue always goes to the
lowest-allocation families the controller still lists. A pure-exploit queue is how a desk spends a
week confirming what it already believes, and the allocator has been wrong before: seven families
were zeroed on the strength of a validator later found defective in four ways.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "data" / "research_loop.json"

#: Older than this and the allocation describes a desk that no longer exists.
MAX_AGE_H = 6.0
#: Share of the weighted queue reserved for the controller's LOWEST-ranked families.
MIN_SHARE_FAMILIES = 0.15
#: A family may not take more than this share of one queue fill, however confident the controller
#: is. Concentration is what n_eff punishes, and a bandit at full tilt will happily produce it.
MAX_SHARE_ONE_FAMILY = 0.40


def _load() -> tuple[dict[str, Any] | None, str]:
    try:
        doc = json.loads(LOOP.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"controller artifact unreadable ({type(exc).__name__})"
    stamp = str(doc.get("ran_at") or "")
    try:
        age_h = (datetime.now(tz=UTC)
                 - datetime.fromisoformat(stamp)).total_seconds() / 3600.0
    except ValueError:
        return None, f"controller artifact declares no readable ran_at ({stamp!r})"
    if age_h > MAX_AGE_H:
        return None, (f"controller allocation is {age_h:.1f}h old (limit {MAX_AGE_H}h) -- steering "
                      f"compute by a stale posterior is worse than not steering")
    return doc, ""


def controller_families(fallback: list[str] | None = None) -> tuple[list[str] | None, str]:
    """Families weighted by the controller's allocation, or (fallback, reason) when it cannot.

    Returns a LIST WITH REPEATS. `lake_campaign_specs` treats its `families` argument as the set
    to generate over, so proportion is expressed by multiplicity -- the only way to pass a budget
    through an interface that takes a set.
    """
    doc, why = _load()
    if doc is None:
        return fallback, why
    alloc = doc.get("allocation") or {}
    if isinstance(alloc, list):
        alloc = {str(r.get("family") or r.get("branch")): int(r.get("trials") or 0)
                 for r in alloc if isinstance(r, dict)}
    alloc = {str(k): int(v) for k, v in alloc.items()
             if isinstance(v, (int, float)) and int(v) > 0}
    if not alloc:
        return fallback, "controller allocated nothing to any family"

    total = sum(alloc.values())
    cap = max(1, int(total * MAX_SHARE_ONE_FAMILY))
    weighted: list[str] = []
    for fam, trials in sorted(alloc.items(), key=lambda kv: -kv[1]):
        # Scale to a queue-sized list rather than emitting one entry per trial: the queue is
        # refilled continuously and a 1,000-entry list is a memory cost with no extra information.
        n = max(1, round(min(trials, cap) / total * 100))
        weighted.extend([fam] * n)

    # THE FLOOR, applied after weighting so it cannot be rounded away. The lowest-allocation
    # families are exactly the ones a confident bandit starves, and they are where an unexplored
    # mechanism lives.
    tail = [f for f, _ in sorted(alloc.items(), key=lambda kv: kv[1])[:max(1, len(alloc) // 4)]]
    floor_n = max(1, int(len(weighted) * MIN_SHARE_FAMILIES / max(1, len(tail))))
    for fam in tail:
        weighted.extend([fam] * floor_n)

    return weighted, (f"controller allocation over {len(alloc)} famil(ies), "
                      f"{len(weighted)} weighted slot(s), {int(MIN_SHARE_FAMILIES * 100)}% floor "
                      f"reserved for the {len(tail)} least-funded")
