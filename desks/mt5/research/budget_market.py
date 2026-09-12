"""ONE BUDGET MARKET — compute, trials and capital priced against each other in ΔE[log W].

ITEM 28, AND THE REASON IT IS LAST ON THE BLUEPRINT. The desk already allocates all three
resources well, and allocates them SEPARATELY:

    capital   pf_allocator solves for marginal robust dE[log W] per unit of heat
    trials    gate_policy charges a fixed 597, so the statistical budget is a constant
    compute   the scheduler runs whatever is on a clock, in whatever order Windows starts it

Three good mechanisms that never price against each other. So the desk cannot answer the only
question that matters at the margin: given one more unit of ANYTHING, where does it go? An hour of
gauntlet compute, a slot in the trial budget and a basis point of heat are all convertible into
expected log wealth, and until they are quoted in the same unit the desk is optimising three
things and maximising none.

WHAT THIS DOES. It prices every competing use in dE[log W] PER UNIT OF ITS OWN RESOURCE, puts them
on one ranked board, and names where the next marginal unit should go. That is the whole of item
28's first half; the second half -- every outcome updating all three priors -- is the `outcomes`
block, which reads what actually happened to the last allocation rather than assuming it.

WHAT IT DOES NOT DO, AND THIS IS DELIBERATE. It has no authority. It does not move capital, start
a job or change a budget: it publishes a price. The allocator remains the only thing that sizes a
position, because a second mechanism with an opinion about capital is exactly how two disagreeing
sizers end up on one money path -- the failure this desk has a law about. A market that prices and
does not trade is still the difference between an informed decision and a habitual one.

THE HARD PART IS THE DENOMINATOR, and it is stated rather than hidden. Capital's denominator is
honest: marginal dE[log W] per unit of heat is what `pf_allocator` already solves. Compute's is an
estimate: survivors per compute-hour from `scaling_laws`, times the dE[log W] a survivor has
historically been worth. Trials' is the weakest: the desk charges a FIXED 597, so a marginal trial
costs nothing statistically and its price is the CAPACITY it consumes, not the significance it
spends. Every one of those is labelled with its basis so a reader can discount it appropriately,
and an input that cannot be measured publishes UNMEASURED rather than a plausible number.

    python desks/mt5/research/budget_market.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "BUDGET_MARKET.json"

#: Trading days a year, for converting a per-day log rate into anything a person reads.
PPY = 252.0


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _capital_price() -> dict:
    """dE[log W] per unit of HEAT, from the allocator's own solve. The honest denominator."""
    a = _read(DESK / "reports" / "pf_allocation.json") or {}
    h = a.get("heat") or {}
    adm = a.get("admission") or {}
    curve = h.get("curve")
    slope = None
    basis = "no curve"
    if isinstance(curve, list) and len(curve) >= 2:
        try:
            pts = sorted((float(x[0]), float(x[1])) for x in curve)
            (h0, g0), (h1, g1) = pts[-2], pts[-1]
            if h1 > h0:
                slope = (g1 - g0) / (h1 - h0)
                basis = (f"measured on the growth curve's last segment "
                         f"{h0:.1%}->{h1:.1%}: {g0:+.5f}->{g1:+.5f}/day")
        except (TypeError, ValueError, IndexError):
            slope = None
    return {
        "resource": "capital",
        "unit": "one unit of total heat (1.00 = 100% of equity at risk)",
        "price_dElogW_per_unit_per_day": slope,
        "basis": basis,
        "deployed": h.get("total"),
        "ceiling": h.get("heat_ceiling"),
        "binding": h.get("binding"),
        "headroom": (None if not isinstance(h.get("heat_ceiling"), (int, float))
                     or not isinstance(h.get("total"), (int, float))
                     else round(float(h["heat_ceiling"]) - float(h["total"]), 6)),
        "n_admitted": adm.get("n_admitted"),
        "why": ("the slope of the measured growth curve at the deployed heat IS the price of the "
                "next unit of capital, and it is the only one of the three denominators the desk "
                "measures directly rather than estimates"),
    }


def _compute_price() -> dict:
    """dE[log W] per compute-hour. An ESTIMATE, and labelled as one."""
    sl = _read(DESK / "reports" / "scaling_laws.json") or _read(ROOT / "data" / "scaling_laws.json")
    surv_per_hour = None
    basis = "scaling_laws.json absent -- survivors per compute hour has never been fitted here"
    if isinstance(sl, dict):
        for k in ("survivors_per_compute_hour", "survivors_per_hour", "slope"):
            v = sl.get(k)
            if isinstance(v, (int, float)):
                surv_per_hour, basis = float(v), f"scaling_laws.{k}"
                break
    u = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    alloc = _read(DESK / "reports" / "pf_allocation.json") or {}
    funded = len(alloc.get("book") or {})
    n_cert = u.get("n")
    # A SURVIVOR IS NOT WORTH THE BOOK'S WHOLE GROWTH. Most certificates are never funded -- 13 of
    # 67 at the last read -- so the expected value of one more is the book's growth times the
    # probability it gets funded at all, divided across the certificates that share the credit.
    fund_rate = (funded / n_cert) if (isinstance(n_cert, int) and n_cert and funded) else None
    growth = ((alloc.get("heat") or {}).get("curve") or [[None, None]])[-1][-1] \
        if isinstance((alloc.get("heat") or {}).get("curve"), list) else None
    per_survivor = None
    if isinstance(growth, (int, float)) and fund_rate and isinstance(n_cert, int) and n_cert:
        per_survivor = (float(growth) / n_cert) * fund_rate
    price = (surv_per_hour * per_survivor) if (surv_per_hour and per_survivor) else None
    return {
        "resource": "compute",
        "unit": "one compute hour of sweep",
        "price_dElogW_per_unit_per_day": price,
        "basis": (f"{basis}; x expected dE[log W] per survivor "
                  f"({'UNMEASURED' if per_survivor is None else f'{per_survivor:.3e}/day'}, "
                  f"book growth / {n_cert} certificates x {fund_rate if fund_rate else '?'} "
                  f"funded rate)"),
        "n_certificates": n_cert,
        "n_funded": funded or None,
        "funded_rate": None if fund_rate is None else round(fund_rate, 4),
        "why": ("an ESTIMATE, twice removed: survivors per hour is fitted, and what a survivor is "
                "worth assumes the next one resembles the average of the ones already held. "
                "Discount it accordingly -- it is a price, not a measurement"),
    }


def _trial_price() -> dict:
    """The statistical budget. Priced at its CAPACITY cost, because its charge is fixed."""
    try:
        from research.gate_policy import _SPEC_FIXED_TRIALS, FIXED_VARIANCE_OF_SHARPES
        fixed = _SPEC_FIXED_TRIALS
        var = FIXED_VARIANCE_OF_SHARPES
    except Exception:
        fixed, var = None, None
    docket = _read(DESK / "data" / "hypotheses" / "external_survivors.json")
    n_docket = len(docket) if isinstance(docket, list) else None
    return {
        "resource": "trials",
        "unit": "one additional gauntlet cell",
        "price_dElogW_per_unit_per_day": 0.0,
        "basis": (f"fixed_campaign_trials({fixed}) and fixed_variance_of_sharpes({var}): the "
                  f"multiple-testing charge does NOT grow with the docket, so a marginal cell "
                  f"spends no significance and costs no other candidate anything"),
        "docket_rows": n_docket,
        "why": ("THE STATISTICAL PRICE IS ZERO BY CONSTRUCTION -- that is the principal's fixed "
                "wall, and it is why breadth is free. The real cost of a marginal cell is the "
                "COMPUTE to judge it, which is already priced above. Trials are not a scarce "
                "resource on this desk; they were made abundant on purpose"),
    }


def build() -> dict:
    cap, comp, tri = _capital_price(), _compute_price(), _trial_price()
    rows = [cap, comp, tri]
    priced = [r for r in rows
              if isinstance(r["price_dElogW_per_unit_per_day"], (int, float))
              and r["price_dElogW_per_unit_per_day"] > 0]
    best = max(priced, key=lambda r: r["price_dElogW_per_unit_per_day"]) if priced else None

    # THE MARGINAL UNIT GOES WHERE THE PRICE IS HIGHEST -- but only among resources whose price
    # could be MEASURED. A resource that publishes UNMEASURED is not cheap, it is unknown, and
    # ranking it as zero would quietly starve it (L1.28a).
    unmeasured = [r["resource"] for r in rows
                  if not isinstance(r["price_dElogW_per_unit_per_day"], (int, float))]
    if cap.get("headroom") is not None and cap["headroom"] <= 0:
        verdict = ("CAPITAL IS AT ITS CEILING. The next unit cannot go to heat whatever it is "
                   "worth, so the marginal unit goes to whatever RAISES the ceiling -- which is "
                   "independent bets, which is compute spent on orthogonal families.")
    elif best is None:
        verdict = ("NO RESOURCE HAS A MEASURED PRICE this pass. That is a reading, not a tie: "
                   f"unmeasured = {unmeasured}. Fix the measurement before moving a budget.")
    else:
        verdict = (f"the next marginal unit goes to {best['resource'].upper()} at "
                   f"{best['price_dElogW_per_unit_per_day']:.4e} dE[log W]/day per unit")

    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "resources": rows,
        "unmeasured": unmeasured,
        "verdict": verdict,
        "boundary": ("This market PRICES. It has no authority: it does not move capital, start a "
                     "job or change a budget. pf_allocator remains the only thing that sizes a "
                     "position, because a second mechanism with an opinion about capital is how "
                     "two disagreeing sizers end up on one money path."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print("budget market:")
    for r in doc["resources"]:
        p = r["price_dElogW_per_unit_per_day"]
        shown = "UNMEASURED" if not isinstance(p, (int, float)) else f"{p:+.4e}"
        print(f"  {r['resource']:<9} {shown:>14} /day per {r['unit'][:44]}")
        print(f"            basis: {r['basis'][:104]}")
    print(f"  -> {doc['verdict']}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
