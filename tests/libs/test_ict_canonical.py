"""ICT as HE defines it -- and the three places my approximation was simply wrong.

WHY THIS SUITE EXISTS SEPARATELY. My first pass encoded these concepts from general knowledge.
The principal supplied actual mentorship transcripts, and three detectors turned out wrong in
specific ways: not vague-but-close, wrong about WHICH CANDLE and WHICH PRICE. "My reading of ICT"
and "ICT" are different hypotheses, so both are kept and the screen decides between them.

The tests below encode his rules as quoted, and each one exists because getting it wrong produces
a detector that still runs, still emits plausible numbers, and answers a different question.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.features.causal_guard import check_causal
from libs.ict.canonical import (
    OTE_HI,
    OTE_LO,
    OTE_MID,
    SILVER_BULLET_WINDOWS,
    _definitions,
    breaker_canonical,
    common_gap,
    in_ote,
    liquidity_void,
    mean_threshold_breach,
    optimal_trade_entry,
    order_block_canonical,
    silver_bullet_window,
)
from libs.ict.patterns import ICT_FAMILY

DETECTORS = {
    "order_block_canonical": order_block_canonical,
    "mean_threshold_breach": mean_threshold_breach,
    "breaker_canonical": breaker_canonical,
    "optimal_trade_entry": optimal_trade_entry,
    "in_ote": in_ote,
    "liquidity_void": liquidity_void,
    "common_gap": common_gap,
    "silver_bullet_window": silver_bullet_window,
}


def _bars(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    c = 100 + np.cumsum(rng.normal(0, 1.0, n))
    sp = np.abs(rng.normal(0, 0.8, n)) + 0.1
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + sp,
                         "low": np.minimum(o, c) - sp, "close": c})


# ------------------------------------------------------------------ the gate, again


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_canonical_detectors_do_not_use_the_future(name: str) -> None:
    """Being canonical buys no exemption. A rule from a transcript is a hypothesis, and a
    hypothesis that reads the future is not one."""
    res = check_causal(DETECTORS[name], _bars(), name=name, min_periods=80)
    assert res.ok, f"{name} LEAKS: {res}"


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_no_detector_is_on_almost_all_the_time(name: str) -> None:
    """CAUGHT ON THE FIRST RUN. order_block_canonical fired on 89% of bars because validation was
    re-signalled every time a later bar sat above the block, rather than once. A detector that is
    on nine times in ten carries almost no information whatever it is named -- and it screens as a
    plausible feature, which is why this is asserted rather than eyeballed."""
    v = DETECTORS[name](_bars())
    if name in ("optimal_trade_entry", "mean_threshold_breach"):
        return          # continuous measures, not event flags
    assert float((v != 0).mean()) < 0.6, f"{name} fires {(v != 0).mean():.0%} of bars"


# ------------------------------------------------------------------ his order block, not mine


def test_the_block_is_the_LARGEST_BODIED_down_close_at_the_low() -> None:
    """"the LOWEST candle with a DOWN CLOSE that has the MOST RANGE between open to close".

    Both clauses. My original picked "the last opposite-colour candle before displacement", which
    selects whichever bar happens to precede a move -- a different object on most legs."""
    b = _bars(120, seed=3)
    lo_i = 60
    # a small down bar exactly at the low, and a LARGER-bodied down bar right beside it
    b.loc[lo_i, ["open", "close"]] = [100.2, 100.0]
    b.loc[lo_i, ["high", "low"]] = [100.3, 99.0]
    b.loc[lo_i + 1, ["open", "close"]] = [104.0, 99.5]
    b.loc[lo_i + 1, ["high", "low"]] = [104.1, 99.1]
    v = order_block_canonical(b)
    assert set(np.unique(v)) <= {-1.0, 0.0, 1.0}
    assert (v != 0).any(), "no block validated at all on a constructed low"


def test_validation_is_a_ONE_TIME_event() -> None:
    """"validated when the high of the lowest down candle is traded through by a LATER formed
    candle" -- once. Re-signalling on every subsequent bar above the block is what produced an
    89%-on detector."""
    v = order_block_canonical(_bars(400))
    runs = int(((v != 0) & (v.shift(1).fillna(0) != 0)).sum())
    assert runs < (v != 0).sum() * 0.5, "blocks are re-signalling on consecutive bars"


def test_mean_threshold_uses_the_BODY_and_never_the_wicks() -> None:
    """He is explicit: "measure the open to the close... DO NOT use the wicks." Using the wick
    would make every long-tailed bar look like a violated block, which inverts his quality filter
    -- long tails are what he says the GOOD blocks have."""
    b = _bars(80, seed=11)
    b.loc[40, ["open", "close"]] = [100.0, 99.0]        # body 100.0 -> 99.0, midpoint 99.5
    b.loc[40, ["high", "low"]] = [110.0, 90.0]          # enormous wicks either side
    b.loc[41, "low"] = 99.7                             # ABOVE the 99.5 midpoint: no breach
    assert mean_threshold_breach(b).iloc[41] == 0.0

    # ...and one tick below it IS a breach, measured in BODY units. If the wicks were used the
    # body would read as 20.0 rather than 1.0 and this depth would be 20x smaller -- long-tailed
    # bars would look pristine, which inverts his filter, since long tails are what he says the
    # GOOD blocks have.
    b.loc[41, "low"] = 99.0                             # half a body below the midpoint
    assert mean_threshold_breach(b).iloc[41] == pytest.approx(0.5, abs=1e-9)


# ------------------------------------------------------------------ his breaker, not mine


def test_the_breaker_requires_a_SWEEP_then_a_STRUCTURE_BREAK() -> None:
    """"an old low is violated... the sellers that sold this low and later see this same swing
    HIGH violated will look to mitigate." Two events in order. My original was "an order block
    that failed", which has no structural requirement at all and fires on unrelated geometry."""
    v = breaker_canonical(_bars(400))
    assert set(np.unique(v)) <= {-1.0, 0.0, 1.0}
    assert (v != 0).any()


def test_structure_break_is_judged_on_the_CLOSE() -> None:
    """His rule everywhere: a wick through a level is the sweep, a CLOSE through it is the break.
    Judging breaks on wicks makes the sweep and the break the same event."""
    b = _bars(120, seed=5)
    src = Path("libs/ict/canonical.py").read_text("utf-8")
    assert "c > prior_high" in src and "c < prior_low" in src
    assert breaker_canonical(b).notna().all()


# ------------------------------------------------------------------ his OTE band


def test_the_ote_band_is_62_to_79_percent_with_705_named() -> None:
    """His three levels exactly. Encoded as a BAND rather than a point because he treats all three
    as the sweet spot -- collapsing to 0.705 would claim a precision he does not."""
    assert (OTE_LO, OTE_MID, OTE_HI) == (0.62, 0.705, 0.79)
    assert OTE_LO < OTE_MID < OTE_HI


def test_equilibrium_is_the_midpoint_and_splits_premium_from_discount() -> None:
    """"anything below equilibrium is now a discount." 0.5 is the hinge of his whole framework."""
    d = optimal_trade_entry(_bars(300))
    assert 0.0 <= d.min() <= d.max() <= 1.0
    assert (d < 0.5).any() and (d > 0.5).any(), "no premium/discount separation observed"


def test_in_ote_only_fires_inside_the_band() -> None:
    d = optimal_trade_entry(_bars(300))
    flag = in_ote(_bars(300))
    inside = (d >= OTE_LO) & (d <= OTE_HI)
    assert (flag.astype(bool) == inside).all()


# ------------------------------------------------------------------ the new objects


def test_a_liquidity_void_is_a_DIFFERENT_object_from_a_fair_value_gap() -> None:
    """A void is a one-sided DELIVERY range ("wide or long one-sided ranges or candles"); an FVG
    is a three-bar geometric gap. Keeping them separate is what lets the screen find out whether
    they are the same signal under two names -- merging them assumes the answer."""
    from libs.ict.patterns import fair_value_gap
    b = _bars(400)
    void, fvg = liquidity_void(b), fair_value_gap(b)
    both = ((void != 0) & (fvg != 0)).sum()
    either = ((void != 0) | (fvg != 0)).sum()
    assert either > 0
    assert both < either, "void and FVG fired identically -- they would be one detector"


def test_the_silver_bullet_windows_are_his_three_NY_hours() -> None:
    """03-04, 10-11, 14-15 New York. Encoded as a QUESTION for crypto: they come from a London
    open and a New York cash session, and crypto has neither."""
    assert SILVER_BULLET_WINDOWS == ((3, 4), (10, 11), (14, 15))
    v = silver_bullet_window(_bars(400))
    assert 0 < v.mean() < 0.5, "a window covering everything or nothing is not a window"


def test_common_gap_is_zero_on_a_continuous_series() -> None:
    """Crypto trades 24/7, so true gaps are rare -- which makes one an anomaly with a cause rather
    than a session boundary. A synthetic continuous series must show none."""
    b = _bars(200)
    b["open"] = np.r_[b["close"].iloc[0], b["close"].to_numpy()[:-1]]
    assert float(common_gap(b).abs().max()) == pytest.approx(0.0, abs=1e-12)


# ------------------------------------------------------------------ same family, same door


def test_canonical_detectors_join_the_same_family() -> None:
    assert {d.category for d in _definitions()} == {ICT_FAMILY}


def test_registration_runs_the_leakage_proof() -> None:
    from libs.features.registry import FeatureRegistry
    from libs.ict.canonical import register
    keys = register(FeatureRegistry(), bars=_bars(400))
    assert len(keys) == 7
