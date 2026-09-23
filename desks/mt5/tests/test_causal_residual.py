"""The residual must not know the future, and the fast path must equal the readable one.

`family_cross_asset_residual` fitted its hedge ratios with one `lstsq` over the whole sample and
then traded the residual from the first bar. That is lookahead on every bar of every fold, and
`funnel_census` records the cost: 348 failures, zero certificates, on the desk's only
non-directional mechanism. The property is pinned here because the fix is arithmetic that reads
correct either way -- only a test that PERTURBS THE FUTURE can tell them apart.
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

from mt5desk.causal_residual import (  # noqa: E402
    causal_residual,
    naive_rolling_residual,
    rolling_betas,
)
from mt5desk.families_orthogonal import family_cross_asset_residual  # noqa: E402


def _panel(n: int = 900, k: int = 3, seed: int = 11):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, k))
    y = 0.4 * X[:, 0] - 0.9 * X[:, 1] + 0.05 + rng.normal(scale=0.4, size=n)
    return y, X


def test_fast_path_equals_the_naive_loop():
    """The cumulative-normal-equations solve must compute the loop's exact quantity."""
    y, X = _panel()
    fast = causal_residual(y, X, 120)
    slow = naive_rolling_residual(y, X, 120)
    assert np.array_equal(np.isfinite(fast), np.isfinite(slow))
    ok = np.isfinite(fast)
    assert ok.sum() > 700
    assert np.max(np.abs(fast[ok] - slow[ok])) < 1e-8


def test_the_future_cannot_change_the_past():
    """This is the whole defect. eps[t] must be identical whatever happens after t."""
    y, X = _panel()
    cut = 600
    base = causal_residual(y, X, 120)

    y2, X2 = y.copy(), X.copy()
    rng = np.random.default_rng(99)
    # Replace everything after `cut` with a wildly different regime: a 10x scale change and a
    # sign-flipped relationship. A full-sample beta would repaint every earlier residual.
    X2[cut:] = rng.normal(scale=10.0, size=X2[cut:].shape)
    y2[cut:] = -5.0 * X2[cut:, 0] + 200.0
    after = causal_residual(y2, X2, 120)

    ok = np.isfinite(base[:cut])
    assert ok.sum() > 400
    assert np.array_equal(base[:cut][ok], after[:cut][ok]), "residual repainted by future bars"


def test_the_old_full_sample_fit_would_have_failed_that_test():
    """Guards the test itself: prove the perturbation is strong enough to catch the old code."""
    y, X = _panel()
    cut = 600
    rng = np.random.default_rng(99)
    y2, X2 = y.copy(), X.copy()
    X2[cut:] = rng.normal(scale=10.0, size=X2[cut:].shape)
    y2[cut:] = -5.0 * X2[cut:, 0] + 200.0

    def full_sample(yv, xv):
        beta, *_ = np.linalg.lstsq(xv, yv, rcond=None)
        return yv - xv @ beta

    assert not np.allclose(full_sample(y, X)[:cut], full_sample(y2, X2)[:cut])


def test_betas_recover_a_known_relationship():
    rng = np.random.default_rng(5)
    n = 800
    X = rng.normal(size=(n, 2))
    y = 0.75 * X[:, 0] - 0.25 * X[:, 1] + 1.5 + rng.normal(scale=0.01, size=n)
    beta = rolling_betas(y, X, 200)
    last = beta[-1]
    assert last[0] == pytest.approx(1.5, abs=0.02), "intercept not fitted"
    assert last[1] == pytest.approx(0.75, abs=0.02)
    assert last[2] == pytest.approx(-0.25, abs=0.02)


def test_the_regression_carries_a_constant():
    """Drift the drivers do not explain belongs in the intercept, not in the residual."""
    rng = np.random.default_rng(3)
    n = 700
    X = rng.normal(size=(n, 2))
    y = 0.5 * X[:, 0] + 40.0 + rng.normal(scale=0.05, size=n)
    eps = causal_residual(y, X, 200)
    ok = np.isfinite(eps)
    assert abs(float(np.mean(eps[ok]))) < 0.05, "constant offset leaked into the residual"


def test_warmup_rows_are_nan_not_guessed():
    y, X = _panel(n=400, k=2)
    eps = causal_residual(y, X, 150)
    assert np.isnan(eps[:150]).all()
    assert np.isfinite(eps[150:]).any()


def test_a_window_with_too_few_observations_refuses():
    y, X = _panel(n=300, k=2)
    y[100:280] = np.nan
    eps = causal_residual(y, X, 60)
    # Windows lying entirely inside the hole cannot be fitted and must not produce a number.
    assert np.isnan(eps[170:270]).all()


def test_collinear_drivers_do_not_raise():
    """Two identical driver columns is a degenerate window, not a reason to drop a sweep."""
    rng = np.random.default_rng(1)
    n = 500
    x = rng.normal(size=n)
    X = np.column_stack([x, x])
    y = 2.0 * x + rng.normal(scale=0.1, size=n)
    eps = causal_residual(y, X, 150)
    assert np.isfinite(eps[200:]).any()


# ------------------------------------------------------------------------------------------
# The same property, one level up: the executable family itself.
# ------------------------------------------------------------------------------------------

def _frame(vals: np.ndarray, idx: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"open": vals, "high": vals * 1.001, "low": vals * 0.999,
                         "close": vals}, index=idx)


def _bars(n: int = 3000, seed: int = 4):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    f1 = np.exp(np.cumsum(rng.normal(scale=0.001, size=n))) * 100
    f2 = np.exp(np.cumsum(rng.normal(scale=0.001, size=n))) * 50
    tgt = np.exp(np.cumsum(rng.normal(scale=0.0012, size=n))) * 1500
    return idx, _frame(tgt, idx), [_frame(f1, idx), _frame(f2, idx)]


def test_family_signals_do_not_move_when_the_future_changes():
    idx, df, factors = _bars()
    cut = 2200
    kw = dict(lookback=240, beta_win=240, entry_z=1.5, ttl_bars=8)
    before = family_cross_asset_residual(df, factors=factors, **kw)

    rng = np.random.default_rng(77)
    df2 = df.copy()
    tail = df2.index[cut:]
    shocked = df2.loc[tail, "close"].to_numpy() * np.exp(
        np.cumsum(rng.normal(scale=0.05, size=len(tail))))
    for col in ("open", "high", "low", "close"):
        df2.loc[tail, col] = shocked
    after = family_cross_asset_residual(df2, factors=factors, **kw)

    early_before = [(s.time, s.side) for s in before if s.time < idx[cut]]
    early_after = [(s.time, s.side) for s in after if s.time < idx[cut]]
    assert early_before, "no signals before the cut: the test proves nothing"
    assert early_before == early_after, "family repainted past signals from future bars"


def test_side_mode_is_a_hypothesis_and_flips_the_side():
    _idx, df, factors = _bars()
    kw = dict(lookback=240, beta_win=240, entry_z=1.5, ttl_bars=8)
    rev = family_cross_asset_residual(df, factors=factors, side_mode="revert", **kw)
    con = family_cross_asset_residual(df, factors=factors, side_mode="continue", **kw)
    assert rev and len(rev) == len(con)
    assert [s.time for s in rev] == [s.time for s in con]
    assert all(a.side == -b.side for a, b in zip(rev, con))


def test_unknown_side_mode_refuses_rather_than_defaulting():
    _idx, df, factors = _bars()
    assert family_cross_asset_residual(df, factors=factors, side_mode="whatever") == []


def test_active_hours_restricts_entries_without_a_second_family():
    _idx, df, factors = _bars()
    kw = dict(lookback=240, beta_win=240, entry_z=1.5, ttl_bars=8)
    everywhere = family_cross_asset_residual(df, factors=factors, **kw)
    windowed = family_cross_asset_residual(df, factors=factors, active_hours=(8, 9, 10), **kw)
    assert everywhere
    assert windowed
    assert len(windowed) < len(everywhere)
    assert {s.time.hour for s in windowed} <= {8, 9, 10}


def test_family_refuses_without_room_for_both_windows():
    idx = pd.date_range("2020-01-01", periods=500, freq="h", tz="UTC")
    vals = np.linspace(100, 110, 500)
    df = _frame(vals, idx)
    assert family_cross_asset_residual(df, factors=[_frame(vals * 2, idx)],
                                       lookback=240, beta_win=240) == []
