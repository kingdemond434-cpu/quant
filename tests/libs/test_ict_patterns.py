"""ICT / SMC pattern detectors -- and the lookahead proof that makes them admissible.

WHY THIS SUITE IS SHAPED THIS WAY. ICT concepts have a poor reputation and largely a deserved one:
they are usually taught as chart annotations drawn AFTER the move, which is unfalsifiable by
construction. The objects themselves are mechanically definable, so the entire question of whether
this family may enter the funnel at all reduces to one thing -- do the detectors use the future?

So every detector is put through the desk's own future-invariance test, which mutates later bars
and asserts earlier values do not move. That is the gate almost every published ICT backtest would
fail, and it is checked here before anything else.

The second shape is NEAR-MISS testing. A detector that fires on the pattern proves little; one
that fires on the pattern AND STAYS SILENT on the case that merely resembles it is worth having.
Every positive test below has a negative twin one tick away.

NOTHING HERE CLAIMS EDGE. These tests assert that detectors detect. Whether any of it predicts
anything is the gauntlet's question, and the desk's prior is 420/420 rejections.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.features.causal_guard import check_causal
from libs.ict.patterns import (
    DEFAULT_CONFIRM,
    ICT_FAMILY,
    breaker_block,
    displacement,
    fair_value_gap,
    fvg_size,
    liquidity_sweep,
    market_structure_shift,
    order_block,
    premium_discount,
    swing_high,
    swing_low,
)

DETECTORS = {
    "fair_value_gap": fair_value_gap,
    "fvg_size": fvg_size,
    "displacement": displacement,
    "liquidity_sweep": liquidity_sweep,
    "market_structure_shift": market_structure_shift,
    "order_block": order_block,
    "breaker_block": breaker_block,
    "premium_discount": premium_discount,
    "swing_high": swing_high,
    "swing_low": swing_low,
}


def _bars(n: int = 300, seed: int = 7) -> pd.DataFrame:
    """A random walk with real intrabar structure -- enough variety that every detector fires."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1.0, n))
    spread = np.abs(rng.normal(0, 0.8, n)) + 0.1
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


# ------------------------------------------------------------------ THE GATE


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_no_detector_uses_the_future(name: str) -> None:
    """THE LOAD-BEARING TEST FOR THE WHOLE FAMILY. Mutates future bars and asserts past values are
    invariant. This is the gate almost every published ICT backtest would fail -- a level marked
    from a move that had not happened yet is not a level, it is a memory.

    If this ever goes red, the family is inadmissible until it is green again: everything
    downstream (screens, labels, any eventual sizing) inherits the leak silently."""
    res = check_causal(DETECTORS[name], _bars(), name=name, min_periods=60)
    assert res.ok, f"{name} LEAKS THE FUTURE: {res}"


def test_swing_levels_are_published_late_not_when_they_form() -> None:
    """A swing high at bar i cannot be known until `confirm` bars print to its right. Publishing
    it at i is the single most common lookahead in charted structure work -- and it is invisible
    on a chart, because the annotation is drawn where the pivot is, not where it was learned."""
    n = 60
    b = _bars(n, seed=3)
    b.loc[30, "high"] = b["high"].max() + 10.0     # an unmistakable pivot at bar 30
    sh = swing_high(b, confirm=DEFAULT_CONFIRM)
    assert sh.iloc[30] != pytest.approx(b.loc[30, "high"]), (
        "the pivot was published on the bar it formed -- that reads the future")
    assert sh.iloc[30 + DEFAULT_CONFIRM] == pytest.approx(b.loc[30, "high"])


# ------------------------------------------------------------------ fair value gap


def test_a_bullish_fvg_fires_exactly_where_the_imbalance_is() -> None:
    """low[i] > high[i-2]: a price band no trade occurred in. The one genuinely unambiguous
    object in the vocabulary."""
    b = pd.DataFrame({"open": [100, 101, 105], "high": [101, 104, 108],
                      "low": [99, 100, 102], "close": [100.5, 103, 107]})
    assert fair_value_gap(b).tolist() == [0.0, 0.0, 1.0]


def test_a_bearish_fvg_is_the_mirror() -> None:
    b = pd.DataFrame({"open": [107, 105, 101], "high": [108, 106, 100],
                      "low": [105, 102, 98], "close": [106, 103, 99]})
    assert fair_value_gap(b).tolist()[-1] == -1.0


def test_touching_bars_are_NOT_a_gap() -> None:
    """THE NEAR MISS. low[i] == high[i-2] means the band was traded, exactly. A detector using
    >= would fire on every ordinary continuation and the 'signal' would be a trend proxy."""
    b = pd.DataFrame({"open": [100, 101, 105], "high": [101, 104, 108],
                      "low": [99, 100, 101], "close": [100.5, 103, 107]})
    assert fair_value_gap(b).tolist() == [0.0, 0.0, 0.0]


def test_gap_size_is_not_pre_filtered_by_a_threshold() -> None:
    """A 2bp gap and a 200bp gap are reported alike, signed and scaled by price. Filtering on a
    threshold picked by eye is how a detector quietly becomes a fitted strategy -- the screen may
    choose a cutoff on evidence; this module may not choose one on taste."""
    b = pd.DataFrame({"open": [100.0, 101.0, 105.0], "high": [101.0, 104.0, 108.0],
                      "low": [99.0, 100.0, 102.0], "close": [100.5, 103.0, 107.0]})
    assert fvg_size(b).iloc[-1] > 0
    tiny = b.copy()
    tiny.loc[2, "low"] = 101.0001          # a 1bp gap: reported, not filtered away
    assert 0 < fvg_size(tiny).iloc[-1] < fvg_size(b).iloc[-1]


# ------------------------------------------------------------------ sweeps and structure


def test_a_sweep_is_settled_on_the_sweeping_bar_not_by_what_follows() -> None:
    """THE CIRCULARITY THIS FAMILY MUST AVOID. 'Swept liquidity and reversed' is normally scored
    from the reversal -- the very thing a strategy would predict -- so the backtest cannot fail.
    Here: pierced the level, closed back inside, decided immediately."""
    b = _bars(40, seed=11)
    # The reference is the MOST RECENT confirmed swing low, not the lowest one on the chart --
    # liquidity rests below the recent low, and an older deeper pivot has already been taken.
    # The first draft of this test pierced a deep pivot from bar 10 that a higher low had since
    # superseded, and read the (correct) silence as a detector bug.
    lvl = float(swing_low(b).iloc[25])
    b.loc[25, "low"] = lvl - 1.0                               # pierce it
    b.loc[25, "close"] = lvl + 1.0                             # and close back above
    b.loc[25, "high"] = max(b.loc[25, "high"], lvl + 1.5)
    assert liquidity_sweep(b).iloc[25] == 1.0


def test_a_close_BEYOND_the_level_is_not_a_sweep() -> None:
    """The near miss, and the one that separates a sweep from a breakout. Closing through means
    the level gave way; a sweep is precisely the case where it did not."""
    b = _bars(40, seed=11)
    lvl = float(swing_low(b).iloc[25])
    b.loc[25, ["low", "close"]] = [lvl - 2.0, lvl - 1.5]
    assert liquidity_sweep(b).iloc[25] == 0.0


def test_structure_shift_needs_a_CLOSE_through_the_level() -> None:
    """Wick-through is the sweep. If a structure break fired on wicks too, the two detectors
    would be the same detector and neither would carry information."""
    b = _bars(40, seed=5)
    lvl = float(swing_high(b).iloc[25])
    b.loc[25, ["high", "close"]] = [lvl + 2.0, lvl - 0.5]      # wick only
    assert market_structure_shift(b).iloc[25] == 0.0
    b.loc[26, ["high", "close"]] = [lvl + 3.0, lvl + 1.0]      # closes through
    assert market_structure_shift(b).iloc[26] == 1.0


# ------------------------------------------------------------------ blocks


def test_displacement_uses_the_BODY_not_the_range() -> None:
    """A long-wicked bar closing where it opened is indecision. Counting range would make a doji
    the strongest 'intent' signal on the chart."""
    b = _bars(120, seed=9)
    b.loc[100, ["open", "close"]] = [100.0, 100.0]             # doji...
    b.loc[100, ["high", "low"]] = [140.0, 60.0]                # ...with an enormous range
    assert displacement(b).iloc[100] == 0.0


def test_an_order_block_is_published_on_the_displacement_bar_not_written_backwards() -> None:
    """Stamping the mark onto the origin candle puts information at a timestamp that did not have
    it -- the commonest lookahead in charted order-block studies, and invisible on a chart."""
    b = _bars(120, seed=13)
    body = (b["close"] - b["open"]).abs().mean()
    b.loc[99, ["open", "close"]] = [100.0, 99.0]               # down candle
    b.loc[100, ["open", "close"]] = [99.0, 99.0 + 20 * body]   # big up leg
    b.loc[100, "high"] = b.loc[100, "close"] + 1
    ob = order_block(b)
    assert ob.iloc[100] == 1.0, "the block must be reported on the leg that revealed it"
    assert ob.iloc[99] == 0.0, "nothing may be written back onto the origin candle"


def test_a_breaker_records_that_a_level_FAILED() -> None:
    """A family that can only recognise its own confirmations is not falsifiable. Detecting
    failure is strictly easier than detecting success and is worth having for that reason."""
    b = _bars(200, seed=17)
    out = breaker_block(b)
    assert set(np.unique(out)) <= {-1.0, 0.0, 1.0}
    assert (out != 0).any(), "no breaker fired in 200 bars -- the detector is inert"


def test_premium_discount_excludes_the_current_bar_from_its_own_range() -> None:
    """A new extreme must not define the range it just broke, or the value pins to 0/1 exactly
    when it is most interesting."""
    b = _bars(120, seed=21)
    b.loc[100, ["high", "close"]] = [b["high"].max() + 50, b["high"].max() + 49]
    assert premium_discount(b).iloc[100] == pytest.approx(1.0)
    assert 0.0 <= premium_discount(b).min() <= premium_discount(b).max() <= 1.0


# ------------------------------------------------------------------ what is NOT claimed


def test_the_family_is_labelled_and_distinct() -> None:
    """P16 judges families JOINTLY by marginal portfolio contribution, and MC_i is undefined with
    one sleeve. Naming a second family is what makes the coexistence law computable -- it does not
    arm it, which happens from a data condition, and must not."""
    assert ICT_FAMILY == "discretionary_ict"


def test_detectors_refuse_missing_columns_loudly() -> None:
    """A detector silently returning zeros on absent input is a dark signal: it screens clean,
    contributes nothing, and nothing distinguishes it from a real negative result."""
    with pytest.raises(KeyError, match="ICT patterns need"):
        fair_value_gap(pd.DataFrame({"close": [1.0, 2.0, 3.0]}))


# ------------------------------------------------------------------ entering the funnel


def test_registration_runs_the_leakage_proof_at_the_door() -> None:
    """A detector that starts reading the future must be refused ENTRY, not discovered later by a
    screen that happened to like its results. `register_feature` runs the proof when given bars,
    so passing them is the difference between a gate and a suggestion."""
    from libs.features.registry import FeatureRegistry
    from libs.ict.patterns import register
    keys = register(FeatureRegistry(), bars=_bars(300, seed=3))
    assert len(keys) == 8
    assert all(k.startswith("ict_") for k in keys), keys


def test_every_registered_detector_declares_the_family() -> None:
    """The category IS the family label. Without it these are eight loose features and P16 has
    nothing to judge jointly -- a sleeve is only a sleeve if something can name its members."""
    from libs.ict.patterns import _definitions
    assert {d.category for d in _definitions()} == {ICT_FAMILY}


def test_min_periods_are_honest_about_warmup() -> None:
    """A detector claiming min_periods=1 while needing 50 bars of range emits garbage for its
    first 49 values, and a screen cannot tell that from signal. Each declared warmup must cover
    the longest window the detector actually reads."""
    from libs.ict.patterns import _definitions
    need = {"ict_fvg": 3, "ict_displacement": 21, "ict_premium_discount": 51}
    got = {d.name: d.min_periods for d in _definitions()}
    for k, v in need.items():
        assert got[k] >= v, f"{k} declares {got[k]}, reads {v}"
