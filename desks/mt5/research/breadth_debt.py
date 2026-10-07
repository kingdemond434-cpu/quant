"""BREADTH_DEBT.json: the breadth-debt queue, BREADTH-CONSTRAINED MODE, and the empty clusters.

Producer-wide enforcement law §3 and §27 (2026-10-05), audit repair rank 12 (2026-10-06).

THE MODE FLAG AND ITS MEASURED TRIGGER. Effective breadth is the BINDING constraint when either
reading below fires. Both are measured, both are published beside the verdict, and an input that
cannot be read is named rather than assumed:

  certificate dilution  N_EFFECTIVE_CERT / N_CERT < BINDING_RATIO (0.25). More than four
                        certificates per effective bet: the desk is minting certificates into bets
                        it already owns, so another certificate of the same kind buys no breadth.
                        Measured on the box 2026-10-06 at 837 certificates -> k_eff 2.5 (0.003).
  stalled ladder        the breadth ladder's n_eff slope per compute-hour is MEASURED and <= 0
                        while n_eff is below its next rung: compute is spent and breadth does not
                        move.

  ON          either fired.
  OFF         both inputs measured and neither fired.
  UNMEASURED  the saturation map is absent or stale. Never read as OFF.

WHAT THE MODE DOES. It names, in priority order, where the next research hour should go: empty
payer clusters, empty information sources, low-occupancy mechanisms, and the regimes, horizons,
session clocks and asset-factor exposures the certified book does not hold. `certificate_
saturation.stamp` raises the breadth value of docket rows that land on those targets while the
mode is ON (ORDER ONLY), and every producer's brief carries the queue. It never decides what passes,
never caps capital, and never takes budget from the protected QUALITY channel.

THE EMPTY CLUSTERS are named with the bounty the portfolio has posted for them and the auction's
current bids for the departments those bounties address. The MISSIONS that fill them are not
built here: they arrive from PR #163 once #137 merges.

k_eff, stress k_eff and tail k_eff are published side by side, because the mode is about the
weakest of the three (robust k_eff).
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
OUT = REPORTS / "BREADTH_DEBT.json"
LADDER = REPORTS / "BREADTH_LADDER.json"
BOUNTY = REPORTS / "PORTFOLIO_BOUNTY.json"
AUCTION = REPORTS / "RESEARCH_AUCTION.json"
UNMEASURED = "UNMEASURED"
BINDING_RATIO = 0.25
#: A mechanism held by at most this many certified groups is LOW-OCCUPANCY.
LOW_OCCUPANCY_GROUPS = 1
#: How far a target row's breadth value is raised while the mode is ON (ordering only).
MODE_BOOST = 1.5
MAX_TARGETS = 25


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def mode(cert: dict[str, Any], ladder: dict[str, Any], map_status: str) -> dict[str, Any]:
    """The mode verdict with both readings behind it."""
    if map_status != "MEASURED":
        return {"mode": UNMEASURED, "fired": [], "why": f"saturation map {map_status}"}
    n, k = _num(cert.get("n_certificates")), _num(cert.get("n_effective_certificates"))
    ratio = (k / n) if n and k is not None else None
    sl = ladder.get("slope") if isinstance(ladder.get("slope"), dict) else {}
    fired: list[str] = []
    readings: dict[str, Any] = {"effective_over_nominal": round(ratio, 6) if ratio else ratio,
                                "binding_ratio": BINDING_RATIO,
                                "ladder_slope_status": sl.get("status"),
                                "ladder_per_hour": sl.get("per_hour"),
                                "n_eff": ladder.get("n_eff"),
                                "next_rung": ladder.get("next_target")}
    if ratio is not None and ratio < BINDING_RATIO:
        fired.append("certificate_dilution")
    stalled = (sl.get("status") == "MEASURED" and (_num(sl.get("per_hour")) or 0.0) <= 0.0
               and ladder.get("next_target") is not None)
    if stalled:
        fired.append("stalled_ladder")
    measured_both = ratio is not None and sl.get("status") == "MEASURED"
    verdict = "ON" if fired else ("OFF" if measured_both else UNMEASURED)
    return {"mode": verdict, "fired": fired, "readings": readings,
            "trigger": (f"ON when N_EFFECTIVE_CERT/N_CERT < {BINDING_RATIO} (certificate "
                        "dilution) OR the ladder's n_eff slope per compute-hour is MEASURED <= 0 "
                        "below the next rung (stalled ladder); OFF only when both are measured "
                        "and neither fires; UNMEASURED otherwise")}


#: THE PAYOFF SHAPE a mechanism's returns take (BREADTH-0221, 0549): what the bet's P&L looks
#: like, not what it trades. Two books of different instruments with one shape share their bad
#: days; a shape the book does not hold is the cheapest independence on offer.
PAYOFF_SHAPE = {
    "trend_persistence": "convex_trend", "breakout_liquidity": "convex_trend",
    "regime_transition": "convex_trend", "cross_market_lead": "convex_trend",
    "range_reversion": "concave_reversion", "carry_rollover": "carry_accrual",
    "macro_release": "event_jump", "volatility_shock": "event_jump",
    "inventory_shock": "event_jump", "gamma_hedging_state": "event_jump",
    "forced_flow": "liquidity_provision", "forced_liquidation": "liquidity_provision",
    "fx_fixing_flow": "liquidity_provision", "hedging_demand_close_flow": "liquidity_provision",
    "positioning_crowding": "liquidity_provision",
    "relative_value_dislocation": "spread_convergence",
    "calendar_seasonality": "calendar_drift", "session_handover": "calendar_drift",
    "session_information_handoff": "calendar_drift",
    "execution_microstructure": "microstructure_scalp",
}
PAYOFF_SHAPES = tuple(sorted(set(PAYOFF_SHAPE.values())))


def payoff_shapes(doc: dict[str, Any]) -> dict[str, Any]:
    """Certificates and effective bets per payoff shape, the shapes the book holds none of
    (MISSING PAYOFF SHAPES, 0549) and every shape ordered by its effective occupancy, emptiest
    first (the low-overlap return geometries, 0221). UNMEASURED without a map."""
    clusters = doc.get("clusters") if isinstance(doc.get("clusters"), dict) else {}
    if not clusters:
        return {"status": UNMEASURED, "why": "no saturation clusters"}
    n: Counter[str] = Counter()
    eff: dict[str, float] = defaultdict(float)
    for v in clusters.values():
        mech = str((v.get("hierarchy") or {}).get("L1"))
        shape = PAYOFF_SHAPE.get(mech)
        if shape is None:
            continue
        n[shape] += int(v.get("certificate_count") or 0)
        eff[shape] += float(v.get("effective_certificate_count") or 0.0)
    rows = [{"shape": sh, "certificates": n.get(sh, 0), "effective": round(eff.get(sh, 0.0), 4)}
            for sh in PAYOFF_SHAPES]
    rows.sort(key=lambda r: (r["effective"], r["certificates"], r["shape"]))
    return {"status": "MEASURED", "by_shape": rows,
            "missing_payoff_shapes": [r["shape"] for r in rows if r["certificates"] == 0],
            "low_overlap_order": [r["shape"] for r in rows]}


def _structures(doc: dict[str, Any]) -> dict[str, list[str]]:
    """Registered cross-asset residual and relative-value families the book holds no
    certificate in (0223/0224), from the family table, never a hand list."""
    held = {str(f).lower() for v in (doc.get("clusters") or {}).values() if isinstance(v, dict)
            for f in (v.get("families") or [])}
    try:
        from research import axis_registry as ar
    except ImportError:
        import axis_registry as ar  # type: ignore[import-not-found,no-redef]
    resid, rv = [], []
    for fam, (mech, info, _style) in sorted(ar.FAMILY_TABLE.items()):
        if fam in held:
            continue
        if info == "cross_asset" and mech in ("relative_value_dislocation", "cross_market_lead"):
            resid.append(fam)
        if mech == "relative_value_dislocation":
            rv.append(fam)
    return {"cross_asset_residual_structures": resid, "relative_value_structures": rv}


def targets(doc: dict[str, Any], lane_factors: set[str] | None = None) -> dict[str, Any]:
    """What breadth-constrained mode prioritises, read from the saturation map."""
    clusters = doc.get("clusters") if isinstance(doc.get("clusters"), dict) else {}
    debts = doc.get("breadth_debts") if isinstance(doc.get("breadth_debts"), list) else []
    occ_l1: Counter[str] = Counter()
    occ_l2: set[str] = set()
    for v in clusters.values():
        h = v.get("hierarchy") or {}
        occ_l1[str(h.get("L1"))] += 1
        occ_l2.add(str(h.get("L2")))
    empty_payers = sorted({str(d.get("mechanism")) for d in debts if d.get("new_payer")})
    empty_info = sorted({str(d.get("information_source")) for d in debts
                         if str(d.get("information_source")) not in occ_l2})
    low_occ = sorted(m for m, c in occ_l1.items() if c <= LOW_OCCUPANCY_GROUPS)
    shapes = payoff_shapes(doc)
    unexplored: dict[str, Counter[str]] = defaultdict(Counter)
    for v in clusters.values():
        for axis, vals in (v.get("remaining_unexplored_axes") or {}).items():
            for x in vals or []:
                unexplored[axis][str(x)] += 1
    try:
        from research.certificate_saturation import factor_of
    except ImportError:
        from certificate_saturation import factor_of  # type: ignore[import-not-found,no-redef]
    book_factors = {str(factor_of(str(c.get("sym") or ""))) for c in
                    (doc.get("certified_specs") or []) if isinstance(c, dict)}
    missing_factors = sorted((lane_factors or set()) - book_factors) if lane_factors else None
    return {
        "empty_payer_clusters": empty_payers,
        "empty_information_sources": empty_info,
        "low_occupancy_mechanisms": low_occ,
        "unrepresented_regimes": [k for k, _ in unexplored.get("regime", Counter()).most_common()],
        "unrepresented_horizons": [k for k, _ in
                                   unexplored.get("horizon", Counter()).most_common()],
        "unrepresented_session_clocks": [k for k, _ in
                                         unexplored.get("session", Counter()).most_common()],
        "unrepresented_asset_factor_exposures": (missing_factors if missing_factors is not None
                                                 else UNMEASURED),
        "low_overlap_return_geometries": shapes.get("low_overlap_order", UNMEASURED),
        "missing_payoff_shapes": shapes.get("missing_payoff_shapes", UNMEASURED),
        **_structures(doc),
    }


def empty_clusters(doc: dict[str, Any], bounty: dict[str, Any],
                   auction: dict[str, Any]) -> list[dict[str, Any]]:
    """Every declared alpha cluster with no certificate, with its bounty and the auction's bids.

    NAMED, NOT FILLED: the missions arrive from PR #163 once #137 merges."""
    pri = doc.get("empty_cluster_priors") if isinstance(doc.get("empty_cluster_priors"),
                                                       dict) else {}
    debts = doc.get("breadth_debts") if isinstance(doc.get("breadth_debts"), list) else []
    rows = bounty.get("bounties") if isinstance(bounty.get("bounties"), list) else []
    bids = auction.get("bids") if isinstance(auction.get("bids"), dict) else {}
    out = []
    for k, v in sorted(pri.items()):
        if not isinstance(v, dict) or int(v.get("certificates") or 0) > 0:
            continue
        mine = [d for d in debts if d.get("alpha_cluster") == k]
        ids = {f"bounty:breadth_debt:{d.get('missing_cluster')}"[:160] for d in mine}
        posted = [b for b in rows if isinstance(b, dict) and b.get("bounty_id") in ids]
        depts = sorted({t for b in posted for t in (b.get("targets") or [])})
        out.append({
            "cluster": k, "status": v.get("status"), "empty_prior_decay": v.get("decay"),
            "effort_judged": v.get("effort_judged"), "families": v.get("families"),
            "breadth_debts": len(mine),
            "bounty_value": round(sum(float(d.get("bounty") or 0.0) for d in mine), 6),
            "expected_delta_k_eff": round(sum(max(0.0, float(d.get("expected_delta_k_eff")
                                                             or 0.0)) for d in mine), 6),
            "bounties_posted": len(posted),
            "auction_bids": {d: (bids.get(d) or {}).get("bid") for d in depts},
            "mission": "NOT BUILT HERE: from PR #163 after #137 merges",
        })
    return out


def _lane_factors() -> set[str] | None:
    try:
        from research.breadth_rotation import hypothesis_symbols
        from research.certificate_saturation import factor_of
    except Exception:
        return None
    lane = hypothesis_symbols()
    return {str(factor_of(s)) for s in lane} if lane else None


def build(*, sat: dict[str, Any] | None = None, ladder: dict[str, Any] | None = None,
          bounty: dict[str, Any] | None = None, auction: dict[str, Any] | None = None,
          lane_factors: set[str] | None = None, now: datetime | None = None) -> dict[str, Any]:
    if sat is None:
        try:
            from research.certificate_saturation import read_fresh
        except ImportError:
            from certificate_saturation import read_fresh  # type: ignore[import-not-found,no-redef]
        sat = read_fresh()
    ladder = ladder if ladder is not None else _read(LADDER)
    bounty = bounty if bounty is not None else _read(BOUNTY)
    auction = auction if auction is not None else _read(AUCTION)
    cert = sat.get("certificates") if isinstance(sat.get("certificates"), dict) else {}
    st = str(sat.get("status") or UNMEASURED)
    m = mode(cert, ladder, st)
    debts = sat.get("breadth_debts") if isinstance(sat.get("breadth_debts"), list) else []
    book = sat.get("book_breadth") if isinstance(sat.get("book_breadth"), dict) else {}
    tg = targets(sat, lane_factors if lane_factors is not None else _lane_factors()) \
        if st == "MEASURED" else {}
    return {
        "at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "status": st if st == "MEASURED" else UNMEASURED,
        "why": sat.get("why"),
        "breadth_constrained_mode": m["mode"], "mode": m,
        "map_at": sat.get("at"), "basis": cert.get("basis"),
        "k_eff": {"k_eff": book.get("k_eff_full"), "stress_k_eff": book.get("k_eff_stress"),
                  "tail_k_eff": book.get("k_eff_tail"), "robust_k_eff": book.get("robust_k_eff"),
                  "n_effective_certificates": cert.get("n_effective_certificates"),
                  "n_effective_status": cert.get("n_effective_status"),
                  "status": book.get("status", UNMEASURED)},
        "priority_targets": tg,
        "payoff_shapes": payoff_shapes(sat) if st == "MEASURED" else {"status": UNMEASURED},
        "queue": [{k: d.get(k) for k in ("priority", "missing_cluster", "mechanism",
                                         "information_source", "asset_class", "alpha_cluster",
                                         "economic_rationale", "current_nearest_exposure",
                                         "expected_delta_k_eff", "value_units",
                                         "expected_independence", "required_data",
                                         "candidate_producers", "historical_search_effort",
                                         "failure_history", "reopen_trigger", "bounty")}
                  for d in debts[:MAX_TARGETS]],
        "empty_clusters": empty_clusters(sat, bounty, auction),
        "inputs_at": {"bounty": bounty.get("at"), "auction": auction.get("at"),
                      "ladder": ladder.get("generated_utc") or ladder.get("at")},
        "consumers": ["certificate_saturation.stamp (docket order: target rows raised while ON)",
                      "certificate_saturation.producer_brief (deepseek, kimi and every seat)",
                      "research/breadth_law_coverage.py (CRO table)"],
        "rule": ("breadth decides what is hunted and judged next, never what passes; the mode "
                 "reorders and briefs, it never drops a row, caps capital or takes the QUALITY "
                 "channel's protected share"),
    }


def publish(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    doc["generated_utc"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def load(path: Path | None = None, *, max_age_h: float = 6.0,
         now: datetime | None = None) -> dict[str, Any]:
    """The published queue when fresh; {} when absent or older than `max_age_h` (a stale mode
    flag is not a mode)."""
    d = _read(path or OUT)
    try:
        t = datetime.fromisoformat(str(d.get("at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return {}
    age = ((now or datetime.now(tz=UTC)) - t).total_seconds() / 3600.0
    return d if age <= max_age_h else {}


def boost_for(cluster: str, debt: dict[str, Any] | None) -> float:
    """MODE_BOOST when the mode is ON and `cluster` (L1/L2/L3/L4/L5) lands on a priority target:
    an empty payer (L1) or information source (L2), a low-occupancy mechanism (L1), an
    unrepresented asset-factor exposure (L4), session clock or horizon (L5). Order and price
    only: the boost moves a row up the docket, it never touches a gate or a verdict."""
    if not isinstance(debt, dict) or debt.get("breadth_constrained_mode") != "ON":
        return 1.0
    tg = debt.get("priority_targets") if isinstance(debt.get("priority_targets"), dict) else {}
    l1, l2, _l3, l4, l5 = [*str(cluster).split("/"), "", "", "", "", ""][:5]
    sess, _chart, hor = [*l5.split("|"), "", "", ""][:3]

    def hit(key: str, value: str) -> bool:
        vals = tg.get(key)
        return bool(value) and isinstance(vals, list) and value in {str(v) for v in vals}
    if hit("empty_payer_clusters", l1) or hit("empty_information_sources", l2) \
            or hit("low_occupancy_mechanisms", l1) \
            or hit("unrepresented_asset_factor_exposures", l4) \
            or hit("unrepresented_session_clocks", sess) \
            or hit("unrepresented_horizons", hor):
        return MODE_BOOST
    return 1.0


def main(argv: list[str] | None = None) -> int:
    doc = build()
    p = publish(doc)
    print(f"breadth_debt: mode {doc['breadth_constrained_mode']} {doc['mode'].get('fired')}; "
          f"{len(doc['queue'])} debt(s); empty clusters "
          f"{[e['cluster'] for e in doc['empty_clusters']]} -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
