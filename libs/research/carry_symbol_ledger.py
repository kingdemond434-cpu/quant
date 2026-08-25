"""R0522 -- WHAT EACH NAME ACTUALLY EARNED, net of what it actually cost, over its own history.

THE SELECTION LOGIC IS INVERTED AND THE AGGREGATE COULD NEVER SHOW IT. "The carry loss is fees,
not thesis" was already known: venue truth over 2026-07-02..08-01 is funding +113.06 USDT against
commission 1750.90 = NET -1637.85. What the aggregate hides is that the loss is not spread -- it
is CONCENTRATED IN THE NAMES THE SELECTOR LIKES BEST. Measured from the income ledger:

    COOKIEUSDT    funding    +7.01   fees  623.30   net  -616.29
    1000CATUSDT   funding    +4.29   fees  413.03   net  -408.74
    MOVEUSDT      funding    +3.29   fees  245.95   net  -242.66
    TSTUSDT       funding   +20.64   fees  221.54   net  -200.90
    XVGUSDT       funding   +21.49   fees   18.09   net    +3.41   <- a survivor

6 of 84 symbols are net-positive. The four worst are among the largest deployed positions.

THE MECHANISM IS TURNOVER, NOT RATE. The executor ranks by `_net_bps`, which prices a SINGLE round
trip. A name whose funding beats one round trip is therefore selected -- and then re-traded until
cumulative fees swamp cumulative harvest. `_MIN_HOLD_H` bounds how long one carry is held; NOTHING
anywhere prices CUMULATIVE fees against CUMULATIVE funding per name. TSTUSDT earned more funding
than any name except XVGUSDT and still lost 200 USDT, which is the whole finding in one row: the
rate was right and the re-trading ate it.

THE ANSWER IS A NUMBER, NOT A TIMER (L1.48). The current cooldown set expires on ELAPSED TIME and
so cannot encode "this name loses money the way we trade it". `reentry_funding_rate` converts each
veto into the funding rate at which the name would clear its own measured round-trip cost -- an
ECONOMIC re-entry condition, which is the L1.16a condition the cooldowns lack.

AND THE VETO IS NEVER A ONE-WAY DOOR (L1.45). An exclusion whose evidence can only be produced by
the trading it forbids is a cycle: never traded -> never measured -> never traded, forever. Every
veto here therefore carries a re-entry rate that FORWARD funding can satisfy without any position
being taken, and the exclusion is scoped to RE-ENTRY -- it never blocks a close.

TWO CAVEATS THAT BOUND EVERY NUMBER IN HERE, both stamped into the artifact:
  * THE RATIO IS A TURNOVER STATISTIC, NOT AN EDGE. Fees accrue on cumulative TRADED notional;
    funding accrues on HELD notional. fees/funding is therefore a statement about how often we
    re-traded, and it is NOT a per-unit-time return. Only `net_usd` is a real economic quantity.
  * THIS IS TESTNET. Fills and the 5bp taker rate need not reproduce live. The RANKING is far more
    durable than the levels, and the ranking is what this is for.

STAGE-A ONLY. Publishes evidence and a candidate list; promotes nothing, sizes nothing, and has no
vocabulary for placing an order.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

#: Taker rate the desk is billed at, both legs, per round trip. Same constant fee_attribution
#: prices the implied-notional residual with; imported rather than re-declared would be better
#: still, but that module owns a DIFFERENT question and a shared constant that drifts is worse
#: than a named duplicate. Kept in sync by test.
TAKER_RATE = 0.0005

#: A round trip is two fills -- open and close -- each billed at the taker rate.
ROUND_TRIP_COST = 2.0 * TAKER_RATE

#: Below this, `fees / funding` is not a meaningful ratio (a near-zero denominator makes any
#: quotient enormous). Names under it are ranked by net_usd alone and say so.
_MIN_FUNDING_FOR_RATIO = 0.01


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def lifetime_net(commission_events: Sequence[Mapping[str, Any]],
                 funding_events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-symbol lifetime funding, commission and NET, from venue income rows.

    ``commission_events`` are `binance_testnet.commission_events()` rows -- commission POSITIVE
    MEANS PAID. ``funding_events`` are raw FUNDING_FEE income rows, whose ``income`` is SIGNED:
    positive is funding RECEIVED, negative is funding PAID. The two sign conventions are different
    and mixing them up flips the sign of the entire finding, so they are read separately here and
    never through one loop.

    Returns UNMEASURED (`measured=False`) when there are no usable commission events: an empty or
    failed venue read is not evidence of a fee-free book (L1.28a).
    """
    fees: dict[str, float] = {}
    n_fee: dict[str, int] = {}
    fee_attempted = 0
    fee_unusable = 0
    for e in commission_events:
        fee_attempted += 1
        if not isinstance(e, Mapping):
            fee_unusable += 1
            continue
        sym = str(e.get("symbol") or "")
        amt = _f(e.get("commission"))
        if not sym or amt <= 0.0:
            fee_unusable += 1              # COUNTED, never dropped in silence (L1.60)
            continue
        fees[sym] = fees.get(sym, 0.0) + amt
        n_fee[sym] = n_fee.get(sym, 0) + 1

    funding: dict[str, float] = {}
    n_fund: dict[str, int] = {}
    fund_attempted = 0
    fund_unusable = 0
    for e in funding_events:
        fund_attempted += 1
        if not isinstance(e, Mapping):
            fund_unusable += 1
            continue
        sym = str(e.get("symbol") or "")
        if not sym:
            fund_unusable += 1
            continue
        # NOT `or 0.0` on a falsy check: a genuine 0.0 settlement is a real observation (the
        # position was held through a stamp and the rate was zero), and it is EVIDENCE that the
        # name is reachable by carry at all. Only a missing/garbage field is unusable.
        raw = e.get("income")
        if raw is None:
            fund_unusable += 1
            continue
        funding[sym] = funding.get(sym, 0.0) + _f(raw)
        n_fund[sym] = n_fund.get(sym, 0) + 1

    if not fees:
        return {"measured": False,
                "fee_events_attempted": fee_attempted, "fee_events_unusable": fee_unusable,
                "funding_events_attempted": fund_attempted,
                "note": ("no usable commission events -- UNMEASURED, not a fee-free book. An "
                         "empty venue read and a costless sleeve are different claims (L1.28a).")}

    symbols = sorted(set(fees) | set(funding))
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        f = funding.get(sym, 0.0)
        c = fees.get(sym, 0.0)
        held = sym in funding
        row: dict[str, Any] = {
            "symbol": sym,
            "funding_usd": round(f, 4),
            "commission_usd": round(c, 4),
            "net_usd": round(f - c, 4),
            "n_fee_events": n_fee.get(sym, 0),
            "n_settlements": n_fund.get(sym, 0),
            # NEVER HELD THROUGH A SETTLEMENT is its own state, not "zero carry". A name that was
            # traded and closed before any funding stamp paid nothing because it was never there
            # to be paid -- a fact about our HOLD TIME, not about the name's carry.
            "held_through_settlement": held,
        }
        row["fee_to_funding"] = (round(c / f, 2) if f >= _MIN_FUNDING_FOR_RATIO else None)
        rows.append(row)

    rows.sort(key=lambda r: float(r["net_usd"]))
    total_f = sum(funding.values())
    total_c = sum(fees.values())
    positive = [r for r in rows if float(r["net_usd"]) > 0]
    never_held = [r for r in rows if not r["held_through_settlement"]]
    return {
        "measured": True,
        "symbols": len(rows),
        "funding_usd": round(total_f, 4),
        "commission_usd": round(total_c, 4),
        "net_usd": round(total_f - total_c, 4),
        "n_net_positive": len(positive),
        "net_positive_symbols": [r["symbol"] for r in positive],
        # THE CLEANEST VETO CLASS THERE IS: billed, and never once present when funding paid.
        "n_never_held_through_settlement": len(never_held),
        "never_held_symbols": [r["symbol"] for r in never_held],
        "fee_events_attempted": fee_attempted, "fee_events_unusable": fee_unusable,
        "funding_events_attempted": fund_attempted, "funding_events_unusable": fund_unusable,
        "by_symbol": rows,
        "ratio_note": ("fee_to_funding is a TURNOVER statistic, not an edge: fees accrue on "
                       "cumulative TRADED notional and funding on HELD notional. Only net_usd is "
                       "a real economic quantity."),
        "venue_note": ("testnet execution -- fills and the 5bp taker rate need not reproduce "
                       "live. The RANKING is more durable than the levels."),
    }


def reentry_rate(row: Mapping[str, Any], taker_rate: float = TAKER_RATE) -> float | None:
    """The per-settlement funding rate at which this name clears its own measured round-trip cost.

    THE ECONOMIC RE-ENTRY CONDITION (L1.16a, L1.48). Over its history the name was held through
    ``n_settlements`` funding stamps across ``n_round_trips`` round trips, so the funding it must
    earn PER SETTLEMENT to break even is the round-trip cost divided by the settlements each round
    trip actually spans:

        settlements_per_round_trip = n_settlements / n_round_trips
        required_rate              = 2 * taker_rate / settlements_per_round_trip

    A name held through many settlements per trip needs very little funding to clear; a name
    re-traded every few hours needs an implausible rate, and THAT is the finding -- the number
    says how far the name is from viability AT OUR OWN OBSERVED HOLD TIME, which is the variable
    the desk controls.

    Returns None when it cannot be computed -- never a default. A name never held through a
    settlement has no measured hold time, so its required rate is not small, it is UNKNOWN, and
    the two must not read alike.
    """
    n_settle = int(_f(row.get("n_settlements")))
    n_fills = int(_f(row.get("n_fee_events")))
    if n_settle <= 0 or n_fills <= 0:
        return None
    round_trips = max(n_fills / 2.0, 1.0)      # two billed fills per round trip
    per_trip = n_settle / round_trips
    if per_trip <= 0:
        return None
    return (2.0 * taker_rate) / per_trip


def veto_candidates(ledger: Mapping[str, Any], taker_rate: float = TAKER_RATE) -> dict[str, Any]:
    """Names whose OWN realized history says the desk loses money trading them, with a way back.

    STAGE-A ONLY -- this is a candidate list and an evidence artifact. It promotes nothing, sizes
    nothing and blocks nothing by itself; the executor-side consumer is a money-path change and
    stages behind the L1.38 window.

    Every candidate carries `reentry_funding_rate`, so the exclusion can be cleared by FORWARD
    funding without a position ever being opened. That is the property that keeps this from
    becoming the L1.45 cycle: an exclusion whose only exit is the trading it forbids.
    """
    if not ledger.get("measured"):
        return {"measured": False, "note": "no ledger -- nothing to veto on (L1.28a)",
                "candidates": []}
    out: list[dict[str, Any]] = []
    for row in ledger.get("by_symbol", []):
        if float(_f(row.get("net_usd"))) >= 0.0:
            continue
        rate = reentry_rate(row, taker_rate)
        out.append({
            "symbol": row.get("symbol"),
            "net_usd": row.get("net_usd"),
            "funding_usd": row.get("funding_usd"),
            "commission_usd": row.get("commission_usd"),
            "fee_to_funding": row.get("fee_to_funding"),
            "held_through_settlement": row.get("held_through_settlement"),
            "reentry_funding_rate": None if rate is None else round(rate, 6),
            "reentry_condition": (
                f"per-settlement funding >= {rate:.4%} at our own observed hold time"
                if rate is not None else
                "UNKNOWN -- never held through a settlement, so no hold time has been measured; "
                "the missing evidence is a hold, not a rate"),
        })
    out.sort(key=lambda r: float(_f(r.get("net_usd"))))
    unknown = [r for r in out if r["reentry_funding_rate"] is None]
    return {
        "measured": True,
        "n_candidates": len(out),
        "n_without_measured_reentry": len(unknown),
        "candidates": out,
        "law": ("L1.16a -- every exclusion carries a re-entry condition. L1.48 -- the condition is "
                "EVIDENCE (a funding rate), never elapsed time: the existing cooldowns expire on a "
                "clock and so cannot encode 'this name loses money the way we trade it'."),
        "scope": ("RE-ENTRY ONLY. A veto never blocks a close, and closes are never withheld to "
                  "chase a settlement (L1.45, L1.47)."),
    }
