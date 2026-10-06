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

BREADTH LAW (2026-10-05), section 16 and section 28. The ladder also publishes the adaptive
A/B/C/D research split -- A new-breadth discovery, B depth/quality, C frontier unknown-unknowns,
D replication/falsification -- and the exploration TEMPERATURE that moves it: a stall (n_eff flat
while compute was spent) or a rising duplicate share heats A and C; edge quality degrading while
breadth rises heats B; many new structural clusters with no rise in N_EFFECTIVE_CERT heats D;
strong independent forward streams accumulating heats B (forward evidence / exploitation). Every
category keeps SPLIT_FLOOR and none exceeds SPLIT_CAP, so no category ever consumes 100% and the
frontier (C) always retains compute. Every input that is absent leaves its rule unfired and is
named in `split.unmeasured`; nothing reads as zero. `budget_factor` multiplies the leg's category
share against its base share (square-rooted, inside FACTOR_CLIP), and `judge_coverage`
reads split.B as the protected quality channel's share of the docket head. N_CERT is published
beside N_EFFECTIVE_CERT so no reader sees a nominal certificate count alone.

Consumers: research_budget.budget_s (factor), judge_coverage.quality_share (split B),
tier1_scorecard (rung), the dashboard.
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
#: breadth law section 16: research categories. C (outside the current taxonomy) is carved out of
#: the exploration legs; D are the legs that check the institution itself.
FRONTIER_LEGS: frozenset[str] = frozenset({"frontier_unknowns", "world_crawler", "deep_forest",
                                           "exogenous_search"})
FALSIFICATION_LEGS: frozenset[str] = frozenset({
    "falsifier_run", "adversaries", "adversary_evolution", "prosecutor", "placebo_audit",
    "lead_replication", "replication_civilization",
})
SATURATION = DESK / "reports" / "CERTIFICATE_SATURATION.json"
FEEDBACK = DESK / "reports" / "BREADTH_FEEDBACK.json"
#: preregistered base split and the heat applied by each fired rule (never tuned on outcomes).
BASE_SPLIT: dict[str, float] = {"A": 0.35, "B": 0.25, "C": 0.20, "D": 0.20}
SPLIT_FLOOR = 0.10
SPLIT_CAP = 0.60
HEAT = 1.5
DUP_RISE = 0.05
STRONG_STREAMS = 3


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


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


def _clamp_split(raw: dict[str, float]) -> dict[str, float]:
    """Normalise to 1 with every share in [SPLIT_FLOOR, SPLIT_CAP] (iterative water-fill)."""
    w = {k: max(1e-9, float(v)) for k, v in raw.items()}
    fixed: dict[str, float] = {}
    for _ in range(len(w) + 1):
        free = {k: v for k, v in w.items() if k not in fixed}
        room = 1.0 - sum(fixed.values())
        tot = sum(free.values())
        shares = {k: room * v / tot for k, v in free.items()} if tot > 0 else {}
        clipped = {k: (SPLIT_FLOOR if v < SPLIT_FLOOR else SPLIT_CAP)
                   for k, v in shares.items() if v < SPLIT_FLOOR or v > SPLIT_CAP}
        if not clipped:
            fixed.update(shares)
            break
        fixed.update(clipped)
    return {k: round(fixed.get(k, SPLIT_FLOOR), 4) for k in raw}


def temperature(sl: dict[str, Any], saturation: dict[str, Any], feedback: dict[str, Any],
                prev: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """Breadth law section 28: which rules fire, from measured inputs only."""
    fired: list[str] = []
    unmeasured: list[str] = []
    if sl.get("status") == "MEASURED":
        if float(sl.get("per_hour") or 0.0) <= 0.0:
            fired.append("stall")
    else:
        unmeasured.append(f"n_eff slope: {sl.get('why')}")
    cert = _dict(saturation.get("certificates"))
    recent = cert.get("median_validated_edge_recent")
    prior = cert.get("median_validated_edge_prior")
    if isinstance(recent, (int, float)) and isinstance(prior, (int, float)):
        if float(recent) < float(prior):
            fired.append("quality_degrading")
    else:
        unmeasured.append("validated edge recent-vs-prior (CERTIFICATE_SATURATION.certificates)")
    dup = feedback.get("duplicate_share")
    pdup = _dict(_dict(prev.get("budget_split")).get("inputs")).get("duplicate_share")
    if isinstance(dup, (int, float)) and isinstance(pdup, (int, float)):
        if float(dup) - float(pdup) > DUP_RISE:
            fired.append("duplicates_rising")
    else:
        unmeasured.append("duplicate share trend (BREADTH_FEEDBACK.json, two readings)")
    rows = [r for r in history if isinstance(r.get("n_structural_clusters"), (int, float))
            and isinstance(r.get("n_effective_certificates"), (int, float))]
    if len(rows) >= 2:
        a, b = rows[max(0, len(rows) - 6)], rows[-1]
        if (float(b["n_structural_clusters"]) > float(a["n_structural_clusters"])
                and float(b["n_effective_certificates"]) <= float(a["n_effective_certificates"])):
            fired.append("new_clusters_not_surviving")
    else:
        unmeasured.append("structural-cluster vs N_EFFECTIVE_CERT trend (effective_breadth.jsonl)")
    streams = cert.get("n_independent_forward_streams")
    if isinstance(streams, (int, float)):
        if int(streams) >= STRONG_STREAMS and "stall" not in fired:
            fired.append("independent_survivors_accumulating")
    else:
        unmeasured.append("independent forward streams (CERTIFICATE_SATURATION.certificates)")
    if "stall" in fired or "duplicates_rising" in fired:
        mode = "EXPLORE"
    elif "new_clusters_not_surviving" in fired:
        mode = "FALSIFY"
    elif "quality_degrading" in fired:
        mode = "DEEPEN"
    elif "independent_survivors_accumulating" in fired:
        mode = "EXPLOIT"
    else:
        mode = "BALANCED"
    return {"mode": mode, "fired": fired, "unmeasured": unmeasured,
            "duplicate_share": dup if isinstance(dup, (int, float)) else None}


def budget_split(temp: dict[str, Any]) -> dict[str, Any]:
    """Breadth law section 16: the adaptive A/B/C/D split from the fired rules."""
    w = dict(BASE_SPLIT)
    fired = set(temp.get("fired") or [])
    if fired & {"stall", "duplicates_rising"}:
        w["A"] *= HEAT
        w["C"] *= HEAT
    if "quality_degrading" in fired:
        w["B"] *= HEAT
    if "new_clusters_not_surviving" in fired:
        w["D"] *= HEAT
    if "independent_survivors_accumulating" in fired:
        w["B"] *= HEAT
    return {"split": _clamp_split(w), "base": dict(BASE_SPLIT), "mode": temp.get("mode"),
            "fired": sorted(fired), "unmeasured": temp.get("unmeasured") or [],
            "inputs": {"duplicate_share": temp.get("duplicate_share")},
            "floor": SPLIT_FLOOR, "cap": SPLIT_CAP,
            "rule": ("stall or rising duplicates heat A and C; quality degrading heats B; new "
                     "clusters without N_EFFECTIVE_CERT rise heat D; strong independent forward "
                     f"streams heat B; every share in [{SPLIT_FLOOR}, {SPLIT_CAP}]")}


def category_of(leg: str) -> str | None:
    if leg in FALSIFICATION_LEGS:
        return "D"
    if leg in FRONTIER_LEGS:
        return "C"
    if leg in EXPLORATION_LEGS:
        return "A"
    if leg in EXPLOITATION_LEGS:
        return "B"
    return None


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
    sat = _read(SATURATION)
    temp = temperature(sl, sat, _read(FEEDBACK), _read(OUT), hist)
    split = budget_split(temp)
    cert = _dict(sat.get("certificates"))
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
        "temperature": temp, "budget_split": split,
        "certificates": {"n_certificates": cert.get("n_certificates"),
                         "n_effective_certificates": cert.get("n_effective_certificates"),
                         "basis": ("CERTIFICATE_SATURATION.json" if cert
                                   else "UNMEASURED: no saturation map")},
        "rule": ("research is paid in n_eff per compute-hour: a stalled ladder moves budget to "
                 "the legs that open axes, a rising one to the legs that deepen them, clipped to "
                 f"{list(FACTOR_CLIP)}; UNMEASURED reallocates nothing"),
    }


def budget_factor(leg: str, doc: dict[str, Any] | None = None) -> float:
    """The ladder's factor for `leg` (1.0 for legs in neither set or when unmeasured)."""
    d = doc if doc is not None else _read(OUT)
    fac = _dict(d.get("factors"))
    if leg in EXPLORATION_LEGS:
        base = float(fac.get("exploration", 1.0) or 1.0)
    elif leg in EXPLOITATION_LEGS:
        base = float(fac.get("exploitation", 1.0) or 1.0)
    else:
        base = 1.0
    return min(FACTOR_CLIP[1], max(FACTOR_CLIP[0], base * split_factor(leg, d)))


def split_factor(leg: str, doc: dict[str, Any]) -> float:
    """The leg's category share over its base share, square-rooted (1.0 when absent)."""
    cat = category_of(leg)
    split = _dict(_dict(doc.get("budget_split")).get("split"))
    share = split.get(cat) if cat else None
    if not isinstance(share, (int, float)) or cat is None or BASE_SPLIT.get(cat, 0) <= 0:
        return 1.0
    return float((float(share) / BASE_SPLIT[cat]) ** 0.5)


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
    print(f"  temperature {doc['temperature']['mode']} fired={doc['temperature']['fired']} "
          f"split={doc['budget_split']['split']}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
