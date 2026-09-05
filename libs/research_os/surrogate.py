"""A learned prior over the semantic space, so the desk can rank ground it has never tested.

WHY THIS EXISTS (2026-09-04)

The controller is UCB over FAMILIES. That can only rank ground it has already spent trials on: a
family with no attempts has no bound, and a coordinate the desk has never touched is invisible to
it. AlphaSchema's contribution is exactly this gap -- it learns a reward model over the SEMANTIC
COORDINATES (event, context, quality, direction, output) rather than over realized candidates, so
it can score a cell BEFORE anything is implemented and steer toward regions rather than repeat
inside families.

WHY NOT A GRADIENT MODEL. With 255 hypotheses and 5 outcome tiers, any fitted model with more
parameters than the desk has observations is memorising, and a memorised prior is worse than no
prior because it is confidently wrong about the ground it has not seen. This is ADDITIVE PER-AXIS
EMPIRICAL BAYES: each axis VALUE gets a mean outcome shrunk toward the global mean by its own
count. A value seen twice barely moves off the global mean; a value seen fifty times is trusted.
The prediction for an unseen coordinate is the sum of its axis effects, which is precisely the
generalisation the desk needs -- `context=asia` learned from carry transfers to a mechanism asia
has never been paired with.

SHRINKAGE IS THE HONESTY. Without it, an axis value with one lucky observation outranks everything
and the allocator pours budget into noise. The shrinkage weight n/(n+PRIOR_STRENGTH) is stated,
not tuned to make a favoured region win.

IT RANKS, IT NEVER GATES. Nothing here can refuse a candidate or lower a bar -- the ten gates and
the forward window are untouched. A surrogate that could veto would let a model trained on the
desk's own past decide what the desk is allowed to discover next, which is how a search collapses
onto what it already believes.
"""
from __future__ import annotations

import json
import math
from typing import Any

#: Axes of the semantic coordinate, in the order the desk writes them.
AXES = ("event", "context", "quality", "direction", "output")

#: Pseudo-observations of the global mean mixed into every axis value. Higher = more conservative.
#: At 8, a value needs ~8 observations before it carries as much weight as the global prior.
PRIOR_STRENGTH = 8.0

#: Outcome ladder, reused from credit assignment so one definition of "progress" governs both.
from libs.research_os.credit import STAGE_VALUE  # noqa: E402

#: Exploration bonus weight. The surrogate ranks; this keeps it from starving the unseen.
EXPLORE_WEIGHT = 0.35


def _coord_axes(coordinate: str) -> dict[str, str]:
    """Split `event|context|quality|direction|output` into named axes; missing parts are ''."""
    parts = (coordinate or "").split("|")
    return {a: (parts[i].strip() if i < len(parts) else "") for i, a in enumerate(AXES)}


def fit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Learn per-axis-value effects from observed outcomes.

    `rows` are {coordinate, stage}. The target is the stage's shaped value, the same ladder credit
    assignment uses, so "progress" means one thing on this desk.
    """
    vals = [STAGE_VALUE.get(str(r.get("stage") or "IDEA"), 0.0) for r in rows]
    if not vals:
        return {"global": 0.0, "effects": {}, "n": 0,
                "why": "no outcomes recorded -- the surrogate has nothing to learn from and "
                       "returns the exploration bonus alone"}
    g = sum(vals) / len(vals)

    # sums[axis][value] -> (count, total). Deliberately not a dict of lists: the desk records
    # hundreds of thousands of rows over time and this stays O(distinct values).
    sums: dict[str, dict[str, list[float]]] = {a: {} for a in AXES}
    for r, v in zip(rows, vals, strict=False):
        for axis, value in _coord_axes(str(r.get("coordinate") or "")).items():
            if not value:
                continue
            cell = sums[axis].setdefault(value, [0.0, 0.0])
            cell[0] += 1.0
            cell[1] += v

    effects: dict[str, dict[str, dict[str, float]]] = {}
    for axis, by_value in sums.items():
        effects[axis] = {}
        for value, (n, total) in by_value.items():
            mean = total / n
            # SHRINK TOWARD THE GLOBAL MEAN by observation count. One lucky trial cannot outrank
            # a region with fifty.
            w = n / (n + PRIOR_STRENGTH)
            effects[axis][value] = {"n": n, "raw": round(mean, 5),
                                    "effect": round(w * (mean - g), 5)}
    return {"global": round(g, 5), "effects": effects, "n": len(rows),
            "prior_strength": PRIOR_STRENGTH,
            "why": ("additive per-axis empirical Bayes: each axis value's mean shrunk toward the "
                    "global mean by n/(n+prior). Unseen values contribute nothing, so an unseen "
                    "coordinate scores the global mean plus its exploration bonus -- never zero, "
                    "which would read as 'known bad'.")}


def score(model: dict[str, Any], coordinate: str) -> dict[str, Any]:
    """Predicted progress for a coordinate, with the exploration bonus that keeps search alive."""
    eff = model.get("effects") or {}
    g = float(model.get("global") or 0.0)
    total = g
    seen_n = []
    contributions = {}
    for axis, value in _coord_axes(coordinate).items():
        if not value:
            continue
        cell = (eff.get(axis) or {}).get(value)
        if cell is None:
            seen_n.append(0.0)
            contributions[axis] = 0.0
            continue
        total += float(cell["effect"])
        seen_n.append(float(cell["n"]))
        contributions[axis] = float(cell["effect"])

    # UCB-SHAPED BONUS over the LEAST-observed axis of this coordinate. A region is unexplored if
    # ANY of its axes is, and taking the minimum is what stops a coordinate inheriting confidence
    # from four well-trodden axes and one nobody has touched.
    n_min = min(seen_n) if seen_n else 0.0
    total_n = max(1.0, float(model.get("n") or 1))
    bonus = EXPLORE_WEIGHT * math.sqrt(math.log(total_n + 1.0) / (n_min + 1.0))
    return {"coordinate": coordinate, "predicted": round(total, 5),
            "exploration_bonus": round(bonus, 5), "rank_score": round(total + bonus, 5),
            "least_observed_axis_n": n_min, "contributions": contributions}


def from_store(limit: int = 5000) -> dict[str, Any]:
    """Fit on everything the research store has recorded."""
    from libs.research_os import store
    from libs.research_os.credit import _stage_for

    rows: list[dict[str, Any]] = []
    with store.connect() as conn:
        for hid, coord in conn.execute(
                "SELECT hypothesis_id, coordinate FROM hypotheses "
                "WHERE coordinate IS NOT NULL AND coordinate != '' LIMIT ?", (limit,)).fetchall():
            stage, _cls, _ad = _stage_for(str(hid), conn)
            rows.append({"coordinate": str(coord), "stage": stage})
    return fit(rows)


def rank(model: dict[str, Any], coordinates: list[str], k: int = 10) -> list[dict[str, Any]]:
    """The k highest-scoring coordinates, best first."""
    scored = [score(model, c) for c in coordinates]
    scored.sort(key=lambda s: -s["rank_score"])
    return scored[:k]


def main() -> int:
    m = from_store()
    print("SEMANTIC SURROGATE")
    print(f"  fitted on {m['n']} hypothes(es); global mean progress {m['global']}")
    for axis, values in (m.get("effects") or {}).items():
        top = sorted(values.items(), key=lambda kv: -kv[1]["effect"])[:3]
        if top:
            print(f"  {axis:10s} " + "  ".join(
                f"{v}({c['effect']:+.3f},n={int(c['n'])})" for v, c in top))
    print(json.dumps({"prior_strength": m.get("prior_strength")}, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
