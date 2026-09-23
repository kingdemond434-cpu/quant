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
import contextlib
import json
import math
import re
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
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"

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


def _certificate_for(symbol: str, family: str) -> dict[str, Any] | None:
    """The best ten-gate certificate on this (symbol, family), with its ev and cell rr.

    Joined on (symbol, family) rather than by id because a sleeve's `certificate` field is the
    string "forward_clock" -- it names the LANE that promoted the row, not a key into the survivor
    ledger. The best ev wins when several certificates cover the same coordinate; `rr` is read off
    the cell name, which is where the gauntlet records it (`...rr=1.5_wb=12`).
    """
    try:
        doc = json.loads(SURVIVORS.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    best: dict[str, Any] | None = None
    for key, val in (doc.get("survivors") or {}).items():
        if not isinstance(val, dict):
            continue
        spec = val.get("shadow_spec") or {}
        if str(spec.get("symbol") or val.get("sym") or "").upper() != symbol.upper():
            continue
        if family and str(spec.get("family") or "") != family:
            continue
        ev = ((val.get("gates") or {}).get("expected_value") or {}).get("ev")
        if not isinstance(ev, (int, float)):
            continue
        rr = None
        m = re.search(r"rr=([0-9]*\.?[0-9]+)", str(val.get("cell") or key))
        if m:
            with contextlib.suppress(ValueError):
                rr = float(m.group(1))
        if best is None or ev > best["ev"]:
            best = {"key": str(key), "ev": float(ev), "rr": rr}
    return best


def elog_per_trade(f: float, exp_r: float, rr: float) -> float | None:
    """E[log(1 + f*R)] for one trade at risk fraction `f`, over the sleeve's own payoff shape.

    THE TWO-POINT FORM IS THE SLEEVE'S OWN, NOT AN ASSUMPTION ABOUT IT. A sleeve declares
    `shadow_exp` (expectancy in R) and a target/stop ATR pair, which fix the reward:risk and
    therefore the win rate exactly: p*rr - (1-p) = exp_r, so p = (exp_r + 1) / (rr + 1). Nothing
    here is fitted and nothing is invented.

    WHY LOG AND NOT THE MEAN. Growth compounds, so the quantity that decides whether an edge is
    worth holding at THIS size is E[log W], and its defining feature is that it turns NEGATIVE
    while the arithmetic edge is still positive. That is the whole of the capacity problem at
    small capital: the venue's minimum lot forces a risk fraction past the growth optimum, and a
    book can be over-betting a real edge into a real loss with every number except this one
    looking healthy.

    f >= 1 IS RUIN AND IS RETURNED AS SUCH. A full-risk loss takes the account to zero, log(0) is
    -inf, and reporting a large negative number instead would invite someone to average it.
    """
    if not (rr > 0) or not (0.0 < f):
        return None
    p_win = (exp_r + 1.0) / (rr + 1.0)
    if not (0.0 < p_win < 1.0):
        return None
    if f >= 1.0:
        return float("-inf")
    return float(p_win * math.log(1.0 + f * rr) + (1.0 - p_win) * math.log(1.0 - f))


def elog_now(sleeve: dict[str, Any], q_target: float, symbol: str, equity: float,
             dist_price: float | None = None) -> dict[str, Any]:
    """Expected log growth per trade AT THIS EXACT EQUITY. The decision, not the display.

    THE LADDER IS A SHAPE AND THIS IS A VERDICT. `elog_at_capital` walks decade rungs so a reader
    can see where growth peaks and where it turns; at EUR 752.51 the nearest rungs are 500 and
    750, and reading the decision off either is reading it off a number the account is not at.
    Measured the day this was added: six sleeves showed NEGATIVE at the 500 rung and POSITIVE at
    750, so the ladder alone could have condemned six working sleeves or blessed six losing ones
    depending on which rung a reader's eye landed on.

    WHAT TO DO WITH A NEGATIVE VERDICT, and it is not "cut risk". Removing a sleeve whose
    E[log W] is negative RAISES the book's total expected log growth -- that is the whole of Rule
    1's test, satisfied directly rather than argued -- and the heat it frees goes to sleeves above
    their peak, which is Rule 2. So this is a REALLOCATION instrument, not a veto: it says which
    bets are paying at this account size, and the answer to a negative one may equally be more
    capital rather than less risk.

    NOTHING HERE FEEDS THE ALLOCATOR. It is published beside the ceiling's refusal like every
    other number in this module.
    """
    exp_r = sleeve.get("_elog_exp_r")
    rr = sleeve.get("_elog_rr")
    if not isinstance(exp_r, (int, float)) or not isinstance(rr, (int, float)):
        return {"status": "UNMEASURED", "why": "no priced edge or payoff shape for this sleeve"}
    if not (equity > 0):
        return {"status": "UNMEASURED", "why": "no positive equity to price against"}
    floor_frac = core.min_lot_risk_eur(symbol, dist_price) / equity
    f = max(q_target * realised_over_policy(equity, q_target, symbol, dist_price), floor_frac)
    g = elog_per_trade(f, float(exp_r), float(rr))
    return {
        "status": "MEASURED",
        "equity_eur": round(equity, 2),
        "realised_frac": round(f, 6),
        "elog_per_trade": None if g is None else (None if g == float("-inf") else round(g, 8)),
        "ruin": g == float("-inf"),
        "verdict": ("RUIN" if g == float("-inf") else
                    "UNPRICEABLE" if g is None else
                    "NEGATIVE" if g <= 0 else "POSITIVE"),
        "why": ("a NEGATIVE verdict means this sleeve is expected to shrink the book by "
                "compounding at THIS equity even though its edge is positive -- the venue's "
                "minimum lot is forcing a fraction past the growth optimum. Reallocating away "
                "from it RAISES total E[log W]; so does more capital"),
    }


def elog_at_capital(sleeve: dict[str, Any], q_target: float, symbol: str,
                    dist_price: float | None = None,
                    ladder: tuple[float, ...] = LADDER_EUR) -> dict[str, Any]:
    """Expected log growth per trade at each rung of the equity ladder. P12.

    THE CEILING IS UNMEASURABLE AND THIS IS NOT THE CEILING. Market impact needs realised fills
    and `matched_fills` is 0, so an upper bound would be a believed fiction. This is the same
    capacity question asked at the end that IS computable from numbers already on disk: what the
    edge is WORTH at each account size, given that below `floor_binding_equity` the venue's
    minimum forces more risk than policy asks for.

    It costs no new data. `realised_over_policy` already says how far past policy the floor pushes
    the fraction at each rung; this multiplies that by the sleeve's declared target and prices the
    result in log growth. The shape it produces is the small-account story stated as a number:
    growth rising with capital and SATURATING at the policy optimum, and -- where the floor pushes
    the realised fraction past the growth peak -- NEGATIVE at the bottom rungs of an edge that is
    genuinely positive.

    `peak_equity_eur` is the rung where growth is highest, and `negative_below_eur` is the equity
    beneath which this sleeve is expected to LOSE money by compounding, both of which are
    decisions the desk could not previously make.
    """
    # WHERE THE EDGE COMES FROM, AND IT IS NAMED. Only 3 of 65 LIVE rows carry `shadow_exp`;
    # the other 62 hold a ten-gate certificate whose `expected_value` gate measured exactly this
    # number. Reporting 62 UNMEASURED while the measurement sits one join away is not rigour, it
    # is a missing join -- so the certificate is consulted, and the artifact says which source
    # priced each curve rather than letting the two look alike.
    exp_r, exp_src = sleeve.get("shadow_exp"), "sleeve.shadow_exp"
    rr, rr_src = None, None
    stop_atr, target_atr = sleeve.get("stop_atr"), sleeve.get("target_atr")
    try:
        rr = float(target_atr) / float(stop_atr)          # type: ignore[arg-type]
        rr_src = "sleeve.target_atr/stop_atr"
    except (TypeError, ValueError, ZeroDivisionError):
        rr = None
    if not isinstance(exp_r, (int, float)) or rr is None:
        cert = _certificate_for(symbol, str(sleeve.get("family") or ""))
        if cert:
            if not isinstance(exp_r, (int, float)) and isinstance(cert.get("ev"), (int, float)):
                exp_r, exp_src = cert["ev"], f"certificate {cert['key'][:48]} expected_value.ev"
            if rr is None and isinstance(cert.get("rr"), (int, float)):
                rr, rr_src = cert["rr"], f"certificate {cert['key'][:48]} cell rr"
    if not isinstance(exp_r, (int, float)):
        return {"status": "UNMEASURED",
                "why": "neither the sleeve nor any certificate on (symbol, family) declares an "
                       "expectancy, so there is no edge to price at any capital -- absence is "
                       "not a zero edge (L1.28a)"}
    if rr is None:
        return {"status": "UNMEASURED",
                "why": "no usable reward:risk from the sleeve's ATR pair or the certificate's "
                       "cell, so the payoff shape is unknown and a win rate cannot be derived"}
    rows: list[dict[str, Any]] = []
    for e in ladder:
        over = realised_over_policy(e, q_target, symbol, dist_price)
        # THE REALISED FRACTION IS WHAT COMPOUNDS, and below `floor_binding_equity` it is the
        # FLOOR's number and not the policy's. A sleeve the allocator zeroed still trades the
        # venue minimum since the principal's 2026-09-12 order, so `q_target * over` would price
        # zero risk for a position that is really on -- the floor is taken directly instead.
        floor_frac = (core.min_lot_risk_eur(symbol, dist_price) / e) if e > 0 else 0.0
        f = max(q_target * over, floor_frac)
        g = elog_per_trade(f, float(exp_r), rr)
        rows.append({"equity_eur": e, "realised_frac": round(f, 6),
                     "over_policy": round(over, 4),
                     "elog_per_trade": None if g is None else (
                         None if g == float("-inf") else round(g, 8)),
                     "ruin": g == float("-inf")})
    priced = [r for r in rows if isinstance(r["elog_per_trade"], float)]
    peak = max(priced, key=lambda r: r["elog_per_trade"]) if priced else None
    negative_below = None
    for r in rows:
        v = r["elog_per_trade"]
        if r["ruin"] or (isinstance(v, float) and v <= 0):
            negative_below = r["equity_eur"]
    return {
        "status": "MEASURED",
        "exp_r": float(exp_r), "exp_r_source": exp_src,
        "rr": round(rr, 4), "rr_source": rr_src,
        # Stashed so `elog_now` can price the exact equity without redoing the certificate join.
        "_resolved": {"exp_r": float(exp_r), "rr": float(rr)},
        "win_rate": round((float(exp_r) + 1.0) / (rr + 1.0), 4),
        "curve": rows,
        "peak_equity_eur": None if peak is None else peak["equity_eur"],
        "peak_elog_per_trade": None if peak is None else peak["elog_per_trade"],
        # THE NUMBER THAT DECIDES WHETHER TO HOLD THIS SLEEVE AT ALL RIGHT NOW.
        "negative_at_or_below_eur": negative_below,
        "basis": ("E[log(1 + f*R)] over the sleeve's own two-point payoff, f = q_target x "
                  "realised_over_policy(equity); no new data, no fitted parameter"),
    }


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
    _curve = elog_at_capital(sleeve, q_target, symbol, dist_price)
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
        # P12: what the edge is WORTH at each account size. The ceiling stays unmeasurable; this
        # is the half of the capacity question that is computable from numbers already on disk,
        # and it is the half that binds at EUR 607.
        "elog_at_capital": _curve,
        # THE VERDICT AT THE ACCOUNT'S ACTUAL EQUITY, which is the number a decision is made on.
        "elog_now": elog_now({**sleeve,
                              "_elog_exp_r": (_curve.get("_resolved") or {}).get("exp_r"),
                              "_elog_rr": (_curve.get("_resolved") or {}).get("rr")},
                             q_target, symbol, equity, dist_price),
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
        # THE EQUITY A SIZING VERDICT USES MUST NOT COME FROM A DASHBOARD (measured 2026-09-13).
        #
        # This read `web/desk_state.json` FIRST, which is the payload the dashboard renders --
        # a display artifact, written by whichever machine last published, and present on boxes
        # that do not trade at all. Run on the mirror it returned EUR 752.51 while the live
        # terminal, account_state.json and gateway_state.json all said 607.68. Every Elog(C)
        # verdict in this module is a function of that number, so the whole P12 table was priced
        # at an equity the account has never had, and nothing in the artifact said which box's
        # dashboard it had believed.
        #
        # PRECEDENCE IS NOW BY AUTHORITY, NOT BY CONVENIENCE: the account organ's own state, then
        # the gateway's, then -- last and named as such -- the dashboard payload. The source
        # RIDES ON THE REPORT, because "EUR 607.68" and "EUR 607.68 from a display artifact on a
        # machine that does not trade" are the same number and different facts.
        equity, equity_source = 0.0, "NONE"
        for candidate, keys, label in (
            (BASE / "data" / "account_state.json", ("equity",), "account_state.json"),
            (BASE / "data" / "gateway_state.json", ("equity",), "gateway_state.json"),
            (BASE / "web" / "desk_state.json", ("account", "equity"), "web/desk_state.json"),
            (REPO / "web" / "desk_state.json", ("account", "equity"),
             "REPO web/desk_state.json (display artifact -- may be another box's)"),
        ):
            try:
                doc = json.loads(candidate.read_text("utf-8"))
                for k in keys:
                    doc = doc[k]
                val = float(doc)
            except Exception:                                           # noqa: BLE001, S110
                continue
            if val > 0:
                equity, equity_source = val, label
                break
    source = "caller"
    if sleeves is None:
        sleeves = []
        source = "decision_core.roster"
        try:
            sleeves = [s for s in core.roster()[0] if isinstance(s, dict)]
        except Exception:                                               # noqa: BLE001
            sleeves = []
        if not sleeves:
            # THE ROSTER WAS THIS ORGAN'S ONLY SOURCE AND IT RAISES ON THIS BOX.
            #
            # Measured 2026-09-12: `from research import decision_core` fails with ImportError,
            # the except above swallows it, and `measure()` has returned "0/0 measured" for as
            # long as the file has existed -- an organ that runs, writes a report and says
            # nothing. That is III.16 exactly, and it is invisible because 0/0 is a perfectly
            # well-formed answer.
            #
            # data/sleeves.json is the file every other organ on this desk reads, and its LIVE
            # rows carry `risk_frac`, which is precisely the policy fraction `assess` wants. The
            # fallback is not a second source of truth: it is the SAME roster, read from the file
            # the roster is built from.
            #
            # THE SOURCE IS RECORDED IN THE OUTPUT. A fallback nobody can see in the artifact is
            # how a desk ends up not knowing which of two answers it is reading.
            source = "data/sleeves.json (LIVE rows) -- roster unavailable"
            try:
                doc = json.loads((BASE / "data" / "sleeves.json").read_text("utf-8"))
                rows_in = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
                sleeves = [s for s in rows_in
                           if isinstance(s, dict)
                           and str(s.get("status", "")).upper() == "LIVE"]
            except Exception:                                           # noqa: BLE001
                sleeves = []
                source = "NONE -- roster unavailable and data/sleeves.json unreadable"
    rows = [assess(s, equity) for s in sleeves]
    flagged = over_risked(rows)
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "equity_eur": equity,
        # WHERE THAT NUMBER CAME FROM. A sizing verdict priced off a display artifact is not the
        # same claim as one priced off the account organ, and a reader must be able to tell.
        "equity_source": equity_source,
        "sleeve_source": source,
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
