"""THE EDGE-QUALITY PARETO FRONTIER OVER THE DOCKET (breadth law, BREADTH-0560..0564). SHADOW.

The law: candidates are ranked on a frontier of capacity, independence, tail behaviour and
time-to-evidence, and a DOMINATED candidate -- one another candidate beats or ties on every
objective and beats on at least one -- gets less compute. This organ measures that frontier over
the judge's docket (`data/hypotheses/external_survivors.json`) every hour:

    capacity          research/breadth_capacity liquidity (spread rank) x capacity headroom for
                      the row's symbol (headroom 1.0 where no sleeve has consumed any)
    independence      the row's persisted breadth value (`breadth_order.sat`: the saturation
                      map's expected marginal independent bet)
    tail              a PRE-EVALUATION prior from the mechanism's payoff shape
                      (breadth_debt.PAYOFF_SHAPE): crash-tailed shapes (carry accrual, concave
                      reversion, liquidity provision) 0, neutral 0.5, convex trend 1
    time_to_evidence  trades per day on the row's chart (breadth_capacity.TRADES_PER_DAY):
                      the faster a candidate can show forward evidence, the better

A row missing any objective is UNMEASURED and is never called dominated (L1.28a).

SHADOW, NOT LIVE. Demoting dominated rows would move the judge's order, and the docket order is
a judged-volume decision: this organ publishes the frontier, the dominated set and the compute
share that WOULD move (`compute_shift_shadow`) beside the live order, and changes nothing. Wiring
it into the order is a separate, reviewed step with its missed-growth line.
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
OUT = DESK / "reports" / "EDGE_PARETO.json"
UNMEASURED, MEASURED = "UNMEASURED", "MEASURED"
OBJECTIVES = ("capacity", "independence", "tail", "time_to_evidence")
TAIL_PRIOR = {"carry_accrual": 0.0, "concave_reversion": 0.0, "liquidity_provision": 0.0,
              "convex_trend": 1.0}
TAIL_NEUTRAL = 0.5
#: rounding before the dominance test: objectives this close are a tie, not a win
ROUND = 3
MAX_EXAMPLES = 20


def _params(row: Mapping[str, Any]) -> dict[str, Any]:
    p = row.get("params")
    if isinstance(p, str):
        try:
            p = ast.literal_eval(p)
        except (ValueError, SyntaxError):
            p = None
    return dict(p) if isinstance(p, Mapping) else {}


def _mods() -> tuple[Any, Any, Any]:
    try:
        from research import axis_registry as ar
        from research import breadth_capacity as bc
        from research import breadth_debt as bd
    except ImportError:                                                  # pragma: no cover
        import axis_registry as ar  # type: ignore[import-not-found,no-redef]
        import breadth_capacity as bc  # type: ignore[import-not-found,no-redef]
        import breadth_debt as bd  # type: ignore[import-not-found,no-redef]
    return ar, bc, bd


def objectives(row: Mapping[str, Any], *, capacity: Any, ar: Any, bc: Any,
               bd: Any) -> dict[str, float | None]:
    """The four objectives of one docket row (higher is better), None where unmeasured."""
    p = _params(row)
    tf = str(p.get("timeframe") or row.get("timeframe") or row.get("chart") or "")
    sym = str(row.get("symbol") or row.get("sym") or "").upper()
    out: dict[str, float | None] = dict.fromkeys(OBJECTIVES)
    t = capacity(sym, tf) if capacity is not None else None
    tt = (t or {}).get("terms") if isinstance(t, Mapping) else None
    if isinstance(tt, Mapping) and tt.get("liquidity") is not None:
        # headroom is measured only where a sleeve already trades the symbol; a symbol the book
        # does not hold has consumed none of it, which is breadth_capacity's own 1.0
        cap_h = tt.get("capacity")
        out["capacity"] = (float(cap_h) if cap_h is not None else 1.0) * float(tt["liquidity"])
    bo = row.get("breadth_order")
    if isinstance(bo, Mapping) and isinstance(bo.get("sat"), (int, float)) \
            and not isinstance(bo.get("sat"), bool):
        out["independence"] = float(bo["sat"])
    mech = ar.classify_family(row.get("family"))[0]
    shape = bd.PAYOFF_SHAPE.get(mech)
    if shape is not None:
        out["tail"] = TAIL_PRIOR.get(shape, TAIL_NEUTRAL)
    tpd = bc.TRADES_PER_DAY.get(tf)
    if tpd is not None:
        out["time_to_evidence"] = float(tpd)
    return out


def dominated_mask(points: np.ndarray) -> np.ndarray:
    """True where some other point is >= on every objective and > on one (maximisation)."""
    n = points.shape[0]
    dom = np.zeros(n, dtype=bool)
    for i in range(n):
        ge = np.all(points >= points[i], axis=1)
        gt = np.any(points > points[i], axis=1)
        dom[i] = bool(np.any(ge & gt))
    return dom


def build(*, docket: Any = None, capacity: Any = "context",
          now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    rows = docket if docket is not None else _read(DOCKET)
    if not isinstance(rows, list):
        return {"status": UNMEASURED, "at": t.isoformat(timespec="seconds"),
                "why": "docket absent or unreadable", "mode": "SHADOW"}
    ar, bc, bd = _mods()
    cap = capacity
    if capacity == "context":
        try:
            ctx = bc.Context()
            cache: dict[tuple[str, str], Any] = {}

            def cap(sym: str, tf: str) -> Any:
                k = (sym, tf)
                if k not in cache:
                    cache[k] = bc.terms(sym, {"timeframe": tf}, ctx)
                return cache[k]
        except Exception:
            cap = None
    objs = []
    missing: Counter[str] = Counter()
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        o = objectives(r, capacity=cap, ar=ar, bc=bc, bd=bd)
        for k, v in o.items():
            if v is None:
                missing[k] += 1
        objs.append((r, o))
    full = [(r, o) for r, o in objs if all(o[k] is not None for k in OBJECTIVES)]
    if not full:
        return {"status": UNMEASURED, "at": t.isoformat(timespec="seconds"), "mode": "SHADOW",
                "n_rows": len(objs), "unmeasured_by_objective": dict(missing),
                "why": "no docket row carries all four objectives"}
    keys = [tuple(round(float(o[k] or 0.0), ROUND) for k in OBJECTIVES) for _, o in full]
    uniq = sorted(set(keys))
    dom_u = dominated_mask(np.asarray(uniq, dtype=float))
    dom_of = {u: bool(d) for u, d in zip(uniq, dom_u, strict=True)}
    n_dom = sum(1 for k in keys if dom_of[k])
    front = [dict(zip(OBJECTIVES, u, strict=True)) for u in uniq if not dom_of[u]]
    examples = []
    for (r, _o), k in zip(full, keys, strict=True):
        if dom_of[k] and len(examples) < MAX_EXAMPLES:
            examples.append({"symbol": r.get("symbol"), "family": r.get("family"),
                             "objectives": dict(zip(OBJECTIVES, k, strict=True))})
    return {"status": MEASURED, "at": t.isoformat(timespec="seconds"), "mode": "SHADOW",
            "n_rows": len(objs), "n_measured": len(full), "n_dominated": n_dom,
            "n_frontier_points": len(front), "frontier": front[:200],
            "dominated_examples": examples,
            "unmeasured_by_objective": dict(missing),
            "compute_shift_shadow": {
                "share_of_measured_rows_dominated": round(n_dom / len(full), 6),
                "would": ("order dominated rows after the frontier inside their breadth tier; "
                          "no row dropped, every judged row still charged its trial"),
                "live": False},
            "tail_basis": "payoff-shape prior before evaluation (breadth_debt.PAYOFF_SHAPE)",
            "rule": ("a row is dominated only against rows measured on all four objectives; a "
                     "row missing one is UNMEASURED, never dominated")}


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def publish(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)
    return p
