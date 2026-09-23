"""The detector's three promises, each one an executable invariant.

  SCALE-FREE   multiply every price by 3, or add 500 to all of them, and the
               strength must not move. This is what lets one detector serve
               gold at 1,800 and gold at 4,500, a quiet Tuesday and an FOMC
               afternoon -- and it is the whole reason nothing here is
               expressed in points.

  SYMMETRIC    mirror the series and strength is identical while direction
               flips. A detector that works better on rallies than on breaks
               is the most expensive possible bug on an instrument that falls
               faster than it rises, and it is invisible in aggregate returns.

  CAUSAL       corrupt every bar after i and the reads at or before i must be
               byte-identical. Same test the families get, for the same reason.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.trendday import efficiency_ratio, read                 # noqa: E402


def frame(close, wick=0.4):
    close = np.asarray(close, float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) + wick,
         "low": np.minimum(open_, close) - wick, "close": close},
        index=pd.date_range("2024-01-01", periods=len(close), freq="1h"))


def walk(n=800, seed=3, drift=0.0):
    rng = np.random.default_rng(seed)
    return 2000.0 + np.cumsum(rng.normal(drift, 1.2, n))


def ramp(n=400, slope=1.0, noise=0.15, seed=5):
    rng = np.random.default_rng(seed)
    return 2000.0 + slope * np.arange(n) + rng.normal(0, noise, n)


# --------------------------------------------------------------- scale-free

def test_multiplying_every_price_changes_nothing():
    df = frame(walk())
    a = read(df)
    b = read(df * 3.0)
    ok = np.isfinite(a.strength) & np.isfinite(b.strength)
    assert np.allclose(a.strength[ok], b.strength[ok], atol=1e-9)
    assert (a.direction == b.direction).all()


def test_adding_a_constant_changes_nothing():
    df = frame(walk())
    a, b = read(df), read(df + 500.0)
    ok = np.isfinite(a.strength) & np.isfinite(b.strength)
    assert np.allclose(a.strength[ok], b.strength[ok], atol=1e-9)


def test_a_quiet_trend_and_a_violent_one_both_register():
    """The point of ratios: small trend days must not be thrown away.

    Same shape, 20x the amplitude and 20x the noise. If the detector were
    calibrated in points, only one of these would be a trend.
    """
    quiet = read(frame(ramp(slope=0.05, noise=0.02), wick=0.02))
    loud = read(frame(ramp(slope=1.0, noise=0.4), wick=0.4))
    assert quiet.strength[-1] > 0.6 and loud.strength[-1] > 0.6
    assert abs(quiet.strength[-1] - loud.strength[-1]) < 0.15


# ---------------------------------------------------------------- symmetric

def test_mirroring_flips_direction_and_preserves_strength():
    c = walk(drift=0.05)
    up = read(frame(c))
    dn = read(frame(2.0 * c[0] - c))          # reflect about the first price
    ok = np.isfinite(up.strength) & np.isfinite(dn.strength)
    assert np.allclose(up.strength[ok], dn.strength[ok], atol=1e-9), \
        "strength is not mirror-invariant: the detector has a side"
    m = up.direction != 0
    assert (dn.direction[m] == -up.direction[m]).all()


def test_a_downtrend_scores_as_hard_as_an_uptrend():
    # A TRUE mirror: negating the slope alone leaves the noise un-negated, so
    # the two series are not reflections and differ in the fourth decimal for
    # reasons that have nothing to do with the detector having a side.
    c = ramp(slope=1.0)
    u = read(frame(c))
    d = read(frame(2.0 * c[0] - c))
    assert u.strength[-1] == pytest.approx(d.strength[-1], abs=1e-9)
    assert u.direction[-1] == 1 and d.direction[-1] == -1


# ------------------------------------------------------------------- causal

def test_the_future_cannot_change_the_past():
    df = frame(walk())
    split = 500
    dirty = df.copy()
    rng = np.random.default_rng(99)
    tail = df["close"].iloc[split - 1] + np.cumsum(
        rng.normal(0, 5.0, len(df) - split))
    for col, v in (("close", tail), ("open", tail), ("high", tail + 2),
                   ("low", tail - 2)):
        dirty.iloc[split:, dirty.columns.get_loc(col)] = v
    a, b = read(df), read(dirty)
    for name in ("strength", "direction", "er", "displacement"):
        x = getattr(a, name)[:split]
        y = getattr(b, name)[:split]
        ok = np.isfinite(x) & np.isfinite(y)
        assert np.allclose(x[ok], y[ok], atol=1e-12), f"{name} reads the future"


# ------------------------------------------------------- does it discriminate

def test_chop_scores_below_trend():
    chop = read(frame(2000 + 5 * np.sin(np.arange(600) / 2.0)))
    trend = read(frame(ramp(slope=1.0)))
    assert chop.strength[-1] < 0.4 < trend.strength[-1]
    assert chop.direction[-1] == 0


def test_efficiency_ratio_is_one_on_a_straight_line_and_zero_on_a_round_trip():
    line = efficiency_ratio(np.arange(100, dtype=float), 10)
    assert line[-1] == pytest.approx(1.0)
    saw = np.concatenate([np.arange(6.0), np.arange(4.0, -1.0, -1)])
    assert efficiency_ratio(np.tile(saw, 12), 10)[-1] < 0.35


# ---------------------------------------------------------------- the dying

def test_a_reversal_is_seen_even_though_it_is_itself_a_clean_trend():
    """The failure mode the first implementation had, pinned.

    A long trend rolling into a short trend keeps `strength` high the whole way
    -- both halves are clean. Comparing to the CURRENT direction therefore sees
    nothing wrong at the one moment a runner must be banked. Death is measured
    against the direction that was in force.
    """
    c = np.concatenate([ramp(200, 1.0), 2200 - 1.5 * np.arange(80)])
    r = read(frame(c))
    assert r.strength[250] > 0.5, "the down leg should itself score as a trend"
    assert r.direction[250] == -1
    assert r.dying[200:250].any(), "the reversal was invisible"


def test_a_trend_that_rolls_over_is_called_dead():
    c = np.concatenate([ramp(200, 1.0), 2200 - 1.0 * np.arange(60)])
    r = read(frame(c))
    assert not r.dying[190], "called dead while still trending"
    assert r.dying[200:245].any(), "never noticed the trend end"


def test_dying_is_relative_so_a_violent_regime_may_decay_violently():
    """Same shape, 20x scale: the death call must land in the same place."""
    shape = np.concatenate([np.arange(200.0), 200 - np.arange(60.0)])
    small = read(frame(2000 + 0.05 * shape, wick=0.02))
    big = read(frame(2000 + 1.0 * shape, wick=0.4))
    assert (small.dying[200:260].any()) == (big.dying[200:260].any())
    assert np.array_equal(small.dying[150:260], big.dying[150:260])


def test_a_flat_market_is_not_dying_because_it_was_never_alive():
    r = read(frame(2000 + np.zeros(400)))
    assert not r.dying.any()
