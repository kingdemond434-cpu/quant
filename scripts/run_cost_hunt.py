#!/usr/bin/env python3
"""COST HUNT (R0198) -- the cheapest trade is an edge nobody has to predict anything to earn.

PRINCIPAL ORDER (2026-07-31): *"hunt ur best net costs n all, make it intelligent."*

WHY COSTS ARE THE ONE LEVER AVAILABLE TODAY. Every other term in the growth identity -- hit rate,
winner shape, independent bets -- needs closed trades before it can be improved on purpose. Costs
do not. They are known BEFORE the trade, they are the difference between the 25.0% gross breakeven
and the 31.1% net one, and near breakeven their effect is grotesquely leveraged: the cost stack is
~24% of one R, and removing a third of it moves the required hit rate by more than a point --
which multiplies compounding severalfold near the threshold (the +3pp = 3.5x g arithmetic in
DISCRETIONARY_DESK.md).

THE HOLE THIS CLOSES. The resolver charges funding ALWAYS-ADVERSE by design -- correct for
marking, because a mark must never flatter itself. But funding is SIGNED and PUBLIC: on Binance
USD-M, positive funding means longs pay shorts, so at any moment half the instrument-sides are
being PAID to hold. The sleeve was blind to which half. A discretionary trader with two comparable
setups takes the one where carry is a tailwind; this organ is that judgement, mechanised:

  * snapshots the CURRENT funding rate for every instrument the sleeve trades
    (Binance premiumIndex bulk endpoint; OKX per-symbol fallback, because Binance answers 451
    from some egress regions and an organ that dies on that never runs),
  * states, per (symbol, direction), who pays whom and how much per 8h stamp,
  * flags EXTREME funding -- the meme-perp regime where a single day's carry eats a meaningful
    fraction of the risk unit and the only winning move is to not pay it,
  * publishes data/cost_hunt.json for the conviction trader, which (a) shows the paid/paying
    sides to the model in its brief, (b) prices each call's expected cost in R from its OWN stop
    and horizon, and (c) REFUSES trades whose expected cost exceeds COST_REFUSE_R of the risk
    unit (run_conviction_trader.trade_cost_view).

WHY COST-IN-R IS SIZE-INDEPENDENT, which is what makes this computable before sizing: cost in R
= (cost as a fraction of notional) / (stop distance as a fraction of price). Leverage cancels.
A 2% stop paying 0.1%/8h funding over 24h costs 0.15R whether the position is $10 or $10,000.

DELIBERATE ASYMMETRY, stated so nobody "fixes" it: SELECTION uses signed funding (prefer the paid
side, refuse the extreme-paying side), but MARKING stays always-adverse. A mark that credits
funding would flatter the book with carry the next regime takes away; a selector that ignores it
leaves free money on the table. Different jobs, different signs.

REFUSES RATHER THAN GUESSES: a symbol whose rate cannot be fetched is NO-DATA, never assumed
zero -- an assumed-zero rate on a 0.3%/8h meme perp is exactly the silent flattery this desk
fences everywhere else (L1.28a).

    python scripts/run_cost_hunt.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/cost_hunt.json"

#: 0.0005 = 0.05% per 8h, five times the typical major's 0.01% stamp. Above this an instrument is
#: in the crowded-carry regime where funding alone eats >=0.15% of notional per day -- at a 1%
#: structural stop that is >=0.15R/day of pure bleed, which no chart thesis of this sleeve's
#: horizon reliably outruns. Derived from the resolver's own funding arithmetic, not chosen.
EXTREME_FUNDING_8H = 0.0005

#: What maker-in entry is WORTH, restated from the resolver's published venue schedule so the
#: model sees the number in its brief: taker 0.045% vs maker 0.018% per side = 2.7bp of notional
#: saved on entry. At the sleeve's reference 0.9% stop that is 0.030R per trade -- measured, and
#: the reason entry_order_type is POST_ONLY_LIMIT at the named level rather than a chase.
MAKER_SAVING_PER_SIDE = 0.00045 - 0.00018


def _http_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-cost-hunt/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_funding(symbols: tuple[str, ...], *, http=_http_json) -> dict[str, dict[str, Any]]:
    """Current funding per symbol, signed Binance-convention: POSITIVE = longs pay shorts.

    Binance bulk first (one call for the whole universe), OKX per-symbol fallback for whatever
    the bulk call missed. A symbol neither venue answers for is NO-DATA -- never zero."""
    out: dict[str, dict[str, Any]] = {}
    # Each venue's failure is CARRIED to the NO-DATA rows rather than swallowed. A bare pass here
    # would make a total Binance outage read identically to "the bulk call just missed this
    # symbol", and those demand different responses -- one is an egress/region problem the
    # operator can fix, the other is a delisted contract nobody should chase.
    bulk_err = ""
    try:
        rows = http("https://fapi.binance.com/fapi/v1/premiumIndex")
        for r in rows if isinstance(rows, list) else []:
            s = r.get("symbol")
            if s in symbols and r.get("lastFundingRate") not in (None, ""):
                out[s] = {"state": "MEASURED", "funding_8h": float(r["lastFundingRate"]),
                          "source": "binance"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        bulk_err = f"binance bulk: {type(exc).__name__}: {exc}"
    for s in symbols:
        if s in out:
            continue
        inst = s.replace("USDT", "-USDT-SWAP")
        okx_err = ""
        try:
            d = http(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}")
            row = (d.get("data") or [{}])[0]
            if row.get("fundingRate") not in (None, ""):
                out[s] = {"state": "MEASURED", "funding_8h": float(row["fundingRate"]),
                          "source": "okx"}
                continue
            # EMPTY data is not an outage -- it is the venue saying it does not list this
            # contract, which is permanent and needs a different answer from a transient
            # failure. Verified 2026-07-31: OKX lists no gold swap at all, so PAXGUSDT is
            # BINANCE-ONLY and its NO-DATA will never heal by retrying. Conflating the two
            # would have the operator chasing a network fault that does not exist.
            okx_err = "okx: NOT LISTED (empty data for this instId -- structural, not an outage)"
        except (OSError, ValueError, urllib.error.URLError) as exc:
            okx_err = f"okx: {type(exc).__name__}: {exc}"
        unlisted = "NOT LISTED" in okx_err
        out[s] = {"state": "NO-DATA", "funding_8h": None,
                  "errors": [e for e in (bulk_err, okx_err) if e],
                  "fallback_exists": not unlisted,
                  "why": ("no fallback venue lists this contract, so this symbol is "
                          "SINGLE-VENUE: its funding is unmeasurable whenever the primary is "
                          "unreachable, and no retry fixes that"
                          if unlisted else
                          "neither venue answered -- NOT assumed zero; an assumed-zero rate on "
                          "an extreme-funding perp is silent flattery (L1.28a)")}
    return out


def signed_funding_8h(funding_8h: float, direction: str) -> float:
    """Per-8h funding for THIS side, positive = this trade PAYS, negative = it is PAID.

    Binance convention: positive funding, longs pay shorts. So a LONG pays +rate and a SHORT
    pays -rate; the sign flip is the entire mechanism by which carry becomes selectable."""
    return float(funding_8h) if direction == "LONG" else -float(funding_8h)


def build_report(symbols: tuple[str, ...], *, http=_http_json) -> dict[str, Any]:
    rates = fetch_funding(symbols, http=http)
    measured = {s: r for s, r in rates.items() if r["state"] == "MEASURED"}
    sides: list[dict[str, Any]] = []
    for s, r in measured.items():
        for d in ("LONG", "SHORT"):
            pays = signed_funding_8h(r["funding_8h"], d)
            sides.append({"symbol": s, "direction": d, "pays_8h": round(pays, 8),
                          "stance": "PAYS" if pays > 0 else ("PAID" if pays < 0 else "FLAT"),
                          "extreme": abs(pays) >= EXTREME_FUNDING_8H and pays > 0})
    sides.sort(key=lambda x: x["pays_8h"])          # most-paid first, worst-paying last
    extremes = [x for x in sides if x["extreme"]]
    status = ("NO-DATA" if not measured else
              "MEASURED" if len(measured) == len(symbols) else "PARTIAL")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.41 -- costs measured, never assumed. Funding is signed and public; selection "
               "uses the sign (prefer the paid side, refuse extreme payers) while MARKING stays "
               "always-adverse. Different jobs, different signs, both deliberate.",
        "status": status,
        "n_measured": len(measured), "n_symbols": len(symbols),
        "rates": rates,
        "sides_ranked": sides,
        "best_carry": sides[:5],
        "extreme_paying": extremes,
        "maker_saving_per_side": MAKER_SAVING_PER_SIDE,
        "detail": (f"{len(measured)}/{len(symbols)} funding rates measured; "
                   + (f"{len(extremes)} extreme-paying side(s) flagged" if extremes else
                      "no extreme funding in force")
                   if measured else
                   "NO-DATA -- neither venue answered for any symbol; the trader's cost veto "
                   "stands down and the flat pessimistic cost model carries alone"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    from scripts.run_conviction_trader import INSTRUMENTS
    rep = build_report(INSTRUMENTS)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"cost hunt (L1.41): {rep['status']} -- {rep['detail']}")
        for x in rep["best_carry"][:3]:
            print(f"  PAID  {x['symbol']:<10} {x['direction']:<5} {x['pays_8h']:+.5%}/8h")
        for x in rep["extreme_paying"][:3]:
            print(f"  AVOID {x['symbol']:<10} {x['direction']:<5} {x['pays_8h']:+.5%}/8h EXTREME")
    return 0


if __name__ == "__main__":
    sys.exit(main())
