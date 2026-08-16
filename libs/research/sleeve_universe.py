"""HOW MANY SYMBOLS THE BOOK CAN ACTUALLY TRADE -- capital first, then data, then liquidity.

**THE UNIVERSE WAS A HARDCODED SIX AND THAT IS THE WRONG KIND OF CONSTANT.** Six was right at $193
and wrong at $600 and wrong again at $2,000, and nothing recomputed it. Two failures, in opposite
directions, from one frozen number:

    TOO WIDE  -- publishing 18 symbols on capital that funds 6 produces twelve refused orders and a
                 book that holds a third of what it published. The refusals are honest and the
                 position is still wrong.
    TOO NARROW - holding six names on capital that funds eighteen leaves breadth unbought. The
                 sleeve trades a third as often as it could at identical per-trade edge, which is
                 the ONE way to raise turnover that does not cost anything.

So the width is DERIVED, every run, from the money actually present. Fund more and the book widens
by itself; that is the whole point, and it is why this is arithmetic rather than a setting.

**THE CAPITAL GATE IS THE BINDING ONE AND IT IS SIMPLE ARITHMETIC.** A sleeve's clip is
`equity * leverage * book_frac / n_sleeves`, and it splits that across its own symbols, so

    max_symbols = floor(equity * leverage * book_frac / n_sleeves / min_notional)

Below the venue's minimum an order is not small, it is REFUSED -- which is why this floors rather
than rounding, and why it is checked before anything else. A universe that passes every data and
liquidity test and cannot place an order has passed nothing.

**WIDENING RAISES TURNOVER AND CAPACITY. IT BARELY RAISES BREADTH, AND SAYING SO MATTERS.** The
tempting claim is that 18 symbols is three times the breadth of 6. It is not, because crypto majors
co-move: at a pairwise correlation of 0.7, `k_eff = n/(1+(n-1)rho)` gives 1.33 at n=6 and 1.40 at
n=18. Effectively NOTHING. What widening actually buys is more trades at the SAME per-trade edge --
which is the legitimate way to reach a higher turnover, as against loosening entry thresholds,
which buys trades by lowering the edge on all of them. `breadth_gain` below publishes the honest
number rather than letting the count imply the other one.

**A SYMBOL WITH NO HISTORY IS EXCLUDED, NOT ASSUMED FLAT.** A generator handed a short series
returns zeros, and a sleeve reading zeros publishes 'no signal' where the truth is 'no data'.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["breadth_gain", "capital_supports", "select"]

#: Minimum daily bars a symbol needs before a generator may be run on it. Below this the
#: generator's own lookback (up to 90 days on `producer_margin_stress`) is longer than the series,
#: and it returns a value computed mostly from padding.
MIN_HISTORY_DAYS = 200

#: Typical pairwise correlation between liquid crypto majors, used ONLY to publish the honest
#: breadth gain from widening. Not a measured input to any sizing decision -- the live figure comes
#: from `track_sleeve_correlation`, and this is a stated reference point for a claim about counts.
TYPICAL_SYMBOL_RHO = 0.7


def capital_supports(equity_usd: float, *, leverage: float, book_frac: float,
                     n_sleeves: int, min_notional: float) -> int:
    """How many symbols per sleeve this capital can place an order in. FLOORS, never rounds.

    Returns 0 when the arithmetic does not reach one order -- a real answer, and the one the
    desk spent a month not seeing: at $193 with a $5 floor, four of five sleeves could not place
    a single leg, and every report showed them LIVE.
    """
    if min_notional <= 0 or n_sleeves <= 0:
        return 0
    per_sleeve = float(equity_usd) * float(leverage) * float(book_frac) / float(n_sleeves)
    if per_sleeve <= 0:
        return 0
    return max(0, math.floor(per_sleeve / float(min_notional)))


def breadth_gain(n_from: int, n_to: int, rho: float = TYPICAL_SYMBOL_RHO) -> dict[str, float]:
    """The k_eff a widening actually buys, published so the COUNT cannot imply it.

    Going 6 -> 18 symbols is a 3x count and, at rho 0.7, about a 1.05x breadth. The gain from
    widening is turnover and capacity, not diversification, and a report that showed only the
    count would be read as the opposite.
    """
    def _k(n: int) -> float:
        if n <= 1:
            return float(max(n, 0))
        return n / (1.0 + (n - 1) * float(rho))

    k0, k1 = _k(n_from), _k(n_to)
    return {"rho_assumed": float(rho), "k_eff_from": round(k0, 4), "k_eff_to": round(k1, 4),
            "count_ratio": round(n_to / n_from, 3) if n_from else 0.0,
            "breadth_ratio": round(k1 / k0, 3) if k0 else 0.0}


def select(candidates: tuple[str, ...], *, equity_usd: float, leverage: float, book_frac: float,
           n_sleeves: int, min_notional: float,
           history: dict[str, int] | None = None,
           liquidity: dict[str, float] | None = None) -> dict[str, Any]:
    """The tradeable universe, ranked by liquidity, truncated to what capital supports.

    `history` is {symbol: n_daily_bars}; a symbol absent from it is treated as having NO history and
    excluded, because a missing series and a short one fail the same way inside a generator.

    `liquidity` is {symbol: dollar volume or any monotone proxy}. RANKING, NOT FILTERING: a hard
    liquidity threshold would need a number nobody has measured on this venue, whereas ordering by
    it and taking the top K is a decision the capital gate has already sized. A symbol with no
    liquidity reading ranks LAST rather than being dropped -- unmeasured is not disqualifying, but
    it does not get to outrank a name that was measured.
    """
    hist = history or {}
    liq = liquidity or {}
    cap = capital_supports(equity_usd, leverage=leverage, book_frac=book_frac,
                           n_sleeves=n_sleeves, min_notional=min_notional)

    eligible, rejected = [], {}
    for s in candidates:
        n = int(hist.get(s, 0))
        if n < MIN_HISTORY_DAYS:
            rejected[s] = (f"{n} daily bars against {MIN_HISTORY_DAYS} needed -- a generator with "
                           "a 90-day lookback on a shorter series returns a number computed "
                           "mostly from padding, and the sleeve cannot tell it from a signal")
            continue
        eligible.append(s)

    # -liquidity so the deepest sorts first; the name breaks ties so the universe is deterministic
    # and two runs on the same inputs cannot publish different books.
    eligible.sort(key=lambda s: (-float(liq.get(s, 0.0)), s))
    chosen = eligible[:cap]

    rep: dict[str, Any] = {
        "equity_usd": round(float(equity_usd), 2), "leverage": float(leverage),
        "book_frac": float(book_frac), "n_sleeves": int(n_sleeves),
        "min_notional": float(min_notional),
        "capital_supports": cap,
        "n_candidates": len(candidates), "n_eligible": len(eligible), "n_selected": len(chosen),
        "symbols": tuple(chosen), "rejected": rejected,
        "per_leg_usd": (round(float(equity_usd) * float(leverage) * float(book_frac)
                              / max(1, n_sleeves) / max(1, len(chosen)), 2) if chosen else 0.0),
    }
    if not chosen:
        rep["state"] = "NO-TRADEABLE-UNIVERSE"
        # NAME THE CAUSE THAT ACTUALLY BOUND. An empty universe has two completely different
        # causes with two completely different fixes -- send money, or collect data -- and the
        # first version of this message blamed capital unconditionally. Measured 2026-08-16 on a
        # $1,000 dry run: capital reached ten symbols, the lake carried none, and the report said
        # the legs were too small. That is a diagnostic pointing at the wrong lever, which is
        # worse than no diagnostic because it gets acted on.
        rep["binding_constraint"] = "CAPITAL" if cap == 0 else "DATA"
        if cap == 0:
            rep["why"] = (
                f"CAPITAL: at ${equity_usd:,.2f} equity, {leverage:.2f}x and a {book_frac:.0%} "
                f"slice across {n_sleeves} sleeves, a leg is worth less than the "
                f"${min_notional:,.2f} venue minimum, so capital supports ZERO symbols. The "
                f"sleeves will publish weights and place NOTHING. {len(eligible)} candidate(s) "
                "have the history and are waiting on money")
        else:
            rep["why"] = (
                f"DATA: capital supports {cap} symbol(s) per sleeve, but NONE of the "
                f"{len(candidates)} candidates carries {MIN_HISTORY_DAYS}+ daily bars in the "
                "lake. Money is not the constraint here -- run the lake backfill. Sending more "
                "capital would change nothing")
        return rep

    binding = "CAPITAL" if cap <= len(eligible) else "DATA"
    rep["state"] = "OK"
    rep["binding_constraint"] = binding
    rep["why"] = (
        f"{len(chosen)} symbol(s) per sleeve at ${rep['per_leg_usd']:,.2f} a leg. "
        + (f"CAPITAL binds: {len(eligible)} symbols have the history, money reaches {cap}. "
           "Funding is the lever -- the universe widens by itself as equity rises"
           if binding == "CAPITAL" else
           f"DATA binds: money supports {cap} and only {len(eligible)} of {len(candidates)} "
           "candidates carry enough history. Collect more series to widen"))
    rep["breadth_note"] = (
        "WIDENING BUYS TURNOVER AND CAPACITY, NOT DIVERSIFICATION. See `breadth_gain`: at a "
        f"typical {TYPICAL_SYMBOL_RHO:g} correlation between majors, tripling the symbol count "
        "raises k_eff by about 5%. The gain is more trades at the SAME per-trade edge, which is "
        "the only honest way to raise turnover -- loosening entry thresholds buys trades by "
        "lowering the edge on every one of them")
    return rep
