"""Laddered dip accumulation -- a CANDIDATE mechanism, generated for the gauntlet, not for capital.

WHAT THIS IS. An external practitioner's "red-day DCA": a finite budget split into N tranches,
released by four independent trigger types as price falls, so that a deeper drawdown buys more
size at worse prices without any single trigger being able to spend the book.

WHAT IT IS NOT. It is not promoted, deployed, or recommended. It enters the desk the way every
other candidate does -- backtest gauntlet as a SCREEN with zero promotion authority, then
pre-registered forward evidence. It is written here so the claim can be MEASURED rather than
argued about, which is the only thing that distinguishes this desk from the video it came from.

THE HONEST PRIOR IS POOR, and it is recorded before any test so the result cannot be rationalised
afterwards. The source presents this alongside an unfalsifiable market call ("we will never see
these prices again") and a fixed 10x target. Dip-buying into a downtrend is the classic shape of
a strategy that prints small wins for years and gives it all back in one regime -- it is short
volatility wearing a friendly name. The desk's own graveyard already holds dip-buying variants.

WHAT IS NEVERTHELESS WORTH EXTRACTING, independent of whether the edge exists. The BUDGET
DISCIPLINE is a genuine execution improvement and it generalises far past this mechanism:
scaled entries across a move, with a hard tranche count, mean no single entry can be early
enough to matter and the average fill improves monotonically as the move extends. That property
is what makes a laddered entry survivable where a single conviction entry is not, and it is
testable separately from the dip thesis.

THE TRIGGERS, from the source, kept verbatim so the test is of THEIR claim and not of my
improvement of it:
  * intraday drawdown from the session open crossing a ladder of depths
  * a daily close below a threshold
  * N consecutive lower closes, none of which individually tripped the close threshold
  * absolute price levels
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np

#: Intraday drawdown depths (fraction, positive = down) from the session open. Each level fires
#: at most ONCE per session -- an 18% day buys six tranches, not six-hundred.
INTRADAY_LADDER = (0.047, 0.070, 0.095, 0.120, 0.150, 0.180)
#: Close-to-close fall that releases a tranche on its own.
CLOSE_TRIGGER = 0.033
#: Consecutive lower closes that release a tranche when none individually tripped CLOSE_TRIGGER.
#: This is the slow-bleed capture: a 3%/2%/1% sequence trips nothing else and is exactly the
#: shape of the drawdowns that quietly do the damage.
CONSECUTIVE_RED = 3
#: Total tranches the budget is cut into. THE BINDING CONSTRAINT -- once spent, spent.
N_TRANCHES = 15


class Fill(NamedTuple):
    bar: int
    trigger: str
    price: float
    tranche: int


class LadderResult(NamedTuple):
    fills: tuple[Fill, ...]
    spent_tranches: int
    avg_price: float
    final_price: float
    unspent: int
    why: str

    @property
    def pnl_fraction(self) -> float:
        """Return on deployed capital only. Unspent tranches earn nothing and are NOT counted as
        a win -- a ladder that never fires has no edge, it has an opinion it never expressed."""
        if not self.fills or self.avg_price <= 0:
            return 0.0
        return float(self.final_price / self.avg_price - 1.0)


def run_ladder(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, *,
               intraday_ladder: tuple[float, ...] = INTRADAY_LADDER,
               close_trigger: float = CLOSE_TRIGGER,
               consecutive_red: int = CONSECUTIVE_RED,
               n_tranches: int = N_TRANCHES,
               price_levels: tuple[float, ...] = ()) -> LadderResult:
    """Walk the bars once, releasing at most one tranche per trigger per bar.

    CAUSAL BY CONSTRUCTION. Every decision uses only the current bar's open/low and closes at or
    before the current index. There is no path by which a later bar informs an earlier fill --
    which matters more here than usual, because the natural way to write a dip-buyer is to scan
    for the lows first, and that version backtests beautifully and is worthless.

    A fill at the ladder depth assumes the level traded, which the bar's low evidences. That is
    optimistic on slippage and deliberately so: if the mechanism cannot clear the gauntlet even
    with a generous fill assumption, tightening the assumption cannot rescue it.
    """
    o = np.asarray(open_, dtype="float64")
    h = np.asarray(high, dtype="float64")
    lo = np.asarray(low, dtype="float64")
    c = np.asarray(close, dtype="float64")
    n = len(c)
    if not (len(o) == len(h) == len(lo) == n) or n < 2 or n_tranches < 1:
        return LadderResult((), 0, 0.0, float(c[-1]) if n else 0.0, n_tranches,
                            "UNRUNNABLE: ragged or empty series")

    fills: list[Fill] = []
    used_levels: set[float] = set()
    red_run = 0

    for i in range(1, n):
        if len(fills) >= n_tranches:
            break
        # --- intraday ladder: depth measured from THIS session's open, level fires once ever
        if o[i] > 0:
            depth = (o[i] - lo[i]) / o[i]
            for lvl in intraday_ladder:
                if len(fills) >= n_tranches:
                    break
                if depth >= lvl and lvl not in used_levels:
                    used_levels.add(lvl)
                    fills.append(Fill(i, f"intraday_{lvl:.3f}", float(o[i] * (1 - lvl)),
                                      len(fills) + 1))
        # --- close-to-close
        prev, cur = c[i - 1], c[i]
        fell = prev > 0 and (prev - cur) / prev >= close_trigger
        if fell and len(fills) < n_tranches:
            fills.append(Fill(i, "close", float(cur), len(fills) + 1))
        # --- consecutive lower closes that did NOT individually trip the close trigger
        if cur < prev and not fell:
            red_run += 1
            if red_run >= consecutive_red and len(fills) < n_tranches:
                fills.append(Fill(i, f"red_x{red_run}", float(cur), len(fills) + 1))
                red_run = 0
        elif cur >= prev:
            red_run = 0
        # --- absolute price levels, each once
        for lvl in price_levels:
            if len(fills) >= n_tranches:
                break
            if lo[i] <= lvl and lvl not in used_levels:
                used_levels.add(lvl)
                fills.append(Fill(i, f"level_{lvl:g}", float(lvl), len(fills) + 1))

    if not fills:
        return LadderResult((), 0, 0.0, float(c[-1]), n_tranches,
                            "no trigger fired -- the ladder held an opinion it never expressed")
    avg = float(np.mean([f.price for f in fills]))
    return LadderResult(tuple(fills), len(fills), avg, float(c[-1]), n_tranches - len(fills),
                        f"{len(fills)}/{n_tranches} tranches at avg {avg:.2f} "
                        f"vs final {c[-1]:.2f}")


def ladder_returns(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   *, window: int = 60,
                   intraday_ladder: tuple[float, ...] = INTRADAY_LADDER,
                   close_trigger: float = CLOSE_TRIGGER,
                   consecutive_red: int = CONSECUTIVE_RED,
                   n_tranches: int = N_TRANCHES,
                   price_levels: tuple[float, ...] = ()) -> np.ndarray:
    """Per-window returns, so the mechanism can be scored by the REAL validate() like any other.

    Non-overlapping windows on purpose. Overlapping windows share bars, which inflates the
    apparent number of independent observations and every statistic built on it -- the same
    defect that inflates a rolling stickiness score, and the reason a dip-buyer evaluated on
    rolling windows looks steadier than it is.
    """
    c = np.asarray(close, dtype="float64")
    out: list[float] = []
    for s in range(0, len(c) - window, window):
        e = s + window
        r = run_ladder(open_[s:e], high[s:e], low[s:e], close[s:e],
                       intraday_ladder=intraday_ladder, close_trigger=close_trigger,
                       consecutive_red=consecutive_red, n_tranches=n_tranches,
                       price_levels=price_levels)
        out.append(r.pnl_fraction if r.fills else 0.0)
    return np.asarray(out, dtype="float64")
