"""THE BREADTH LADDER -- effective breadth as the research objective, measured and rung by rung.

WHY THIS EXISTS (principal's blueprint, 2026-09-16, item 4). The desk optimised candidate COUNT:
88,716 docket rows, 65 sleeves, and an effective breadth the allocator measured at 2.06 bets on
realised returns (reports/EFFECTIVE_BREADTH.json). Ten thousand hypotheses drawn from six
information axes are not ten thousand edges. The number that moves E[log W] is n_eff -- the
independent bets the book actually holds -- so the research allocator has to be paid in n_eff
per compute-hour, not in rows per hour. The ladder is 6 -> 10 -> 15 -> 25 -> 40.

WHAT THIS DOES, AND WHAT IT DOES NOT. It reads the desk's own effective-breadth history and the
compute ledger, publishes the current rung, the next target and the measured slope
d(n_eff)/d(compute-hour), and derives one bounded factor per research leg that
`research_budget` multiplies into the bandit's budget: a STALLED ladder (no rise over the last
readings while compute was spent) moves seconds from exploitation legs to the exploration legs
that open new axes; a RISING ladder moves them back. Two-sided (Rule 2), clipped to [0.75, 1.5],
1.0 whenever the slope is UNMEASURED -- an absent measurement never reallocates anything. The
exploration floor is the share of UNMEASURED cells in the axis registry when it exists, else the
share of empty breadth clusters, bounded to [0.2, 0.6]; it is published, and `research_budget`
reads it as the minimum share of the exploration legs' seconds.

Consumers: research_budget.budget_s (factor), tier1_scorecard (rung), the dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
HISTORY = DESK / "data" / "effective_breadth.jsonl"
LATEST = DESK / "reports" / "EFFECTIVE_BREADTH.json"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
AXIS = DESK / "reports" / "AXIS_REGISTRY.json"
OUT = DESK / "reports" / "BREADTH_LADDER.json"
RUNGS: tuple[int, ...] = (6, 10, 15, 25, 40)
FLOOR_BOUNDS = (0.2, 0.6)
FACTOR_CLIP = (0.75, 1.5)
MIN_READINGS = 3
#: Legs that OPEN axes (exploration) versus legs that DEEPEN what is already open (exploitation).
EXPLORATION_LEGS: frozenset[str] = frozenset({
    "breadth_sweep", "exogenous_search", "standing_questions", "axis_registry", "world_crawler",
    "deep_forest", "frontier_unknowns", "session_chart_expansion", "causal_graph",
})
EXPLOITATION_LEGS: frozenset[str] = frozenset({"deepen", "alpha_evolution", "mine", "search"})


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _jsonl(p: Path, tail: int = 5000) -> list[dict[str, Any]]:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _at(v: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def readings(history: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    """(time, n_eff) pairs, oldest first, from the effective-breadth history."""
    out: list[tuple[datetime, float]] = []
    for r in history:
        t = _at(r.get("at"))
        v = r.get("effective_breadth")
        if t is not None and isinstance(v, (int, float)):
            out.append((t, float(v)))
    out.sort(key=lambda x: x[0])
    return out


def compute_hours_between(ledger: list[dict[str, Any]], start: datetime, end: datetime,
                          ) -> tuple[float, dict[str, float]]:
    """Wall hours the ledger records between two instants, in total and per leg."""
    total = 0.0
    per: dict[str, float] = {}
    for r in ledger:
        t = _at(r.get("at"))
        if t is None or t < start or t > end:
            continue
        try:
            h = float(r.get("wall_s") or 0.0) / 3600.0
        except (TypeError, ValueError):
            continue
        total += h
        name = str(r.get("run") or "")
        per[name] = per.get(name, 0.0) + h
    return total, per


def rung_of(n_eff: float) -> tuple[int | None, int | None]:
    """(current rung reached, next target). Below the first rung reads (None, 6)."""
    reached = None
    for r in RUNGS:
        if n_eff >= r:
            reached = r
    nxt = next((r for r in RUNGS if r > n_eff), None)
    return reached, nxt


def slope(reads: list[tuple[datetime, float]], ledger: list[dict[str, Any]],
          window: int = 6) -> dict[str, Any]:
    """d(n_eff)/d(compute-hour) over the last `window` readings; UNMEASURED below MIN_READINGS
    or when no compute was recorded between them."""
    rs = reads[-window:]
    if len(rs) < MIN_READINGS:
        return {"status": "UNMEASURED", "why": f"{len(rs)} reading(s), below {MIN_READINGS}",
                "n_readings": len(rs)}
    hours, per_leg = compute_hours_between(ledger, rs[0][0], rs[-1][0])
    d_neff = rs[-1][1] - rs[0][1]
    if hours <= 0:
        return {"status": "UNMEASURED", "why": "no compute recorded between the readings",
                "n_readings": len(rs), "d_neff": round(d_neff, 4)}
    return {"status": "MEASURED", "n_readings": len(rs), "d_neff": round(d_neff, 4),
            "compute_hours": round(hours, 3), "per_hour": round(d_neff / hours, 5),
            "from": rs[0][0].isoformat(timespec="seconds"),
            "to": rs[-1][0].isoformat(timespec="seconds"),
            "exploration_hours": round(sum(h for k, h in per_leg.items()
                                           if k in EXPLORATION_LEGS), 3),
            "exploitation_hours": round(sum(h for k, h in per_leg.items()
                                            if k in EXPLOITATION_LEGS), 3)}


def exploration_floor(axis: dict[str, Any], latest: dict[str, Any],
                      history_row: dict[str, Any] | None) -> dict[str, Any]:
    """Share of UNMEASURED cells (axis registry) else share of empty clusters, bounded."""
    by_state = axis.get("by_state") if isinstance(axis.get("by_state"), dict) else None
    if by_state:
        n = sum(int(v) for v in by_state.values() if isinstance(v, (int, float)))
        unm = int(by_state.get("UNMEASURED", 0) or 0)
        if n > 0:
            raw = unm / n
            return {"floor": round(min(FLOOR_BOUNDS[1], max(FLOOR_BOUNDS[0], raw)), 3),
                    "raw": round(raw, 4), "basis": "AXIS_REGISTRY.json by_state UNMEASURED share"}
    row = history_row or {}
    occ, emp = row.get("n_clusters_occupied"), row.get("n_clusters_empty")
    if isinstance(occ, (int, float)) and isinstance(emp, (int, float)) and (occ + emp) > 0:
        raw = float(emp) / float(occ + emp)
        return {"floor": round(min(FLOOR_BOUNDS[1], max(FLOOR_BOUNDS[0], raw)), 3),
                "raw": round(raw, 4), "basis": "effective_breadth.jsonl empty-cluster share"}
    return {"floor": FLOOR_BOUNDS[0], "raw": None,
            "basis": "UNMEASURED: no axis registry and no cluster counts; the lower bound applies"}


def factors(sl: dict[str, Any]) -> dict[str, Any]:
    """Per-leg budget factors from the slope. UNMEASURED -> 1.0 everywhere."""
    if sl.get("status") != "MEASURED":
        return {"exploration": 1.0, "exploitation": 1.0, "why": "slope UNMEASURED: no reallocation"}
    per_hour = float(sl.get("per_hour") or 0.0)
    if per_hour <= 0.0:
        return {"exploration": FACTOR_CLIP[1] ** 0.5, "exploitation": FACTOR_CLIP[0] ** 0.5,
                "why": (f"n_eff did not rise ({sl.get('d_neff')} over {sl.get('compute_hours')} "
                        "compute-hours): seconds move from exploitation to the legs that open axes")}
    return {"exploration": 1.0, "exploitation": min(FACTOR_CLIP[1], 1.0 + per_hour),
            "why": (f"n_eff rose {sl.get('d_neff')} over {sl.get('compute_hours')} compute-hours: "
                    "exploitation is paying; exploration keeps its floor")}


def build() -> dict[str, Any]:
    hist = _jsonl(HISTORY)
    reads = readings(hist)
    latest = _read(LATEST)
    ledger = _jsonl(LEDGER, tail=20000)
    axis = _read(AXIS)
    n_eff = reads[-1][1] if reads else None
    reached, nxt = rung_of(n_eff) if n_eff is not None else (None, RUNGS[0])
    sl = slope(reads, ledger)
    fac = factors(sl)
    floor = exploration_floor(axis, latest, hist[-1] if hist else None)
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_eff": n_eff, "n_eff_at": reads[-1][0].isoformat(timespec="seconds") if reads else None,
        "binding_reading": (hist[-1].get("binding_reading") if hist else None),
        "rungs": list(RUNGS), "rung_reached": reached, "next_target": nxt,
        "gap_to_next": (None if n_eff is None or nxt is None else round(nxt - n_eff, 3)),
        "slope": sl, "factors": fac, "exploration_floor": floor,
        "exploration_legs": sorted(EXPLORATION_LEGS),
        "exploitation_legs": sorted(EXPLOITATION_LEGS),
        "status": "UNMEASURED" if n_eff is None else "MEASURED",
        "rule": ("research is paid in n_eff per compute-hour: a stalled ladder moves budget to "
                 "the legs that open axes, a rising one to the legs that deepen them, clipped to "
                 f"{list(FACTOR_CLIP)}; UNMEASURED reallocates nothing"),
    }


def budget_factor(leg: str, doc: dict[str, Any] | None = None) -> float:
    """The ladder's factor for `leg` (1.0 for legs in neither set or when unmeasured)."""
    d = doc if doc is not None else _read(OUT)
    fac = d.get("factors") if isinstance(d.get("factors"), dict) else {}
    if leg in EXPLORATION_LEGS:
        return float(fac.get("exploration", 1.0) or 1.0)
    if leg in EXPLOITATION_LEGS:
        return float(fac.get("exploitation", 1.0) or 1.0)
    return 1.0


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"breadth ladder: n_eff={doc['n_eff']} rung={doc['rung_reached']} "
          f"next={doc['next_target']} slope={doc['slope'].get('status')} "
          f"per_hour={doc['slope'].get('per_hour')} floor={doc['exploration_floor']['floor']} "
          f"factors exploration x{doc['factors']['exploration']:.2f} "
          f"exploitation x{doc['factors']['exploitation']:.2f}")
    print(f"  {doc['factors']['why']}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
