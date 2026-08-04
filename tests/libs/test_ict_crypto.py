"""ICT in CRYPTO -- where the premise stops being an inference and becomes observable.

THE CLAIM THIS SUITE EXISTS TO PROTECT. ICT's core premise is that price seeks liquidity resting
at obvious levels. On FX and futures that is an INFERENCE -- nobody can see the stops. Crypto
perpetuals make a large share of it mechanical and partially observable: positions liquidate at
computable prices, open interest reports how much is outstanding, and funding settles on a fixed
8-hour clock that creates flow nobody chose to send. The desk already records all three.

So the tests below are mostly about keeping that distinction honest: what is a VENUE FACT (the
funding clock), what is an OBSERVED event (an OI collapse during a price run), and what is merely
a PARTITION the screen may test (session buckets). Collapsing those three is how borrowed folklore
enters as if it were measurement -- and this desk already holds the receipt for that, with
M_ATTENTION_DELAY a family kill at 13 deaths.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.features.causal_guard import check_causal
from libs.ict.crypto import (
    FUNDING_HOURS_UTC,
    _definitions,
    equal_highs,
    equal_lows,
    funding_window,
    has_oi,
    oi_flush,
    session_partition,
    sweep_into_funding,
)
from libs.ict.patterns import ICT_FAMILY

DETECTORS = {
    "funding_window": funding_window,
    "session_partition": session_partition,
    "equal_highs": equal_highs,
    "equal_lows": equal_lows,
    "oi_flush": oi_flush,
    "sweep_into_funding": sweep_into_funding,
}


def _perp(n: int = 400, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 1.0, n))
    spread = np.abs(rng.normal(0, 0.8, n)) + 0.1
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({
        "timestamp": ts, "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread, "close": close,
        "open_interest": 1e6 + np.cumsum(rng.normal(0, 2000, n)),
    })


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_no_crypto_detector_uses_the_future(name: str) -> None:
    """Same gate as the base family. A crypto-native detector gets no exemption for being novel."""
    res = check_causal(DETECTORS[name], _perp(), name=name, min_periods=60)
    assert res.ok, f"{name} LEAKS THE FUTURE: {res}"


# ------------------------------------------------------------------ venue fact vs belief


def test_the_funding_clock_is_a_venue_fact_and_wraps_midnight() -> None:
    """00/08/16 UTC settles whatever anybody believes -- that is why it is worth testing, and why
    it is not a killzone. The midnight wrap is the easy bug: a naive |h - 0| <= w misses 23:45."""
    df = _perp()
    fw = funding_window(df, minutes=30)
    flagged = {t.hour for t, f in zip(df["timestamp"], fw, strict=True) if f}
    assert set(FUNDING_HOURS_UTC) <= flagged
    assert 23 in flagged, "the window before 00:00 UTC was missed -- midnight wrap bug"
    assert 0 < fw.sum() < len(df), "a window flagging everything or nothing is not a window"


def test_sessions_are_a_partition_and_claim_nothing() -> None:
    """Crypto never closes, so there is no London open to trade around. What survives from the FX
    idea is only that participants are human and clustered -- which MAY produce a regime
    difference. This function lets the screen ask; it must not answer."""
    s = session_partition(_perp())
    assert set(np.unique(s)) <= {0.0, 1.0, 2.0}
    assert len(set(np.unique(s))) > 1, "a partition with one bucket partitions nothing"


# ------------------------------------------------------------------ the observable part


def test_an_oi_collapse_during_a_price_run_is_a_flush() -> None:
    """THE CRYPTO-SPECIFIC PAYOFF. In FX, 'price hunted stops' is unfalsifiable. Here a cascade has
    a signature in data the desk records: positions close INVOLUNTARILY, so open interest drops
    hard while price moves hard."""
    df = _perp()
    df.loc[300, "open_interest"] = df.loc[299, "open_interest"] - 200_000
    df.loc[300, "close"] = df.loc[299, "close"] * 0.95
    assert oi_flush(df).iloc[300] == -1.0


def test_RISING_oi_on_a_big_move_is_not_a_flush() -> None:
    """THE NEAR MISS, and the one that makes the detector worth having. Rising OI on a large move
    is new positioning -- a breakout. Conflating it with forced exit merges two opposite events
    and the feature becomes 'price moved a lot', which the desk already has."""
    df = _perp()
    df.loc[300, "open_interest"] = df.loc[299, "open_interest"] + 200_000
    df.loc[300, "close"] = df.loc[299, "close"] * 1.05
    assert oi_flush(df).iloc[300] == 0.0


def test_absent_open_interest_is_reportable_not_silently_zero() -> None:
    """WS-005 applied here. All-zero from 'no OI column' and all-zero from 'measured, no flush'
    are the same array and opposite facts, so the absence must be answerable separately."""
    df = _perp().drop(columns=["open_interest"])
    assert (oi_flush(df) == 0.0).all()
    assert has_oi(df) is False
    assert has_oi(_perp()) is True


def test_a_FROZEN_oi_column_counts_as_absent() -> None:
    """A venue reporting a constant tells you nothing about deleveraging. Same rule the moat miner
    applies to a degenerate series: zero dispersion is not a measurement."""
    df = _perp()
    df["open_interest"] = 1_000_000.0
    assert has_oi(df) is False


# ------------------------------------------------------------------ resting liquidity


def test_equal_highs_count_a_shelf_and_ignore_a_staircase() -> None:
    """A shelf of near-identical extremes is where invalidation stops accumulate. A steadily
    rising series has no shelf, and a detector that scored it would just be measuring trend."""
    shelf = pd.DataFrame({"high": [100.0, 100.01, 99.99, 100.0, 100.005]})
    stair = pd.DataFrame({"high": [100.0, 101.0, 102.0, 103.0, 104.0]})
    assert equal_highs(shelf).iloc[-1] >= 3
    assert equal_highs(stair).iloc[-1] == 0
    assert equal_lows(pd.DataFrame({"low": [50.0, 50.01, 49.99]})).iloc[-1] >= 1


def test_the_conjunction_is_the_crypto_only_hypothesis() -> None:
    """Neither half is novel -- sweeps are ICT's oldest idea, the funding clock is public. The
    CONJUNCTION cannot even be posed on a market without perpetuals, which is what makes it worth
    a gauntlet slot. Non-zero only where both hold."""
    df = _perp()
    s = sweep_into_funding(df)
    fw = funding_window(df)
    assert ((s != 0) <= (fw != 0)).all(), "fired outside the funding window"


# ------------------------------------------------------------------ same door as everything else


def test_crypto_detectors_join_the_same_family_and_pass_the_same_gate() -> None:
    from libs.features.registry import FeatureRegistry
    from libs.ict.crypto import register
    keys = register(FeatureRegistry(), bars=_perp())
    assert len(keys) == 6
    assert {d.category for d in _definitions()} == {ICT_FAMILY}
