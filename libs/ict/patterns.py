"""ICT / SMC PATTERNS -- mechanical, causal, falsifiable. A second strategy family.

WHY THIS IS WORTH BUILDING, AND WHAT IS BEING CLAIMED. ICT ("inner circle trader") concepts --
fair value gaps, order blocks, liquidity sweeps, market structure shifts -- have a poor
reputation, and largely a deserved one: they are usually taught as chart annotations drawn AFTER
the move, which is unfalsifiable by construction. But the underlying objects are mechanically
definable, and once defined they are testable like anything else.

NOTHING HERE CLAIMS EDGE. These are DETECTORS. They say "a bullish fair value gap opened at bar
i", not "buy it". Whether any of them predicts anything is a question for the gauntlet, and the
desk's own record -- 420/420 rejections -- is the prior. A detector that fires correctly and
predicts nothing is a successful detector and a dead hypothesis, and those are different verdicts.

THE FAILURE THIS MODULE IS BUILT AGAINST IS LOOKAHEAD, and it is not hypothetical: it is how
almost every ICT backtest lies. Three specific ways, all closed here:

  SWING CONFIRMATION. A swing high at bar i is only knowable after `confirm` bars have printed to
  its right. Marking it at bar i uses the future. Every swing here is published with the lag it
  actually needed, so a "prior high" is one the desk could have known about.
  SWEEP DIRECTION. "Price swept liquidity and reversed" is normally judged from the reversal --
  which is the thing being predicted. A sweep here is defined only by the close relative to the
  level it exceeded, on the sweeping bar itself.
  GAP MITIGATION. A gap is not marked "unfilled" using later bars; fill state is carried forward
  bar by bar, so the value at time t reflects only what had happened by t.

Every detector is a causal pd.Series and the suite proves it with the desk's own future-invariance
test (libs.features.causal_guard), which mutates future bars and asserts past values do not move.
That test is the whole reason this family is admissible at all.

Pure pandas/numpy. No I/O, no network, no order paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from libs.features.definition import FeatureDefinition

import numpy as np
import pandas as pd

__all__ = [
    "ICT_FAMILY",
    "breaker_block",
    "displacement",
    "fair_value_gap",
    "liquidity_sweep",
    "market_structure_shift",
    "order_block",
    "premium_discount",
    "swing_high",
    "swing_low",
]

#: Family label. Distinct from the systematic sleeve on purpose -- P16 judges families JOINTLY by
#: marginal portfolio contribution, and a second family is what makes MC_i defined at all. The
#: coexistence organ arms from a DATA condition (a second family with a performance record), so
#: naming the family here does not fake that arming; it makes it possible.
ICT_FAMILY = "discretionary_ict"

#: Bars to the RIGHT that must print before a swing point is confirmed. This lag is the difference
#: between a tradeable level and a drawn one: without it, every "prior high" is one the chart knew
#: about only in hindsight, and the whole family becomes unfalsifiable.
DEFAULT_CONFIRM = 2


def _need(bars: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in bars.columns]
    if missing:
        raise KeyError(f"ICT patterns need {missing} -- got {list(bars.columns)}")


def swing_high(bars: pd.DataFrame, confirm: int = DEFAULT_CONFIRM) -> pd.Series:
    """Price of the most recent CONFIRMED swing high, forward-filled.

    A swing high is a bar whose high exceeds `confirm` bars either side. The right-hand side is
    the causal problem: it cannot be known until those bars print, so the level is published
    `confirm` bars late. Everything downstream that references "the prior high" inherits that
    honesty for free.
    """
    _need(bars, "high")
    h = bars["high"]
    is_top = pd.Series(True, index=bars.index)
    for k in range(1, confirm + 1):
        is_top &= h > h.shift(k)
        is_top &= h > h.shift(-k)
    # Published only once the confirming bars exist: shift FORWARD by `confirm`.
    level = h.where(is_top).shift(confirm)
    return level.ffill()


def swing_low(bars: pd.DataFrame, confirm: int = DEFAULT_CONFIRM) -> pd.Series:
    _need(bars, "low")
    lo = bars["low"]
    is_bot = pd.Series(True, index=bars.index)
    for k in range(1, confirm + 1):
        is_bot &= lo < lo.shift(k)
        is_bot &= lo < lo.shift(-k)
    return lo.where(is_bot).shift(confirm).ffill()


def fair_value_gap(bars: pd.DataFrame) -> pd.Series:
    """+1 bullish FVG, -1 bearish FVG, 0 none -- on the bar that COMPLETES the three-bar pattern.

    The one genuinely unambiguous ICT object. A bullish gap exists when bar i's low is above bar
    (i-2)'s high: no trade occurred in that band, so the book left an unfilled imbalance. Bearish
    is the mirror. All three bars have closed when this fires, so it needs no lag.

    Deliberately NOT filtered by size here. Whether a 2bp gap and a 200bp gap behave alike is a
    question for the screen, and pre-filtering on a threshold chosen by eye is how a detector
    quietly becomes a fitted strategy.
    """
    _need(bars, "high", "low")
    hi, lo = bars["high"], bars["low"]
    bull = lo > hi.shift(2)
    bear = hi < lo.shift(2)
    return pd.Series(np.where(bull, 1.0, np.where(bear, -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def fvg_size(bars: pd.DataFrame) -> pd.Series:
    """Width of the gap as a fraction of price, signed. Zero when no gap."""
    _need(bars, "high", "low", "close")
    hi, lo, c = bars["high"], bars["low"], bars["close"]
    bull = (lo - hi.shift(2)).where(lo > hi.shift(2), 0.0)
    bear = (hi - lo.shift(2)).where(hi < lo.shift(2), 0.0)
    return ((bull + bear) / c.replace(0.0, np.nan)).fillna(0.0)


def displacement(bars: pd.DataFrame, window: int = 20, k: float = 2.0) -> pd.Series:
    """+1/-1 when a bar's BODY exceeds k x the trailing mean body -- energetic, directional intent.

    Body, not range: a long-wicked bar that closes where it opened is indecision, and counting it
    as displacement is how a doji becomes a signal. The trailing window is strictly prior
    (`shift(1)`), so the bar being judged never contributes to its own threshold -- a subtle
    normalisation leak that flatters every large bar.
    """
    _need(bars, "open", "close")
    body = (bars["close"] - bars["open"])
    scale = body.abs().rolling(window, min_periods=window).mean().shift(1)
    big = body.abs() > (k * scale)
    return pd.Series(np.where(big & (body > 0), 1.0, np.where(big & (body < 0), -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def liquidity_sweep(bars: pd.DataFrame, confirm: int = DEFAULT_CONFIRM) -> pd.Series:
    """+1 sell-side sweep (took a prior low, closed back above), -1 buy-side sweep. 0 otherwise.

    THE DEFINITION IS THE WHOLE POINT. "Price swept liquidity and reversed" is normally judged
    from the reversal that followed -- which is the thing a strategy would be trying to predict,
    so scoring it that way is circular and the backtest cannot fail. Here a sweep is settled ON
    THE SWEEPING BAR: the low pierced a confirmed prior swing low AND the close returned above it.
    Whether anything follows is left entirely to the label.
    """
    _need(bars, "high", "low", "close")
    hi, lo, c = bars["high"], bars["low"], bars["close"]
    prior_low, prior_high = swing_low(bars, confirm), swing_high(bars, confirm)
    sell_side = (lo < prior_low) & (c > prior_low)
    buy_side = (hi > prior_high) & (c < prior_high)
    return pd.Series(np.where(sell_side, 1.0, np.where(buy_side, -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def market_structure_shift(bars: pd.DataFrame, confirm: int = DEFAULT_CONFIRM) -> pd.Series:
    """+1 when close breaks the confirmed prior swing HIGH, -1 the prior swing LOW, else 0.

    CLOSE, not wick. A wick through a level is exactly the sweep above; treating it as a
    structure break makes the two detectors fire together and neither means anything.
    """
    _need(bars, "close")
    c = bars["close"]
    up = c > swing_high(bars, confirm)
    dn = c < swing_low(bars, confirm)
    return pd.Series(np.where(up, 1.0, np.where(dn, -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def order_block(bars: pd.DataFrame, window: int = 20, k: float = 2.0) -> pd.Series:
    """+1/-1 marking the last opposite-colour candle BEFORE a displacement leg; else 0.

    Published on the displacement bar, never retroactively stamped on the origin candle: writing
    the mark back onto bar i-1 would put information at a timestamp that did not have it, which
    is the single most common lookahead in charted order-block studies. The value here answers
    "as of now, a block formed one bar ago", which is what a live system could act on.
    """
    _need(bars, "open", "close")
    disp = displacement(bars, window, k)
    prev_up = (bars["close"].shift(1) > bars["open"].shift(1))
    prev_dn = (bars["close"].shift(1) < bars["open"].shift(1))
    bull_ob = (disp > 0) & prev_dn      # down candle before an up leg
    bear_ob = (disp < 0) & prev_up
    return pd.Series(np.where(bull_ob, 1.0, np.where(bear_ob, -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def breaker_block(bars: pd.DataFrame, confirm: int = DEFAULT_CONFIRM,
                  window: int = 20, k: float = 2.0) -> pd.Series:
    """+1/-1 when an order block FAILED -- structure broke the other way after it formed.

    A breaker is the honest half of order-block theory: it records that the level did NOT hold.
    Detecting failure is strictly easier than detecting success and is worth having for exactly
    that reason -- a family that can only recognise its own confirmations is not falsifiable.
    """
    ob = order_block(bars, window, k)
    mss = market_structure_shift(bars, confirm)
    had_bull = (ob > 0).cummax() if len(ob) else ob
    had_bear = (ob < 0).cummax() if len(ob) else ob
    broke_dn = (mss < 0) & had_bull
    broke_up = (mss > 0) & had_bear
    return pd.Series(np.where(broke_dn, -1.0, np.where(broke_up, 1.0, 0.0)),
                     index=bars.index, dtype="float64")


def premium_discount(bars: pd.DataFrame, window: int = 50) -> pd.Series:
    """Where price sits in the trailing dealing range: 0 = range low, 1 = high, 0.5 equilibrium.

    The one ICT idea that is simply a normalisation, and useful precisely because it is boring.
    The range EXCLUDES the current bar (`shift(1)`), so a new extreme cannot define the range it
    just broke -- which would pin the value at 0 or 1 exactly when it is most interesting.
    """
    _need(bars, "high", "low", "close")
    hi = bars["high"].rolling(window, min_periods=window).max().shift(1)
    lo = bars["low"].rolling(window, min_periods=window).min().shift(1)
    span = (hi - lo).replace(0.0, np.nan)
    return ((bars["close"] - lo) / span).clip(0.0, 1.0).fillna(0.5)


#: Registered as versioned FeatureDefinitions so this family enters the funnel through exactly the
#: same door as everything else -- same registry, same causal guard, same screen, same gauntlet.
#: A "discretionary" family that bypassed the validation path would be a second desk, not a second
#: sleeve, and P16 governs sleeves of ONE desk competing for one capital base.
ICT_FEATURES: tuple[Any, ...] = ()


def _definitions() -> tuple[FeatureDefinition, ...]:
    from libs.features.definition import FeatureDefinition
    spec = (
        ("ict_fvg", fair_value_gap, ("high", "low"), 3,
         "fair value gap: +1 bullish, -1 bearish, on the bar completing the 3-bar imbalance"),
        ("ict_fvg_size", fvg_size, ("high", "low", "close"), 3,
         "signed gap width as a fraction of price; unfiltered by size on purpose"),
        ("ict_displacement", displacement, ("open", "close"), 21,
         "body exceeds k x trailing mean body -- directional intent, not range"),
        ("ict_sweep", liquidity_sweep, ("high", "low", "close"), 6,
         "pierced a confirmed swing level and closed back inside, settled on the sweeping bar"),
        ("ict_mss", market_structure_shift, ("high", "low", "close"), 6,
         "CLOSE through a confirmed swing level -- wick-through is the sweep, not a break"),
        ("ict_order_block", order_block, ("open", "close"), 21,
         "last opposite-colour candle before displacement, published on the displacement bar"),
        ("ict_breaker", breaker_block, ("open", "high", "low", "close"), 21,
         "an order block that FAILED -- the falsifiable half of block theory"),
        ("ict_premium_discount", premium_discount, ("high", "low", "close"), 51,
         "position in the trailing dealing range, 0.5 = equilibrium; current bar excluded"),
    )
    return tuple(
        FeatureDefinition(name=n, version=1, compute=f, inputs=i,
                          category=ICT_FAMILY, description=d, min_periods=m)
        for n, f, i, m, d in spec
    )


def register(registry: Any = None, *, bars: Any = None,
             overwrite: bool = False) -> list[str]:
    """Register every ICT detector. Returns the keys registered.

    `bars` is passed straight through to the desk's own `register_feature`, which runs the
    leakage proof at REGISTRATION time when given data -- so a detector that starts reading the
    future is refused entry rather than discovered later by a screen that liked its results.
    """
    from libs.features.registry import register_feature
    out = []
    for d in _definitions():
        register_feature(d, registry=registry, bars=bars, overwrite=overwrite)
        out.append(d.key if hasattr(d, "key") else d.name)
    return out
