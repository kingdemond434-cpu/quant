"""EVERY SCIENTIFIC FACTORY HAS A MEASURED CONTRACT, AND COMPUTE FOLLOWS IT.

    "Scientific factories measured: every factory has a contract: candidates produced, novelty
     rate, falsification rate, survivor yield, independent-alpha yield, compute cost, incremental
     E[log W]; compute follows yield."                               -- the principal, 2026-09-29

THE SEVEN TERMS ALREADY EXIST ON THIS DESK, IN THREE ARTIFACTS THAT NEVER MET:

    PRODUCTIVITY_CENSUS.json   per producer: raw cells, unique cells, cells judged, cheap-stage
                               survivors, certificates and compute hours -- the funnel
    RESEARCH_ROI.json          scientist_roi per generator: dE[log W] credited back along the
                               provenance walk (the allocator's own marginal numbers)
    ALPHA_RANK.json            per producer: the marginal EFFECTIVE INDEPENDENT ALPHA RANK its
                               certificates add to the certified set (the north star)

This joins them into ONE contract per producer, every term either a number or UNMEASURED with its
reason (L1.28a -- a term nobody measured is never a zero), and publishes the contract's own
coverage so the share of producers with a complete contract is a number that can only be pushed
up. The per-hour rates are then rank-blended into one YIELD SCORE per producer and folded onto the
hourly legs that run them (`leg_yield`), which `cycle_pricing` reads as a price source: spare
seconds follow measured yield.

ONE-SIDED BY CONSTRUCTION. The yield score is a PRICE for ADDITIONAL compute; the consumer
guarantees every leg its base budget (the principal's standing order: no miner is ever starved or
throttled), so a low score costs a producer nothing it already has.

    python desks/mt5/research/factory_contracts.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA_VERSION = "factory_contracts/1"
CENSUS = DESK / "reports" / "PRODUCTIVITY_CENSUS.json"
ROI = DESK / "reports" / "RESEARCH_ROI.json"
ALPHA_RANK = DESK / "reports" / "ALPHA_RANK.json"
OUT = DESK / "reports" / "FACTORY_CONTRACTS.json"
UNMEASURED = "UNMEASURED"
#: An input older than this is a claim about a desk that no longer exists.
MAX_AGE_H = 48.0

TERMS: tuple[str, ...] = ("candidates_produced", "novelty_rate", "falsification_rate",
                          "survivor_yield", "independent_alpha_yield", "compute_cost_hours",
                          "incremental_elogw")
#: The per-compute-hour rates the yield score blends. Each is a thing an hour of THIS producer's
#: compute bought; volume without a denominator is never a yield.
RATES: tuple[str, ...] = ("unique_cells_per_hour", "survivors_per_hour",
                          "independent_alpha_per_hour", "elogw_per_hour")


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _age_h(doc: dict[str, Any]) -> float | None:
    for k in ("at", "generated_utc"):
        try:
            t = datetime.fromisoformat(str(doc.get(k)).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return (datetime.now(tz=UTC) - t).total_seconds() / 3600.0
    return None


def norm(name: Any) -> str:
    """The census's own producer key rule: `exe:` and path shapes collapse onto the stem."""
    raw = str(name or "").strip()
    if raw.startswith("exe:"):
        raw = raw[4:]
    if "/" in raw or raw.endswith(".py") or raw.endswith(".json"):
        raw = Path(raw).stem
    return raw.strip().lower()


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _um(why: str) -> dict[str, str]:
    return {"verdict": UNMEASURED, "why": why}


def _fresh(doc: dict[str, Any], name: str) -> tuple[bool, str]:
    if not doc:
        return False, f"{name} absent or unreadable"
    age = _age_h(doc)
    if age is None:
        return False, f"{name} carries no readable stamp"
    if age > MAX_AGE_H:
        return False, f"{name} is {age:.1f}h old (max {MAX_AGE_H:.0f}h)"
    return True, f"{name} {age:.1f}h old"


def contract(row: dict[str, Any], roi_row: dict[str, Any] | None,
             ind: float | None, ind_why: str) -> dict[str, Any]:
    """One producer's seven-term contract from its census row, ROI row and alpha-rank credit.
    PURE: every input is passed in, so the suite pins the arithmetic without touching disk."""
    f = row.get("funnel") if isinstance(row.get("funnel"), dict) else {}
    raw, uniq = _num(f.get("raw_cells")), _num(f.get("unique_cells"))
    judged = _num(f.get("cells_judged"))
    surv = _num(f.get("cheap_survivors"))
    certs = _num(f.get("certificates"))
    hours = _num(row.get("compute_hours"))
    c: dict[str, Any] = {}
    c["candidates_produced"] = raw if raw is not None else _um("census raw_cells unmeasured")
    c["novelty_rate"] = (round(uniq / raw, 6) if raw and uniq is not None else
                         _um("no raw cells to take unique cells over"))
    if judged:
        c["falsification_rate"] = (round(max(0.0, judged - (surv or 0.0)) / judged, 6)
                                   if surv is not None else _um("cheap survivors unmeasured"))
        c["survivor_yield"] = (round((certs or 0.0) / judged, 6) if certs is not None else
                               _um("certificates unmeasured"))
    else:
        c["falsification_rate"] = _um("no cell of this producer has been judged")
        c["survivor_yield"] = _um("no cell of this producer has been judged")
    c["independent_alpha_yield"] = round(ind, 6) if ind is not None else _um(ind_why)
    c["compute_cost_hours"] = hours if hours is not None else _um(
        "no compute recorded for this producer in the census window")
    elog = _num((roi_row or {}).get("credited_delta_elogw"))
    c["incremental_elogw"] = elog if elog is not None else _um(
        "no scientist_roi row for this producer in RESEARCH_ROI.json")
    rates: dict[str, float | None] = dict.fromkeys(RATES)
    if hours and hours > 0:
        rates["unique_cells_per_hour"] = round(uniq / hours, 6) if uniq is not None else None
        rates["survivors_per_hour"] = round(surv / hours, 6) if surv is not None else None
        rates["independent_alpha_per_hour"] = round(ind / hours, 6) if ind is not None else None
        rates["elogw_per_hour"] = round(elog / hours, 6) if elog is not None else None
    n_meas = sum(1 for t in TERMS if not isinstance(c[t], dict))
    return {"contract": c, "rates": rates, "n_terms_measured": n_meas,
            "complete": n_meas == len(TERMS)}


def _pct_ranks(values: dict[str, float]) -> dict[str, float]:
    """Average-rank percentiles in [0, 1]; ties share a rank (see cycle_pricing._rank01)."""
    if not values:
        return {}
    order = sorted(values, key=lambda k: values[k])
    n = len(order)
    if n == 1:
        return {order[0]: 0.5}
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + j) / 2.0 / (n - 1)
        i = j + 1
    return out


def yield_scores(rates: dict[str, dict[str, float | None]]) -> dict[str, float]:
    """One score per producer: the mean percentile over the rates it has MEASURED. A producer with
    no measured rate gets no score (unpriced), never a zero."""
    per_rate = {r: _pct_ranks({p: float(v[r]) for p, v in rates.items()
                               if isinstance(v.get(r), (int, float))}) for r in RATES}
    out: dict[str, float] = {}
    for p in rates:
        got = [per_rate[r][p] for r in RATES if p in per_rate[r]]
        if got:
            out[p] = round(sum(got) / len(got), 6)
    return out


def _legs() -> set[str]:
    try:
        from libs.research.layers import LEG_LAYER
        return set(LEG_LAYER)
    except Exception:
        return set()


def leg_of(key: str, clock: Any, legs: set[str]) -> str | None:
    """The hourly leg that RUNS this producer, from its own name or its declared clock. Nothing
    fuzzy: an exact leg name, or `hourly_cycle:<leg>` inside the clock string."""
    k = key.replace("-", "_")
    if k in legs:
        return k
    s = str(clock or "")
    for tok in s.replace(",", " ").split():
        if tok.startswith("hourly_cycle:"):
            leg = tok.split(":", 1)[1].strip()
            if leg in legs:
                return leg
    return None


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    census, roi, rank = _read(CENSUS), _read(ROI), _read(ALPHA_RANK)
    inputs = {n: {"fresh": ok, "why": why} for n, (ok, why) in (
        ("PRODUCTIVITY_CENSUS", _fresh(census, CENSUS.name)),
        ("RESEARCH_ROI", _fresh(roi, ROI.name)),
        ("ALPHA_RANK", _fresh(rank, ALPHA_RANK.name)))}
    rows = census.get("producers") if inputs["PRODUCTIVITY_CENSUS"]["fresh"] else None
    if not isinstance(rows, list) or not rows:
        return {"schema_version": SCHEMA_VERSION, "at": now, "status": UNMEASURED,
                "inputs": inputs, "producers": {}, "leg_yield": {},
                "why": ("no fresh PRODUCTIVITY_CENSUS.json producer rows: the funnel every "
                        "contract is built on is unmeasured on this host")}
    sci = ((roi.get("scientist_roi") or {}) if inputs["RESEARCH_ROI"]["fresh"] else {})
    roi_by = {norm(k): v for k, v in sci.items() if isinstance(v, dict)}
    ind_by: dict[str, float] = {}
    ind_why = inputs["ALPHA_RANK"]["why"]
    if inputs["ALPHA_RANK"]["fresh"] and rank.get("status") == "MEASURED":
        for k, v in (rank.get("producer_independent_alpha") or {}).items():
            if _num(v) is not None:
                ind_by[norm(k)] = float(v)
        ind_why = ("no certificate of this producer is in the certified set ALPHA_RANK.json "
                   "measured")
    elif inputs["ALPHA_RANK"]["fresh"]:
        ind_why = f"ALPHA_RANK.json is {rank.get('status')}: {rank.get('why')}"
    legs = _legs()
    out: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = norm(row.get("key") or row.get("producer"))
        if not key:
            continue
        c = contract(row, roi_by.get(key), ind_by.get(key), ind_why)
        c["producer"] = row.get("producer")
        c["leg"] = leg_of(key, row.get("clock"), legs)
        out[key] = c
    scores = yield_scores({k: v["rates"] for k, v in out.items()})
    for k, s in scores.items():
        out[k]["yield_score"] = s
    leg_yield: dict[str, float] = {}
    for k, v in out.items():
        if v.get("leg") and k in scores:
            leg_yield[v["leg"]] = max(leg_yield.get(v["leg"], 0.0), scores[k])
    # THE NORTH STAR AS ITS OWN PRICE (2026-09-30): marginal effective independent alpha rank
    # per compute hour, per leg, published beside the blended yield score so `cycle_pricing`
    # can weight it directly instead of as one quarter of a percentile mean.
    leg_alpha: dict[str, float] = {}
    for v in out.values():
        r = (v.get("rates") or {}).get("independent_alpha_per_hour")
        if v.get("leg") and _num(r) is not None:
            leg_alpha[v["leg"]] = max(leg_alpha.get(v["leg"], float("-inf")), float(r))
    n = len(out)
    coverage = {t: round(sum(1 for v in out.values() if not isinstance(v["contract"][t], dict))
                         / n, 4) if n else 0.0 for t in TERMS}
    ranked = sorted(scores, key=lambda k: -scores[k])
    return {
        "schema_version": SCHEMA_VERSION, "at": now, "status": "MEASURED", "inputs": inputs,
        "n_producers": n,
        "n_complete_contracts": sum(1 for v in out.values() if v["complete"]),
        "n_priced": len(scores),
        "term_coverage": coverage,
        "terms": list(TERMS), "rates": list(RATES),
        "leg_yield": dict(sorted(leg_yield.items(), key=lambda kv: -kv[1])),
        "leg_independent_alpha": dict(sorted(leg_alpha.items(), key=lambda kv: -kv[1])),
        "top_by_yield": [{"producer": k, "yield_score": scores[k], "leg": out[k].get("leg"),
                          "rates": out[k]["rates"]} for k in ranked[:15]],
        "producers": out,
        "rule": ("every producer's contract is its measured funnel, its credited dE[log W] and "
                 "its marginal independent alpha rank; the yield score is the mean percentile of "
                 "its measured per-hour rates; leg_yield prices ADDITIONAL compute only -- the "
                 "consumer floors every leg at its base budget"),
        "consumers": ["desks/mt5/research/cycle_pricing.py (price source `factory_contracts`)"],
    }


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def leg_yield(path: Path | None = None) -> tuple[dict[str, float], str]:
    """The consumer's door: {leg: yield score} from a fresh artifact, or {} and why."""
    doc = _read(path or OUT)
    if not doc:
        return {}, "FACTORY_CONTRACTS.json absent"
    ok, why = _fresh(doc, "FACTORY_CONTRACTS.json")
    if not ok:
        return {}, why
    ly = doc.get("leg_yield")
    if not isinstance(ly, dict) or not ly:
        return {}, "FACTORY_CONTRACTS.json prices no hourly leg"
    return {str(k): float(v) for k, v in ly.items() if _num(v) is not None}, ""


def leg_alpha_rank(path: Path | None = None) -> tuple[dict[str, float], str]:
    """{leg: marginal independent alpha rank per compute hour} from a fresh artifact, or {} and
    why. The north star's own price source for `cycle_pricing`."""
    doc = _read(path or OUT)
    if not doc:
        return {}, "FACTORY_CONTRACTS.json absent"
    ok, why = _fresh(doc, "FACTORY_CONTRACTS.json")
    if not ok:
        return {}, why
    la = doc.get("leg_independent_alpha")
    if not isinstance(la, dict) or not la:
        return {}, "no leg carries a measured independent-alpha rate (ALPHA_RANK.json unread)"
    return {str(k): float(v) for k, v in la.items() if _num(v) is not None}, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"factory contracts: {doc['status']}  {doc.get('n_producers', 0)} producer(s), "
          f"{doc.get('n_complete_contracts', 0)} complete, {doc.get('n_priced', 0)} priced, "
          f"{len(doc.get('leg_yield') or {})} leg(s) priced")
    for t, v in (doc.get("term_coverage") or {}).items():
        print(f"   coverage {t:<26} {v}")
    if doc.get("why"):
        print(f"   {doc['why']}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
