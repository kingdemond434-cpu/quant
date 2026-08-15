"""LONG-ONLY SPOT MOMENTUM -- the cross-sectional tilt a spot-only account can actually hold.

WHY THIS IS A NEW STRATEGY AND NOT `xsec_price_mom` WITH A FLAG. `crossasset.xsec_signal_returns`
builds a DOLLAR-NEUTRAL book: it buys the top quantile at +0.5 and shorts the bottom at -0.5. Its
measured Sharpe -- 0.82 on the desk's own dashboard -- describes that book. Remove the short leg
and three things change at once:

  * THE MARKET EXPOSURE COMES BACK. The short leg is what cancelled beta. Long-only is a crypto
    long with a selection overlay on top, and in a 40% drawdown it loses roughly 40% however good
    the selection was. Dollar-neutral was the entire reason the original could be sized calmly.
  * HALF THE SIGNAL IS DISCARDED. Cross-sectional momentum claims the top quantile outperforms the
    BOTTOM. Keeping only the long leg keeps only half of the spread the hypothesis was about.
  * THE BENCHMARK MOVES, and this is the one that turns a real result into a fake one.

**A LONG-ONLY CRYPTO BOOK MUST BE JUDGED AGAINST BUY-AND-HOLD, NEVER AGAINST ZERO.** In a rising
market a long-only tilt makes money whether or not its selection has any skill, so a Sharpe
computed against zero measures the market and credits the strategy. The only quantity selection can
claim is the EXCESS over an equal-weight hold of the same universe, and this module computes that
by default and reports the raw number beside it rather than instead of it. Reporting raw Sharpe
alone here would be the exact shape of the desk's variance-collapse defect: a flattering number
whose denominator quietly excludes the thing that actually drives it.

**SO IT INHERITS NO NUMBER.** Not `xsec_price_mom`'s Sharpe, not its dashboard row, not its name.
A figure measured on a book with a short in it does not describe a book without one, and carrying
it across would be the strongest form of the substitution this desk keeps finding in itself.

Pandas + numpy, pure. import from libs.research.spot_momentum.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from libs.research.crossasset import _inv_vol

__all__ = [
    "DEFAULT_BAND",
    "DEFAULT_GROSS",
    "DEFAULT_Q",
    "SpotMomentumResult",
    "benchmark_returns",
    "evaluate",
    "spot_long_only_returns",
]

#: Top fraction of the universe held. Carried over from the dollar-neutral construction so the
#: LONG leg is the same leg, unchanged -- the difference between the two strategies must be the
#: missing short and nothing else, or a comparison between them measures two changes at once.
DEFAULT_Q = 0.3

#: Turnover band, likewise unchanged from the original.
DEFAULT_BAND = 0.05

#: Gross exposure. 1.0 is FULLY INVESTED, which is what a spot account actually does with its
#: balance -- the dollar-neutral book's 0.5-long/0.5-short is not available here, and holding 0.5
#: long with 0.5 in cash would be a different (lower-beta, lower-return) strategy that nobody
#: asked for. Named and exposed so the choice is visible rather than buried in a magic 0.5.
DEFAULT_GROSS = 1.0


def spot_long_only_returns(
    close: pd.DataFrame,
    signal: pd.DataFrame,
    cost: dict[str, float],
    *,
    q: float = DEFAULT_Q,
    band: float = DEFAULT_BAND,
    gross: float = DEFAULT_GROSS,
    vol_window: int = 30,
    min_names: int = 6,
) -> np.ndarray:
    """Daily net return of a LONG-ONLY, inverse-vol weighted top-quantile spot book.

    Deliberately mirrors `crossasset.xsec_signal_returns` line for line on everything except the
    short leg: same one-bar signal lag, same inverse-vol weighting, same turnover band, same
    per-symbol cost application. A reimplementation that also changed the weighting or the lag
    would make any comparison to the dollar-neutral original meaningless, and the comparison is
    the only way to see what dropping the short leg actually cost.

    NO SHORT LEG AND NO CASH DRAG MODEL. Weights sum to `gross` across the held names; the
    remainder (zero at gross=1.0) earns nothing. A spot account holding stablecoins would earn
    something, and modelling that here would credit the strategy with a yield it did not generate.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    sig_l = signal.shift(1)                       # POINT-IN-TIME: never the current bar's signal
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig_l.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            # TOO FEW NAMES TO RANK: hold what is held rather than liquidating into a thin tape.
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        longs = s.sort_values(ascending=False).index[:k]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw = iv.reindex(longs).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = gross * lw / lw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[c] - prev[c]) * cost.get(c, 1.0e-3) for c in w.index))
        out[t] = price_ret - turn_cost
        prev = w
    return out


def benchmark_returns(close: pd.DataFrame, *, gross: float = DEFAULT_GROSS) -> np.ndarray:
    """EQUAL-WEIGHT BUY-AND-HOLD of the same universe -- the only honest comparison.

    A long-only crypto book makes money in a rising market whether or not its selection has any
    skill. Judged against ZERO it reports the market's return as its own; judged against this, only
    the part selection actually added survives. Costs are deliberately EXCLUDED from the benchmark:
    buy-and-hold trades once, the strategy trades constantly, and charging the benchmark a turnover
    it does not incur would hand the strategy free alpha equal to its own trading costs.
    """
    ret = close.pct_change(fill_method=None)
    return np.asarray(gross * ret.mean(axis=1).fillna(0.0).to_numpy(), dtype="float64")


@dataclass(frozen=True)
class SpotMomentumResult:
    """Raw and EXCESS side by side. Neither is published without the other."""

    n_days: int
    ann_return: float
    ann_vol: float
    sharpe_raw: float
    benchmark_ann_return: float
    benchmark_sharpe: float
    #: THE NUMBER THAT MEANS SOMETHING. Sharpe of (strategy - benchmark).
    sharpe_excess: float
    beta_to_universe: float
    max_drawdown: float

    def as_row(self) -> dict[str, Any]:
        return {
            "n_days": self.n_days,
            "ann_return": round(self.ann_return, 4),
            "ann_vol": round(self.ann_vol, 4),
            "sharpe_raw": round(self.sharpe_raw, 3),
            "benchmark_ann_return": round(self.benchmark_ann_return, 4),
            "benchmark_sharpe": round(self.benchmark_sharpe, 3),
            "sharpe_excess": round(self.sharpe_excess, 3),
            "beta_to_universe": round(self.beta_to_universe, 3),
            "max_drawdown": round(self.max_drawdown, 4),
            "note": ("sharpe_raw MEASURES THE MARKET as much as the strategy: a long-only crypto "
                     "book earns in a rising tape with or without selection skill. sharpe_excess "
                     "is over equal-weight buy-and-hold of the same universe and is the only part "
                     "selection can claim. beta_to_universe near 1.0 confirms this is NOT a "
                     "market-neutral book -- the short leg that removed beta is unavailable on a "
                     "spot venue, so full drawdown risk is retained and must be sized for."),
        }


def _sharpe(r: np.ndarray, ppy: float = 365.0) -> float:
    r = np.asarray(r, dtype="float64")
    r = r[np.isfinite(r)]
    sd = float(r.std())
    return float(r.mean() / sd * np.sqrt(ppy)) if sd > 0 and r.size > 2 else 0.0


def _max_dd(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + np.asarray(r, dtype="float64"))
    peak = np.maximum.accumulate(eq)
    return float(np.min(eq / peak - 1.0)) if eq.size else 0.0


def evaluate(strategy: np.ndarray, benchmark: np.ndarray,
             *, ppy: float = 365.0) -> SpotMomentumResult:
    """Raw, benchmark and EXCESS together, plus the beta that proves it is not neutral."""
    s = np.asarray(strategy, dtype="float64")
    b = np.asarray(benchmark, dtype="float64")
    n = min(s.size, b.size)
    s, b = s[:n], b[:n]
    var_b = float(b.var())
    beta = float(np.cov(s, b)[0, 1] / var_b) if var_b > 0 and n > 2 else 0.0
    return SpotMomentumResult(
        n_days=n,
        ann_return=float(s.mean() * ppy),
        ann_vol=float(s.std() * np.sqrt(ppy)),
        sharpe_raw=_sharpe(s, ppy),
        benchmark_ann_return=float(b.mean() * ppy),
        benchmark_sharpe=_sharpe(b, ppy),
        sharpe_excess=_sharpe(s - b, ppy),
        beta_to_universe=beta,
        max_drawdown=_max_dd(s),
    )
