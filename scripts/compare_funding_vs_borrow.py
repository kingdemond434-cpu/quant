#!/usr/bin/env python3
"""PERP FUNDING vs MARGIN BORROW: which venue is cheaper to carry the SAME LONG on.

Built because the principal asked for perps "if perp pays way more". The instrument comes before
the build: a perp execution path is a second venue with its own connector, its own liquidation
arithmetic and its own cost model, and it is worth none of that if the answer is no. Two things
decide it, in this order, and only the second is about money.

================================================================================================
GATE 1 -- ACCESS, WHICH NO COST NUMBER CAN OVERRIDE
================================================================================================
`scripts/run_live_guard.py` records, measured 2026-08-15: the principal is IRISH RETAIL, so EEA
derivatives are unavailable under MiCA and the futures account CANNOT BE READ AT ALL. The futures
keyfile exists and the venue refuses the account. `run_discretionary_live --spot-only` and the
spot-only momentum book both exist for the same reason.

So the perp question is very likely closed before the arithmetic starts, and this script checks
access FIRST and says so. A cost comparison that concludes "perps win" for an account that may not
open one is a number that gets acted on and cannot be.

================================================================================================
GATE 2 -- THE ARITHMETIC, WHICH HAS A TRAP IN IT
================================================================================================
The intuition "perp funding pays you" is true for a SHORT and backwards for a LONG, and this book
is long-only. Worse, the two costs are charged on DIFFERENT BASES, which is the part that decides
the answer and is the easiest thing to get wrong:

    MARGIN BORROW is charged on the BORROWED PART ONLY. Carrying gross G at leverage f borrows
    G*(f-1)/f, so the cost per unit of NOTIONAL is  r * (f-1)/f.

    PERP FUNDING is charged on the WHOLE NOTIONAL, every stamp, whatever the leverage. The cost
    per unit of notional is simply the annualised funding rate.

    => PERP IS CHEAPER IFF  funding_annual  <  r * (f-1)/f

At f=2.3x and r=5.1% that break-even is about 2.9%/yr. Perp funding on the majors runs near
0.01% per 8h stamp, which is ~11%/yr -- roughly FOUR TIMES the break-even, in the wrong direction.
Comparing the raw rates (5.1% vs 11%) gets the sign right by luck; comparing them without the
leverage adjustment gets the MAGNITUDE wrong and would flip the answer at high leverage, where
(f-1)/f approaches 1 and margin's advantage disappears.

**WHEN PERP WINS, STATED SO THE CASE IS NOT LOST.** Funding goes NEGATIVE in bearish regimes --
shorts pay longs -- and a perp long is then PAID to hold. This script reports the realised
distribution rather than an average precisely so that regime is visible rather than smoothed away.
A venue that is cheaper 30% of the time is a conditional decision, not a permanent one.

**WHAT PERPS BUY THAT IS NOT COST, and it is the real argument for them.** A spot-margin short
means borrowing the BASE asset, which is why `place_entry` refuses SELL and why every fade
mechanism in the playbook (H1, H7, H11) journals a refusal instead of a trade. On perps a short is
symmetric. That is a CAPABILITY gain and it should be argued on its own terms, never smuggled in
as a funding saving.

    python scripts/compare_funding_vs_borrow.py [--leverage 2.3] [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

_OUT = Path("web/funding_vs_borrow.json")

#: The sidecar's `funding` column is the SUM OF THE DAY'S funding payments (see
#: `libs/data/crypto_source.daily_with_funding`), so annualising is x365 and NOT x365x3. Getting
#: this wrong by the stamp count would treble every perp cost and decide the question by arithmetic
#: error in the direction that happens to agree with the conclusion -- which is the worst kind.
DAYS_PER_YEAR = 365

DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "ADAUSDT")


def breakeven_funding(borrow_rate: float, leverage: float) -> float:
    """The annualised funding rate at which a perp long costs exactly what a margin long costs.

    `r * (f-1)/f` -- margin interest per unit of NOTIONAL, since the loan is only the levered part.
    At f<=1 there is no loan, so margin carries the position for nothing and any positive funding
    loses: the break-even is 0.0 and that is a real answer, not a degenerate one.
    """
    f = float(leverage)
    if f <= 1.0:
        return 0.0
    return float(borrow_rate) * (f - 1.0) / f


def _funding_stats(series: dict[str, float]) -> dict[str, Any] | None:
    """Annualised funding: mean, median, and the SHARE OF DAYS NEGATIVE. None on an empty series."""
    vals = [float(v) for v in series.values()]
    if len(vals) < 30:
        return None
    ann = [v * DAYS_PER_YEAR for v in vals]
    return {
        "n_days": len(vals),
        "mean_annual": round(sum(ann) / len(ann), 5),
        "median_annual": round(median(ann), 5),
        # THE DISTRIBUTION, NOT JUST THE CENTRE. A venue that is cheaper a third of the time is a
        # conditional decision; a mean alone would present that as a single permanent verdict.
        "share_days_negative": round(sum(1 for v in vals if v < 0) / len(vals), 4),
    }


def _futures_access() -> dict[str, Any]:
    """Can this account open a perp at all? UNKNOWN is not YES."""
    row: dict[str, Any] = {
        "recorded_finding": ("run_live_guard.py, measured 2026-08-15: the principal is Irish "
                             "retail, EEA derivatives are unavailable under MiCA, and the futures "
                             "account cannot be read at all"),
        "state": "UNKNOWN", "why": "",
    }
    try:
        from libs.execution import binance_live as fut

        armed, why = fut.is_armed()
        row["connector_armed"] = bool(armed)
        row["why"] = str(why)[:200]
        row["state"] = "KEYS-PRESENT-ACCESS-UNVERIFIED" if armed else "NOT-ARMED"
    except Exception as exc:
        row["why"] = f"{type(exc).__name__}: {exc}"
    row["gate"] = ("ACCESS DECIDES THIS BEFORE COST DOES. A cost verdict of 'perp wins' on an "
                   "account that may not open a perp is a number that gets acted on and cannot be")
    return row


def build(symbols: tuple[str, ...] = DEFAULT_SYMBOLS, *, leverage: float = 2.3,
          borrow_rate: float | None = None) -> dict[str, Any]:
    from scripts.collect_perp_funding import load as load_funding

    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "question": "carry the SAME LONG: cross-margin borrow, or perp funding?",
        "leverage": float(leverage),
        "access": _futures_access(),
        "cost_bases": {
            "margin": "r * (f-1)/f per unit of NOTIONAL -- interest is charged on the borrowed "
                      "part only",
            "perp": "the annualised funding rate per unit of NOTIONAL -- funding is charged on the "
                    "WHOLE position, at every stamp, whatever the leverage",
            "why_it_matters": "comparing the raw rates ignores (f-1)/f and gets the magnitude "
                              "wrong; at high leverage (f-1)/f approaches 1 and margin's advantage "
                              "disappears entirely",
        },
        "symbols": {}, "verdict": "UNMEASURED", "why": "",
    }

    if borrow_rate is None:
        try:
            from libs.execution.binance_margin_live import borrow_rate as _br

            rate, why_rate = _br("USDC")
        except Exception as exc:
            rate, why_rate = None, f"{type(exc).__name__}: {exc}"
    else:
        rate, why_rate = float(borrow_rate), f"OVERRIDE: {borrow_rate}"
    rep["borrow_rate"] = rate
    rep["borrow_rate_why"] = why_rate

    if rate is None:
        rep["why"] = ("borrow rate UNMEASURED -- the comparison has no left-hand side. Refusing to "
                      "substitute a placeholder: this decides which venue the book settles on, and "
                      "a guessed cost of capital is how the account got capped at 1x once already")
        return rep

    be = breakeven_funding(rate, leverage)
    rep["breakeven_funding_annual"] = round(be, 5)
    rep["breakeven_why"] = (
        f"at {leverage:.2f}x on a {rate:.2%} borrow, a perp long is cheaper only below "
        f"{be:.2%}/yr funding. Above it, margin wins")

    wins_perp = wins_margin = 0
    for sym in symbols:
        stats = _funding_stats(load_funding(sym))
        if stats is None:
            rep["symbols"][sym] = {
                "state": "NO-FUNDING-SERIES",
                "why": ("fewer than 30 daily observations in data/perp_funding.json -- run "
                        "scripts/collect_perp_funding.py. UNMEASURED, not 'funding is zero'")}
            continue
        med = float(stats["median_annual"])
        cheaper = "PERP" if med < be else "MARGIN"
        if cheaper == "PERP":
            wins_perp += 1
        else:
            wins_margin += 1
        # MEDIAN, NOT MEAN. Funding is fat-tailed on the upside -- a squeeze prints stamps many
        # multiples of normal -- and a mean lets a handful of those decide a standing venue choice.
        stats["cheaper"] = cheaper
        stats["margin_cost_annual"] = round(be, 5)
        stats["excess_of_perp_over_margin"] = round(med - be, 5)
        rep["symbols"][sym] = stats

    if not wins_perp and not wins_margin:
        rep["verdict"] = "UNMEASURED"
        rep["why"] = ("no symbol carries a funding series on this host. data/ is gitignored, so "
                      "this is a statement about the clone, not about perps")
        return rep

    rep["n_cheaper_on_perp"], rep["n_cheaper_on_margin"] = wins_perp, wins_margin
    rep["verdict"] = "PERP" if wins_perp > wins_margin else "MARGIN"
    rep["why"] = (f"perp cheaper on {wins_perp}/{wins_perp + wins_margin} symbols at "
                  f"{leverage:.2f}x. " + (
                      "ACCESS STILL GATES THIS -- see `access`" if wins_perp > wins_margin else
                      "Funding is charged on the whole notional while interest is charged only on "
                      "the borrowed part, which is why margin wins a comparison the raw rates make "
                      "look closer than it is"))
    rep["capability_note"] = (
        "COST IS NOT THE ONLY ARGUMENT FOR PERPS AND IT IS THE WEAKER ONE. A spot-margin short "
        "borrows the BASE asset, which is why place_entry refuses SELL and why H1/H7/H11 journal "
        "refusals instead of trades. On perps a short is symmetric. That is a capability gain and "
        "it must be argued on its own terms, never as a funding saving")
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leverage", type=float, default=2.3,
                    help="the leverage the comparison is made at. It MATTERS: margin's cost per "
                         "unit of notional is r*(f-1)/f, so its advantage shrinks as f rises")
    ap.add_argument("--borrow-rate", type=float, default=None,
                    help="override the venue's rate. Absent, it is read; unreadable is UNMEASURED "
                         "and the comparison refuses rather than guessing")
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build(tuple(s.strip() for s in args.symbols.split(",") if s.strip()),
                leverage=float(args.leverage), borrow_rate=args.borrow_rate)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    acc = rep["access"]
    print(f"=== FUNDING vs BORROW === verdict {rep['verdict']} at {rep['leverage']:.2f}x")
    print(f"  ACCESS GATE: {acc['state']} -- {acc['recorded_finding'][:150]}")
    print(f"  borrow rate: {rep.get('borrow_rate')} ({str(rep.get('borrow_rate_why'))[:90]})")
    if rep.get("breakeven_funding_annual") is not None:
        print(f"  break-even funding: {rep['breakeven_funding_annual']:.2%}/yr -- "
              f"{rep['breakeven_why']}")
    for sym, row in rep["symbols"].items():
        if row.get("state"):
            print(f"  [{row['state']:<18}] {sym}")
            continue
        print(f"  [{row['cheaper']:<18}] {sym:<10} funding median {row['median_annual']:+.2%}/yr "
              f"vs margin {row['margin_cost_annual']:.2%}/yr  "
              f"(negative on {row['share_days_negative']:.0%} of days)")
    print(f"  {rep['why']}")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
