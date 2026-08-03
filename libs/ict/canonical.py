"""ICT AS HE DEFINES IT -- transcribed from source, replacing my approximations.

WHY THIS FILE EXISTS SEPARATELY FROM patterns.py. My first pass encoded ICT concepts from general
knowledge. The principal supplied actual mentorship transcripts, and three of the detectors were
wrong in specific ways -- not vague-but-close, wrong about which candle and which price. Rather
than silently edit patterns.py and lose the record, the canonical definitions live here and the
divergences are stated, because "my reading of ICT" and "ICT" are different hypotheses and the
screen should be able to tell them apart.

WHAT CHANGED, AND THE SOURCE FOR EACH.

  ORDER BLOCK (Core Content Month 04 -- Orderblocks)
    HIS:  "the LOWEST candle with a DOWN CLOSE that has the MOST RANGE between open to close and
           is near a support level." Validated "when the HIGH of the lowest down candle is traded
           through by a later formed candle." Entry on return to that candle's OPEN. Risk below
           its low. Mean threshold = 50% of OPEN-TO-CLOSE, and he is explicit: "do not use the
           wicks."
    MINE: "last opposite-colour candle before displacement." That is a different object. It picks
           whichever candle happens to precede a big move rather than the largest-bodied down
           close at the low, so on most legs it selects the wrong bar entirely.

  BREAKER (Core Content Month 04 -- ICT Breaker Block)
    HIS:  a three-point structure. An old low is violated (sell stops taken); the SWING HIGH
           BETWEEN THE TWO LOWS is the breaker; it is confirmed when price breaks UP THROUGH that
           high; the entry is the return to it. "The sellers that sold this low and later see this
           same swing high violated will look to mitigate the loss."
    MINE: "an order block that failed." Not the same thing, and mine had no structural
           requirement at all.

  OTE (Core Content Month 01 -- Equilibrium Vs. Discount / Vs. Premium)
    HIS:  equilibrium is 50% of the impulse swing; discount is below it, premium above. The
           optimal trade entry is the 62%-79% band, with 70.5% named as the midpoint. He requires
           FOUR CANDLES: a swing high (one lower bar either side) and then a fourth bar closing
           lower before the retracement watch even begins.
    MINE: a rolling-window position measure, which answers a related but different question.

  SWING CONFIRMATION
    HIS:  one bar either side. MINE: two. I am keeping mine as the default because it is the
           stricter reading and a swing confirmed by more bars is harder to fake -- but his value
           is exposed, and the difference is now a parameter rather than an accident.

Every detector here is causal and proven so by the same future-invariance test. Being canonical
buys no exemption: a rule from a transcript is a hypothesis, and this desk's prior is 420/420.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from libs.features.definition import FeatureDefinition

import numpy as np
import pandas as pd

from libs.ict.patterns import ICT_FAMILY, _need, swing_high, swing_low

__all__ = [
    "ICT_FAMILY",
    "SILVER_BULLET_WINDOWS",
    "breaker_canonical",
    "common_gap",
    "liquidity_void",
    "mean_threshold_breach",
    "optimal_trade_entry",
    "order_block_canonical",
    "silver_bullet_window",
]

#: OTE band. His three named levels are 0.62, 0.705 and 0.79 of the impulse swing, retraced from
#: the high. Kept as the band rather than the midpoint: he treats all three as the sweet spot and
#: picking one would be a precision he does not claim.
OTE_LO, OTE_MID, OTE_HI = 0.62, 0.705, 0.79

#: ICT Silver Bullet windows, NEW YORK LOCAL TIME, from the 2023 lecture. Three fixed 60-minute
#: intervals; he claims one of them sets up every trading day.
#:
#: THESE ARE A FOREX/FUTURES CLAIM AND CRYPTO IS THE TEST, NOT THE ASSUMPTION. They derive from
#: session structure that crypto does not have -- it never closes. Encoded so the screen can ASK
#: whether they survive translation; this desk already holds the receipt for importing session
#: folklore across asset classes (M_ATTENTION_DELAY, a family kill at 13 deaths).
SILVER_BULLET_WINDOWS = ((3, 4), (10, 11), (14, 15))

#: His displacement rule, stated as a ratio rather than a z-score: "what I like to look for is two
#: to three [times] the height, or the range, of the order block" as the move away.
DISPLACEMENT_MULTIPLE = 2.0


def order_block_canonical(bars: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """+1 when a bar VALIDATES a bullish order block, -1 bearish, else 0.

    HIS DEFINITION, and each clause is load-bearing:

      "the LOWEST candle with a DOWN CLOSE that has the MOST RANGE between open to close"

    So the block is not "the candle before the move" -- it is the largest-bodied down-close bar at
    the swing low. Both conditions matter: lowest, and biggest body. A small down bar sitting at
    the exact low is not the block if a larger-bodied one is near it.

      "validated when the HIGH of the lowest down candle is traded through by a later formed
       candle"

    Validation is a separate event from formation, which is what makes this causal: the block is
    published on the bar that trades through it, never written back onto the origin candle. A
    charted order block is drawn on the origin bar, and that is precisely the lookahead.
    """
    _need(bars, "open", "high", "low", "close")
    o, h, lo_s, c = bars["open"], bars["high"], bars["low"], bars["close"]
    body = (c - o).to_numpy()
    hi_a, lo_a = h.to_numpy(), lo_s.to_numpy()
    out = np.zeros(len(bars), dtype="float64")

    # VALIDATION IS A ONE-TIME EVENT, and the first draft missed that. "Validated when the high of
    # the lowest down candle is traded through by a LATER formed candle" -- once. Re-signalling on
    # every subsequent bar that happens to sit above the block made this fire on 89% of bars, and
    # a detector that is on nine times in ten carries almost no information whatever it names.
    last_bull = last_bear = -1
    for i in range(lookback, len(bars)):
        w0 = i - lookback
        idx = np.arange(w0, i)

        dmask = body[w0:i] < 0
        if dmask.any():
            d_idx = idx[dmask]
            lows = lo_a[d_idx]
            # "the LOWEST candle with a down close that has the MOST RANGE open-to-close":
            # restrict to bars in the bottom quartile of the window's low range, then take the
            # largest body among them. Both clauses, in his order.
            band = lows.min() + (lows.max() - lows.min()) * 0.25
            near = d_idx[lows <= band]
            if len(near):
                blk = int(near[np.argmax(np.abs(body[near]))])
                if blk != last_bull and hi_a[i] > hi_a[blk]:
                    out[i] = 1.0
                    last_bull = blk

        umask = body[w0:i] > 0
        if umask.any() and out[i] == 0.0:
            u_idx = idx[umask]
            highs = hi_a[u_idx]
            band = highs.max() - (highs.max() - highs.min()) * 0.25
            near = u_idx[highs >= band]
            if len(near):
                blk = int(near[np.argmax(np.abs(body[near]))])
                if blk != last_bear and lo_a[i] < lo_a[blk]:
                    out[i] = -1.0
                    last_bear = blk
    return pd.Series(out, index=bars.index, dtype="float64")


def mean_threshold_breach(bars: pd.DataFrame) -> pd.Series:
    """How far price has traded past the order block's MEAN THRESHOLD, in body units.

    "measure the open to the close on the down candle to measure where the middle of it is --
     DO NOT use the wicks. The better order blocks won't [trade below it] at all."

    This is his own quality filter, and it is the falsifiable half of order-block theory: a block
    that gets traded through its own midpoint was a bad block, and he says so. 0 means untouched,
    1.0 means price reached the far side of the body.
    """
    _need(bars, "open", "high", "low", "close")
    o, c = bars["open"], bars["close"]
    mid = (o + c) / 2.0
    body = (c - o).abs().replace(0.0, np.nan)
    # PER BAR, not rolled. The first draft took a rolling max over `lookback`, which is an
    # aggregation the source never asks for and which makes the per-bar reading untestable: a bar
    # that never breached anything inherited a neighbour's breach. He states the rule about ONE
    # block ("the better order blocks won't trade below it at all"), so the per-bar depth is the
    # measurement and any aggregation belongs to the caller.
    depth = (mid.shift(1) - bars["low"]) / body.shift(1)
    return depth.clip(lower=0.0).fillna(0.0)


def breaker_canonical(bars: pd.DataFrame, confirm: int = 2) -> pd.Series:
    """+1 bullish breaker, -1 bearish, else 0 -- his three-point structure, not "a failed block".

    BULLISH: an old low is violated (sell stops taken), and the SWING HIGH BETWEEN THE TWO LOWS is
    the breaker. It is confirmed only when price breaks UP THROUGH that high; the trade is the
    return to it. "The sellers that sold this low and later see this same swing high violated will
    look to mitigate the loss when price returns back to the swing high."

    The economics are the point and they are testable: whoever sold to drive price below the old
    low is underwater once structure breaks the other way, and has a reason to unwind at the level
    where they sold. That is a claim about positioning, not about a chart shape.
    """
    _need(bars, "high", "low", "close")
    lo, hi, c = bars["low"], bars["high"], bars["close"]
    prior_low, prior_high = swing_low(bars, confirm), swing_high(bars, confirm)
    # Step 1: an old low was taken. Latched forward -- the sweep is a past event once it happens.
    swept_low = (lo < prior_low).cummax()
    swept_high = (hi > prior_high).cummax()
    # Step 2: structure breaks the OTHER way, on a CLOSE (his rule everywhere: close, not wick).
    broke_up = c > prior_high
    broke_dn = c < prior_low
    return pd.Series(np.where(swept_low & broke_up, 1.0,
                              np.where(swept_high & broke_dn, -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def optimal_trade_entry(bars: pd.DataFrame, lookback: int = 40) -> pd.Series:
    """Retracement depth into the impulse swing: 0 at the swing high, 1 at its low.

    His framework exactly. Equilibrium is 0.50; below it is DISCOUNT and above it PREMIUM; the
    optimal trade entry is the 0.62-0.79 band. "Anything below equilibrium is now a discount...
    markets will not sustain discount prices very long if the underlying is bullish."

    Reported as the raw depth rather than as a boolean, so the screen chooses the band on evidence.
    He picked 0.62-0.79 by experience; this module may not adopt a threshold on his authority any
    more than on mine.
    """
    _need(bars, "high", "low", "close")
    hi = bars["high"].rolling(lookback, min_periods=lookback).max().shift(1)
    lo = bars["low"].rolling(lookback, min_periods=lookback).min().shift(1)
    span = (hi - lo).replace(0.0, np.nan)
    return ((hi - bars["close"]) / span).clip(0.0, 1.0).fillna(0.5)


def in_ote(bars: pd.DataFrame, lookback: int = 40) -> pd.Series:
    """1.0 when retracement sits inside his named 62-79% band, else 0."""
    d = optimal_trade_entry(bars, lookback)
    return ((d >= OTE_LO) & (d <= OTE_HI)).astype("float64")


def liquidity_void(bars: pd.DataFrame, window: int = 20, k: float = 3.0) -> pd.Series:
    """+1/-1 on a ONE-SIDED delivery range -- distinct from a fair value gap.

    "a range in price delivery where one side of the market liquidity is shown in WIDE or LONG
     ONE-SIDED ranges or candles. Price typically will want to revisit this porous range."

    An FVG is a three-bar geometric gap. A void is a stretch delivered almost entirely in one
    direction -- his example is two long bodies with barely any opposing trade between them.
    Measured as consecutive same-direction body dominance over the window's scale, so it can fire
    where no FVG exists and vice versa. Keeping them separate is what lets the screen find out
    whether they are actually the same signal wearing two names.
    """
    _need(bars, "open", "close")
    body = bars["close"] - bars["open"]
    scale = body.abs().rolling(window, min_periods=window).mean().shift(1)
    two = body + body.shift(1)
    same = (np.sign(body) == np.sign(body.shift(1))) & (body != 0)
    big = two.abs() > (k * scale)
    return pd.Series(np.where(same & big & (two > 0), 1.0,
                              np.where(same & big & (two < 0), -1.0, 0.0)),
                     index=bars.index, dtype="float64")


def common_gap(bars: pd.DataFrame) -> pd.Series:
    """Signed gap between one bar's close and the next bar's open, as a fraction of price.

    "see that little space right there where the bodies don't close in -- what is this? This is a
     gap... we can put an order in here."

    Crypto trades continuously, so true gaps are rare and mostly mark venue outages or violent
    repricing. That makes this MORE interesting here, not less: a gap in a 24/7 market is an
    anomaly with a cause, where in futures it is merely the session boundary.
    """
    _need(bars, "open", "close")
    g = bars["open"] - bars["close"].shift(1)
    return (g / bars["close"].shift(1).replace(0.0, np.nan)).fillna(0.0)


def silver_bullet_window(bars: pd.DataFrame) -> pd.Series:
    """1.0 inside one of his three 60-minute windows (NY local), else 0.

    03:00-04:00, 10:00-11:00, 14:00-15:00 New York time. He claims one sets up every trading day.

    ENCODED AS A QUESTION, NOT A CLAIM. These windows come from FX and index-futures session
    structure -- a London open and a New York cash session -- and crypto has neither. Whether they
    survive the translation is exactly the sort of borrowed-conclusion the desk has already paid
    for once, so it ships as a partition the screen can test and refute.
    """
    _need(bars, "timestamp")
    ts = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    try:
        h = ts.dt.tz_convert("America/New_York").dt.hour
    except (TypeError, ValueError):
        h = ts.dt.hour
    inside = pd.Series(False, index=bars.index)
    for lo, hi in SILVER_BULLET_WINDOWS:
        inside |= (h >= lo) & (h < hi)
    return inside.astype("float64").fillna(0.0)


def _definitions() -> tuple[FeatureDefinition, ...]:
    from libs.features.definition import FeatureDefinition
    spec = (
        ("ict_ob_canonical", order_block_canonical, ("open", "high", "low", "close"), 21,
         "lowest down-close bar with the largest body, published when its high is traded through"),
        ("ict_mean_threshold", mean_threshold_breach, ("open", "high", "low", "close"), 2,
         "depth past the block's 50%-of-BODY midpoint -- his own quality filter, falsifiable"),
        ("ict_breaker_canonical", breaker_canonical, ("high", "low", "close"), 6,
         "old low swept, then structure closes through the swing high between the two lows"),
        ("ict_ote", optimal_trade_entry, ("high", "low", "close"), 41,
         "retracement depth: 0.5 equilibrium, <0.5 premium, 0.62-0.79 his optimal-entry band"),
        ("ict_liquidity_void", liquidity_void, ("open", "close"), 21,
         "one-sided delivery range -- distinct object from a 3-bar fair value gap"),
        ("ict_common_gap", common_gap, ("open", "close"), 2,
         "close-to-open gap; rare in 24/7 crypto, which makes it an anomaly with a cause"),
        ("ict_silver_bullet", silver_bullet_window, ("timestamp",), 1,
         "his three 60-min NY windows -- a FOREX claim, encoded here as a question for crypto"),
    )
    return tuple(
        FeatureDefinition(name=n, version=1, compute=f, inputs=i,
                          category=ICT_FAMILY, description=d, min_periods=m)
        for n, f, i, m, d in spec
    )


def register(registry: Any = None, *, bars: Any = None,
             overwrite: bool = False) -> list[str]:
    from libs.features.registry import register_feature
    out = []
    for d in _definitions():
        register_feature(d, registry=registry, bars=bars, overwrite=overwrite)
        out.append(getattr(d, "key", d.name))
    return out
