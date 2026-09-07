"""CAPACITY: what an edge is worth AT THIS ACCOUNT'S SIZE, which is not what it is worth at any.

    py -3 research/capacity.py            # write reports/CAPACITY.json
    py -3 research/capacity.py --report   # print, write nothing

ONE OF THE TWELVE CAPABILITY GROUPS NO MODULE ON THIS TREE OWNED. `ontology.unaddressed()` has
been naming it for weeks: "what an edge is worth AT OUR SIZE". Nothing measured it, so every
admission decision was made as though an edge's value were a property of the edge alone.

THE INSTITUTIONAL CAPACITY QUESTION IS THE WRONG ONE HERE, AND GETTING THAT BACKWARDS IS THE
POINT. A large fund asks "at what size does my own order move the price against me" -- an UPPER
bound set by market impact. At EUR 742 on 0.01-lot minimums this desk has no measurable impact
whatsoever, and importing the institutional machinery would be pure complexity rent: modelling
the market impact of orders that have none.

The binding constraint at this size is the opposite one, and it is a LOWER bound:

    the venue's minimum lot forces MORE risk per trade than the policy asks for

`decision_core.realised_q` exists precisely because of this -- "a book configured for 0.75% could
run at 5.9% with nothing in the code, the log or the state file ever saying so". That is the
capacity question this desk actually has, it is exactly computable from numbers already on the
tree, and nothing was reporting it per sleeve.

WHAT IS MEASURED AND WHAT IS REFUSED, kept separate because they are not equally knowable:

  FLOOR   exact. `min_lot_risk_eur(symbol, dist)` is the EUR at risk on one minimum lot, so the
          equity below which the floor binds is `min_lot_risk_eur / q_target`. Above that
          equity the sleeve runs its policy; below it, the venue overrides the policy upward and
          the account is running a risk nobody chose.
  CEILING UNMEASURED, and said so rather than estimated. Impact needs realised fills and
          `execution.matched_fills` is 0 -- nothing has ever filled. A capacity ceiling derived
          from a cost model nobody has validated against a fill is a number that would be
          believed and should not be. UNMEASURED IS A VERDICT, NOT A ZERO.

THE SMALL-CAPITAL ADVANTAGE IS A REAL ASSET AND IS REPORTED AS ONE. An edge too small for a fund
running billions is not a worse edge here -- it is the one kind this desk can hold uncontested.
`headroom_multiple` says how much this account could grow before a sleeve's floor stops binding,
which is the honest version of "how long does this edge remain ours".

WIRING. Producer: this module, hourly. Storage: reports/CAPACITY.json. Consumer: the issue board
via `over_risked()`, which raises a sleeve whose realised risk exceeds its policy by more than
`OVER_RISK_TOLERANCE`. It does NOT size anything: changing the allocator is a money-path edit and
belongs in its own reviewed change, not smuggled in behind a new measurement organ.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
for _p in (str(BASE), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as core  # noqa: E402

REPORT = BASE / "reports" / "CAPACITY.json"

#: How far realised risk may exceed the policy before it is an issue rather than a rounding edge.
#: 1.25 = a quarter more risk than chosen. Not a threshold anything is allowed to relax to make a
#: board go green: it decides what gets REPORTED, and reporting less over-risk does not make an
#: account safer.
OVER_RISK_TOLERANCE = 1.25

#: Account sizes the capacity curve is evaluated at. Spans this desk's plausible next two orders
#: of magnitude, so the report answers "when does this stop binding" rather than only "does it".
LADDER_EUR = (250.0, 500.0, 750.0, 1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0, 100_000.0)


def floor_binding_equity(q_target: float, symbol: str, dist_price: float | None = None,
                         info: object | None = None) -> float:
    """Equity below which the minimum lot forces more risk than `q_target`.

    Exactly `min_lot_risk_eur / q_target`: one minimum lot puts that many EUR at risk, and any
    account smaller than that divided by the target fraction is running above policy. Returns
    `inf` for a non-positive target, because a sleeve targeting no risk is always over-sized by
    any lot at all -- reporting a finite number there would invite the reader to compare it.
    """
    if q_target <= 0:
        return float("inf")
    return float(core.min_lot_risk_eur(symbol, dist_price, info) / q_target)


def realised_over_policy(equity: float, q_target: float, symbol: str,
                         dist_price: float | None = None, info: object | None = None) -> float:
    """How many times the policy risk the account ACTUALLY runs at this equity.

    1.0 means the sleeve runs what it chose. 3.0 means the venue's floor is imposing three times
    the intended risk and no state file says so, which is the failure `realised_q` was written
    for -- reported here per sleeve rather than only at the moment of an order.
    """
    if equity <= 0 or q_target <= 0:
        return float("inf")
    floor_eur = core.min_lot_risk_eur(symbol, dist_price, info)
    intended_eur = q_target * equity
    return float(max(floor_eur, intended_eur) / intended_eur)


def capacity_curve(q_target: float, symbol: str, dist_price: float | None = None,
                   info: object | None = None,
                   ladder: tuple[float, ...] = LADDER_EUR) -> list[dict[str, Any]]:
    """Over-policy multiple at each rung of the equity ladder."""
    return [
        {"equity_eur": e,
         "over_policy": round(realised_over_policy(e, q_target, symbol, dist_price, info), 4),
         "binding": realised_over_policy(e, q_target, symbol, dist_price, info) > 1.0}
        for e in ladder
    ]


def assess(sleeve: dict[str, Any], equity: float) -> dict[str, Any]:
    """One sleeve's capacity facts. Never raises on a missing field -- it reports the gap."""
    name = str(sleeve.get("name") or "?")
    symbol = str(sleeve.get("symbol") or core.GOLD_SYMBOL)
    dist = sleeve.get("dist")
    q_target = sleeve.get("q_target") or sleeve.get("risk_frac")
    if not q_target:
        return {"sleeve": name, "symbol": symbol, "status": "UNMEASURED",
                "why": "the sleeve declares no target risk fraction, so there is no policy for "
                       "the floor to be compared against"}
    q_target = float(q_target)
    dist_price = float(dist) if dist else None
    bind_at = floor_binding_equity(q_target, symbol, dist_price)
    over = realised_over_policy(equity, q_target, symbol, dist_price)
    return {
        "sleeve": name, "symbol": symbol, "q_target": q_target,
        "min_lot_risk_eur": round(core.min_lot_risk_eur(symbol, dist_price), 4),
        "floor_binding_below_eur": round(bind_at, 2),
        "over_policy_now": round(over, 4),
        "binding_now": over > 1.0,
        # HOW MUCH ROOM IS LEFT, which is the small-capital advantage stated as a number: an edge
        # whose floor stops binding only far above this account is one a large fund cannot hold.
        "headroom_multiple": round(bind_at / equity, 3) if equity > 0 else None,
        "ceiling_eur": None,
        "ceiling_status": "UNMEASURED",
        "ceiling_why": ("market impact needs realised fills and matched_fills is 0; a ceiling "
                        "from an unvalidated cost model would be believed and should not be"),
        "status": "MEASURED",
    }


def over_risked(rows: list[dict[str, Any]],
                tolerance: float = OVER_RISK_TOLERANCE) -> list[dict[str, Any]]:
    """Sleeves whose realised risk exceeds their policy by more than the tolerance.

    THE CONSUMER. A capability that produces an artifact nobody reads is code, not a capability,
    so this is the function the issue board calls -- the difference between WIRED and RUNNING.
    """
    return [r for r in rows
            if r.get("status") == "MEASURED" and float(r.get("over_policy_now") or 0) > tolerance]


def measure(sleeves: list[dict[str, Any]] | None = None,
            equity: float | None = None) -> dict[str, Any]:
    """The whole capability, in one call."""
    if equity is None:
        equity = 0.0
        state = BASE / "web" / "desk_state.json"
        for candidate in (REPO / "web" / "desk_state.json", state):
            try:
                equity = float(json.loads(candidate.read_text("utf-8"))["account"]["equity"])
                break
            except Exception:                                           # noqa: BLE001, S110
                continue
    if sleeves is None:
        sleeves = []
        try:
            sleeves = [s for s in core.roster()[0] if isinstance(s, dict)]
        except Exception:                                               # noqa: BLE001
            sleeves = []
    rows = [assess(s, equity) for s in sleeves]
    flagged = over_risked(rows)
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "equity_eur": equity,
        "sleeves": len(rows),
        "measured": sum(1 for r in rows if r.get("status") == "MEASURED"),
        "binding_now": sum(1 for r in rows if r.get("binding_now")),
        "over_risked": [r["sleeve"] for r in flagged],
        "tolerance": OVER_RISK_TOLERANCE,
        "rows": rows,
        "ceiling_status": "UNMEASURED",
        "law": ("capacity at this desk is a FLOOR problem, not a ceiling one: the venue's "
                "minimum lot forces more risk than policy below a computable equity, and market "
                "impact is unmeasurable until a fill exists"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="print only, write nothing")
    args = ap.parse_args(argv)
    out = measure()
    if not args.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"capacity: {out['measured']}/{out['sleeves']} measured, "
          f"{out['binding_now']} floor-bound at EUR {out['equity_eur']:.2f}, "
          f"{len(out['over_risked'])} over policy; ceiling UNMEASURED", flush=True)
    for row in out["rows"]:
        if row.get("binding_now"):
            print(f"  {row['sleeve']:28} {row['over_policy_now']:.2f}x policy "
                  f"(floor binds below EUR {row['floor_binding_below_eur']:.0f})", flush=True)
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
