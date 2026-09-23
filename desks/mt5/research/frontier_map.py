"""F9 -- ONE MAP OF WHERE THIS DESK HAS LOOKED, and therefore of where it has not.

THE PRINCIPAL, 2026-09-12:

    ONE global map of data x mechanism x market x horizon x state x representation x execution x
    payoff geometry, with occupancy/confidence/expected value per region, DIRECTLY controlling
    research allocation.

THE GAP, AS THE LEDGER STATES IT: alpha_frontier, EVIG, transfer classes, crowding hazard, tail
complementarity, null calibration and strategy DNA all exist; the single authoritative map does
not. The desk also holds a 7x9 mechanism-by-axis matrix in side_channels -- genuinely useful, and
two of the eight dimensions.

WHY EIGHT DIMENSIONS AND NOT TWO. A desk that has tested momentum on FX has not tested momentum on
FX at a swing horizon with a resting entry and a convex payoff. Those are different experiments
with different answers, and a two-dimensional map records them as one filled cell -- which is how
"we have covered momentum" becomes true on paper and false in fact. The eight axes are the ones
that actually change an answer, and they are derived from each cell's OWN record rather than
declared by hand.

THE MAP IS OF OCCUPIED REGIONS, NOT OF THE CROSS PRODUCT. The full product is hundreds of
thousands of regions and enumerating it would produce a map whose every cell is empty -- the
denominator trick the laws forbid, dressed as coverage. So the map is built from what the desk has
actually judged, and the FRONTIER is computed as the regions ONE STEP from an occupied one: a
neighbour that differs on exactly one axis. That is a reachable research target rather than an
imaginary one, and there are few enough of them to rank.

THREE NUMBERS PER REGION, and the third is the one that decides:

    OCCUPANCY    cells judged there. Zero is a real reading and sorts to the FRONTIER, not out.
    CONFIDENCE   the WIDTH of the Wilson interval on that region's certification rate. A region
                 with one cell has no confidence however that cell went.
    VALUE        the posterior mean rate under a Beta prior centred on the desk's base rate, and
                 the expected INFORMATION from one more cell there. A region the desk is already
                 certain about is worth nothing more, however good it is.

IT CONTROLS ALLOCATION BY BEING READ. The map publishes a weight per region and the meta-
controller consumes it; nothing here schedules or refuses anything on its own. A map that acted
would be a second capital authority, and this desk allows exactly one.

    python desks/mt5/research/frontier_map.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
OUT = DESK / "reports" / "FRONTIER_MAP.json"

#: The eight axes, each with a SMALL vocabulary. Small on purpose: an axis with forty values makes
#: every region singleton, and a map of singletons measures nothing but the docket's size.
AXES: tuple[str, ...] = ("data", "mechanism", "market", "horizon", "state",
                         "representation", "execution", "payoff")

#: Which family maps to which mechanism SHAPE. Derived from the family's own name and cross-checked
#: against alpha_grammar's shape vocabulary; a family whose shape cannot be read from its name is
#: UNCLASSIFIED, and UNCLASSIFIED is a region of its own rather than a guess folded into another.
_MECH: tuple[tuple[str, str], ...] = (
    ("breakout", "breakout"), ("range", "reversion"), ("reversion", "reversion"),
    ("reversal", "reversion"), ("momentum", "momentum"), ("trend", "momentum"),
    ("drift", "momentum"), ("carry", "carry"), ("swap", "carry"),
    ("cot", "positioning"), ("positioning", "positioning"),
    ("relative_value", "relative_value"), ("residual", "relative_value"),
    ("pca", "relative_value"), ("lead_lag", "cross_asset"), ("cross_asset", "cross_asset"),
    ("correlation", "cross_asset"), ("triangle", "cross_asset"),
    ("vol", "volatility"), ("squeeze", "volatility"), ("gap", "gap"),
    ("session", "session"), ("hour", "session"), ("dow", "session"), ("monday", "session"),
    ("event", "event"), ("macro", "macro"), ("news", "event"),
    ("discovered", "mined_anomaly"), ("anomal", "mined_anomaly"),
)

#: Which SOURCE implies which representation lane. The desk now has three and they are not
#: interchangeable: a grammar expression can be read and falsified by an economic argument, a
#: mined anomaly cannot, and a learned representation has no unit at all.
_REPR: tuple[tuple[str, str], ...] = (
    ("joint_evolution", "joint_genome"), ("research_tree", "joint_genome"),
    ("alpha_evolution", "symbolic_grammar"), ("orthogonal_sweep", "symbolic_grammar"),
    ("miner", "mined_anomaly"), ("anomal", "mined_anomaly"),
    ("external", "external_claim"), ("deep_forest", "external_claim"),
    ("kimi", "seat_proposal"), ("deepseek", "seat_proposal"), ("seat", "seat_proposal"),
)

#: Prior strength for a region's Beta, in pseudo-observations of the desk base rate. Two is weak
#: enough not to drown a real count and strong enough that a one-cell region cannot claim a rate.
PRIOR_N = 2.0

#: Regions with fewer cells than this are reported but never given a confident value -- their
#: interval is published instead, which is the honest form of "we do not know yet".
MIN_CELLS_FOR_RATE = 15


def _load(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _first_match(text: str, table: tuple[tuple[str, str], ...], default: str) -> str:
    low = text.lower()
    for needle, value in table:
        if needle in low:
            return value
    return default


def _asset_class(symbol: str) -> str:
    try:
        from research.universe_policy import asset_class_of
        return str(asset_class_of(symbol) or "UNCLASSIFIED")
    except Exception:
        return "UNCLASSIFIED"


def _horizon(params: dict[str, Any]) -> str:
    """Bars the position may live, bucketed.

    Absent is UNSPECIFIED and never a default of "intraday": a cell whose horizon nobody recorded
    has not been tested at any horizon, and filing it under the commonest one would fill a region
    with experiments that were never run there.
    """
    for k in ("ttl_bars", "hold_bars", "horizon", "hold"):
        v = params.get(k)
        if isinstance(v, (int, float)) and v > 0:
            n = float(v)
            return ("scalp" if n <= 4 else "intraday" if n <= 24
                    else "swing" if n <= 120 else "position")
    return "UNSPECIFIED"


def _state(params: dict[str, Any]) -> str:
    keys = {str(k).lower() for k in params}
    if {"state_band"} & keys:
        return "volatility_band"
    if {"session", "hour", "range_start", "window"} & keys:
        return "session"
    if {"vol_gate_q", "regime", "atr_gate"} & keys:
        return "volatility_gate"
    return "unconditional"


def _execution(params: dict[str, Any]) -> str:
    t = params.get("trigger_atr")
    if isinstance(t, (int, float)):
        return "resting" if float(t) > 0 else "market"
    if "wait_bars" in params or "rest_bars" in params:
        return "resting"
    return "UNSPECIFIED"


def _payoff(params: dict[str, Any]) -> str:
    """The trade's own geometry.

    A 3R target and a 1R target are different bets on the same signal, and folding them into one
    region is how a map says a question was answered when the other half was never asked.
    """
    for k in ("rr", "rr_mult", "reward_risk"):
        v = params.get(k)
        if isinstance(v, (int, float)) and v > 0:
            r = float(v)
            return "convex" if r >= 2.0 else "linear" if r >= 1.0 else "concave"
    return "UNSPECIFIED"


def _data_need(family: str, source: str) -> str:
    blob = f"{family} {source}".lower()
    if any(k in blob for k in ("cot", "macro", "ecb", "fred", "bis", "event", "news")):
        return "external_axis"
    if any(k in blob for k in ("tape", "tick", "depth", "swap", "broker")):
        return "microstructure"
    if any(k in blob for k in ("lead_lag", "cross_asset", "correlation", "pca",
                               "relative_value", "triangle", "residual")):
        return "multi_instrument_price"
    return "single_instrument_price"


def _region(row: dict[str, Any]) -> tuple[str, ...]:
    fam = str(row.get("family") or "")
    src = str(row.get("source") or "")
    raw = row.get("params")
    params: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    return (
        _data_need(fam, src),
        _first_match(fam, _MECH, "UNCLASSIFIED"),
        _asset_class(str(row.get("symbol") or "")),
        _horizon(params),
        _state(params),
        _first_match(src or fam, _REPR, "UNCLASSIFIED"),
        _execution(params),
        _payoff(params),
    )


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    z, ph = 1.96, k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _beta_entropy(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    def _digamma(x: float) -> float:
        r = 0.0
        while x < 6:
            r -= 1.0 / x
            x += 1
        f = 1.0 / (x * x)
        return r + math.log(x) - 0.5 / x + f * (
            -1 / 12.0 + f * (1 / 120.0 + f * (-1 / 252.0 + f * (1 / 240.0))))
    return (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
            - (a - 1) * _digamma(a) - (b - 1) * _digamma(b) + (a + b - 2) * _digamma(a + b))


def _info_gain(a: float, b: float) -> float:
    n = a + b
    if n <= 0:
        return 0.0
    p = a / n
    return max(0.0, _beta_entropy(a, b)
               - (p * _beta_entropy(a + 1, b) + (1 - p) * _beta_entropy(a, b + 1)))


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rows = _load(DOCKET)
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    if len(rows) < 200:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"{len(rows)} docket row(s) -- too few to map anything"}

    surv = _load(SURVIVORS) or {}
    pos: set[tuple[str, str, str]] = set()
    for r in (surv.get("survivors") or {}).values():
        if not isinstance(r, dict):
            continue
        sp = r.get("shadow_spec") or {}
        if sp.get("symbol") and sp.get("family"):
            pos.add((str(sp["symbol"]), str(sp["family"]),
                     json.dumps(sp.get("params"), sort_keys=True)))

    agg: dict[tuple[str, ...], dict[str, int]] = {}
    for r in rows:
        reg = _region(r)
        a = agg.setdefault(reg, {"n": 0, "k": 0})
        a["n"] += 1
        key = (str(r.get("symbol") or ""), str(r.get("family") or ""),
               json.dumps(r.get("params"), sort_keys=True))
        if key in pos:
            a["k"] += 1

    n_all = sum(a["n"] for a in agg.values())
    k_all = sum(a["k"] for a in agg.values())
    base = k_all / n_all if n_all else 0.0

    regions: list[dict[str, Any]] = []
    for reg, a in agg.items():
        alpha = PRIOR_N * base + a["k"]
        beta = PRIOR_N * (1 - base) + (a["n"] - a["k"])
        lo, hi = _wilson(a["k"], a["n"])
        regions.append({
            "region": dict(zip(AXES, reg, strict=True)),
            "key": "|".join(reg),
            "occupancy": a["n"], "certificates": a["k"],
            "rate": round(a["k"] / a["n"], 6) if a["n"] else None,
            "ci95": [round(lo, 6), round(hi, 6)],
            "confidence_width": round(hi - lo, 6),
            "posterior_value": round(alpha / (alpha + beta), 6),
            "info_gain_nats": round(_info_gain(alpha, beta), 6),
            "rate_is_quotable": a["n"] >= MIN_CELLS_FOR_RATE,
        })
    regions.sort(key=lambda r: -int(r["occupancy"]))

    # THE FRONTIER: regions ONE AXIS from an occupied one. Not the cross product -- enumerating
    # hundreds of thousands of empty regions would be a coverage number with an invented
    # denominator, which the laws call out by name. A one-step neighbour is a reachable
    # experiment: the desk already has everything it needs except that one choice.
    occupied = set(agg)
    vocab: dict[str, set[str]] = {ax: set() for ax in AXES}
    for reg in occupied:
        for ax, v in zip(AXES, reg, strict=True):
            vocab[ax].add(v)
    frontier: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for reg in sorted(occupied, key=lambda r: -agg[r]["n"])[:120]:
        parent = agg[reg]
        pa = PRIOR_N * base + parent["k"]
        pb = PRIOR_N * (1 - base) + (parent["n"] - parent["k"])
        for i, ax in enumerate(AXES):
            for v in vocab[ax]:
                if v == reg[i]:
                    continue
                cand = (*reg[:i], v, *reg[i + 1:])
                if cand in occupied or cand in seen:
                    continue
                seen.add(cand)
                # A NEIGHBOUR INHERITS HALF ITS PARENT'S EVIDENCE and nothing more. It is one
                # choice away, which is a reason to look and never a reason to believe.
                a2, b2 = PRIOR_N * base + 0.5 * pa, PRIOR_N * (1 - base) + 0.5 * pb
                frontier.append({
                    "region": dict(zip(AXES, cand, strict=True)),
                    "key": "|".join(cand),
                    "one_step_from": "|".join(reg),
                    "changed_axis": ax, "from_value": reg[i], "to_value": v,
                    "parent_occupancy": parent["n"], "parent_certificates": parent["k"],
                    "inherited_value": round(a2 / (a2 + b2), 6),
                    "info_gain_nats": round(_info_gain(a2, b2), 6),
                })
    frontier.sort(key=lambda r: (-float(r["info_gain_nats"]),
                                 -float(r["inherited_value"])))

    quotable = [r for r in regions if r["rate_is_quotable"]]
    productive = sorted((r for r in quotable if r["certificates"] > 0),
                        key=lambda r: -float(r["rate"] or 0))
    barren = [r for r in quotable if r["certificates"] == 0 and r["occupancy"] >= 100]
    barren.sort(key=lambda r: -int(r["occupancy"]))

    # THE ALLOCATION WEIGHTS. Published, not applied: the meta-controller reads them. A map that
    # scheduled would be a second authority over research compute and this desk allows one.
    total_ig = sum(float(r["info_gain_nats"]) for r in regions) or 1.0
    weights = {r["key"]: round(float(r["info_gain_nats"]) / total_ig, 8)
               for r in regions[:200]}

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "axes": list(AXES),
        "coverage": {
            "n_cells_mapped": n_all, "n_certificates": k_all,
            "base_rate": round(base, 6),
            "n_regions_occupied": len(agg),
            "n_regions_with_quotable_rate": len(quotable),
            "n_frontier_regions_one_step": len(frontier),
            "vocabulary_size": {ax: len(v) for ax, v in vocab.items()},
        },
        "most_occupied": regions[:15],
        "most_productive": productive[:12],
        "barren_and_expensive": [
            {**r, "note": (f"{r['occupancy']} cells judged, 0 certificates, upper bound "
                           f"{r['ci95'][1]:.4%}")} for r in barren[:12]],
        "frontier": frontier[:40],
        "allocation_weights": weights,
        "denominator_honesty": (
            "THERE IS NO COVERAGE PERCENTAGE HERE ON PURPOSE. The cross product of these eight "
            "axes is hundreds of thousands of regions, nearly all of which are meaningless "
            "combinations; dividing by it would manufacture a coverage number whose denominator "
            "was invented. Occupancy is counted, the frontier is the reachable one-step "
            "neighbourhood, and neither is presented as a fraction of an imaginary whole."),
        "boundary": (
            "IT CONTROLS ALLOCATION BY BEING READ. The weights are published and the "
            "meta-controller consumes them; nothing here schedules, refuses or sizes. A map that "
            "acted would be a second authority over research compute."),
        "why": (
            "a desk that has tested momentum on FX has not tested momentum on FX at a swing "
            "horizon with a resting entry and a convex payoff. Those are different experiments "
            "with different answers, and a two-dimensional map records them as one filled cell -- "
            "which is how 'we have covered momentum' becomes true on paper and false in fact."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"frontier map: {doc.get('status')} -- {doc.get('why')}")
        return 0
    c = doc["coverage"]
    print(f"frontier map: OK   {c['n_cells_mapped']} cell(s) in {c['n_regions_occupied']} "
          f"occupied region(s); base rate {c['base_rate']:.4%}")
    print(f"  {c['n_regions_with_quotable_rate']} region(s) hold enough cells to quote a rate; "
          f"{c['n_frontier_regions_one_step']} region(s) are ONE axis away")
    print("  most productive:")
    for r in doc["most_productive"][:5]:
        g = r["region"]
        print(f"    {float(r['rate']):.2%} of {r['occupancy']:<5} "
              f"{g['mechanism']:<16} {g['market']:<12} {g['horizon']:<11} {g['payoff']}")
    print("  barren and expensive:")
    for r in doc["barren_and_expensive"][:5]:
        g = r["region"]
        print(f"    {r['occupancy']:<6} cells 0 certs  {g['mechanism']:<16} {g['market']:<12} "
              f"{g['representation']:<16} upper {r['ci95'][1]:.3%}")
    print("  frontier -- one axis from somewhere the desk has been:")
    for r in doc["frontier"][:6]:
        print(f"    {r['info_gain_nats']:.4f} nats  change {r['changed_axis']}: "
              f"{r['from_value']} -> {r['to_value']}  (parent {r['parent_occupancy']} cells, "
              f"{r['parent_certificates']} certs)")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
