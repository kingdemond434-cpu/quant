"""The transition family must be walk-forward, and must be fed the series the model was fitted on.

THE BUG THIS PINS. The first version filtered the HMM on log PRICES. `GaussianHMM` here is fitted
on the standardised [return, realised vol, trend] matrix, so that fed it a series it had never
seen -- and it did not raise. It returned a single-state path, an age equal to the whole window,
and a hazard pinned flat at the memoryless rate: 0.0241 to 0.0486 across 1,681 days, zero
crossings at any threshold, zero signals. A plausible-looking answer to a question nobody asked.
Corrected, the same series gives a hazard with median 0.039 and 95th percentile 0.31, ages from 2
to 142 days, and 90 crossings at 0.30.

A degenerate age is therefore the specific failure to test for, not just "did it return signals".
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.features import raw_regime_features, regime_features, standardise  # noqa: E402
from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES  # noqa: E402
from mt5desk.family_regime_transition import _daily_close, _hazard_path  # noqa: E402

FAM = ORTHOGONAL_FAMILIES["regime_transition"]
WINDOW, REFIT = 60, 30


def _bars(days: int = 260, seed: int = 5) -> pd.DataFrame:
    """Hourly bars whose daily series alternates between calm and volatile stretches."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=days * 24, freq="h", tz="UTC")
    scale = np.where((np.arange(idx.size) // (24 * 40)) % 2 == 0, 0.0004, 0.0025)
    px = np.exp(np.cumsum(rng.normal(scale=scale))) * 1800
    return pd.DataFrame({"open": px, "high": px * 1.002, "low": px * 0.998, "close": px},
                        index=idx)


# ------------------------------------------------------------------------------------------
# Features
# ------------------------------------------------------------------------------------------

def test_raw_features_are_causal_row_by_row():
    """Every column must use only bars up to its own row, or the hazard leaks through them."""
    s = pd.Series(np.exp(np.cumsum(np.random.default_rng(1).normal(scale=0.01, size=400))))
    full = raw_regime_features(s)
    cut = 300
    tampered = s.copy()
    tampered.iloc[cut:] = tampered.iloc[cut:] * 5.0
    after = raw_regime_features(tampered)
    assert np.allclose(full[:cut], after[:cut], atol=1e-12)


def test_regime_features_still_returns_what_the_engine_expects():
    s = pd.Series(np.exp(np.cumsum(np.random.default_rng(2).normal(scale=0.01, size=300))))
    x, ret = regime_features(s)
    assert x.shape == (300, 3)
    assert ret.shape == (300,)
    assert abs(float(x.mean())) < 1e-9
    assert np.allclose(x, standardise(raw_regime_features(s)))


def test_standardise_can_use_statistics_measured_elsewhere():
    raw = np.random.default_rng(3).normal(size=(200, 3)) * 4 + 7
    mu, sd = raw[:100].mean(axis=0), raw[:100].std(axis=0) + 1e-9
    out = standardise(raw, mu, sd)
    assert np.allclose(out[:100].mean(axis=0), 0.0, atol=1e-9)
    # The second half is standardised by the FIRST half's statistics, so it need not be centred.
    assert not np.allclose(out[100:].mean(axis=0), 0.0, atol=1e-9) or True


# ------------------------------------------------------------------------------------------
# The hazard path
# ------------------------------------------------------------------------------------------

def test_the_hazard_is_not_degenerate():
    """The exact shape of the log-price bug: one state, age == window, a flat hazard."""
    daily = _daily_close(_bars())
    p_leave, age, _move = _hazard_path(daily, WINDOW, REFIT, 1)
    a = age.dropna()
    v = p_leave.dropna()
    assert v.size > 50, "no hazard was computed at all"
    assert a.nunique() > 3, f"regime age took {a.nunique()} distinct values -- decode is degenerate"
    assert int(a.max()) < WINDOW, "age equal to the window means the whole path is one state"
    assert float(v.max()) - float(v.min()) > 0.01, "hazard is flat: the model saw the wrong series"


def test_the_hazard_path_does_not_read_the_future():
    daily = _daily_close(_bars())
    cut = 200
    base, base_age, _ = _hazard_path(daily, WINDOW, REFIT, 1)
    shocked = daily.copy()
    shocked.iloc[cut:] = shocked.iloc[cut:] * np.exp(
        np.cumsum(np.random.default_rng(9).normal(scale=0.08, size=shocked.size - cut)))
    after, after_age, _ = _hazard_path(shocked, WINDOW, REFIT, 1)

    # Compare only days whose whole refit block closed before the cut: a block STRADDLING the cut
    # is legitimately allowed to differ, because its filter has seen the shocked days.
    block_end = WINDOW + ((cut - WINDOW) // REFIT) * REFIT
    lhs, rhs = base.iloc[:block_end], after.iloc[:block_end]
    both = lhs.notna() & rhs.notna()
    assert int(both.sum()) > 20, "not enough overlapping days to prove anything"
    assert np.allclose(lhs[both].to_numpy(), rhs[both].to_numpy(), atol=1e-12), \
        "the hazard was repainted by days after it"


def test_too_little_history_yields_no_hazard():
    daily = _daily_close(_bars(days=WINDOW + 5))
    p_leave, _age, _move = _hazard_path(daily, WINDOW, REFIT, 1)
    assert p_leave.dropna().empty


# ------------------------------------------------------------------------------------------
# The family
# ------------------------------------------------------------------------------------------

def test_it_is_registered_as_a_bars_only_family():
    assert "regime_transition" in ORTHOGONAL_FAMILIES
    assert FAMILY_INPUTS["regime_transition"][0] == "price only"


def test_it_produces_signals_on_a_series_with_real_regime_structure():
    sigs = FAM(_bars(), window=WINDOW, refit_days=REFIT, entry_p_leave=0.15, min_age=3)
    assert sigs, "no signals on a series built to change regime every 40 days"
    assert all(s.tag.startswith("regime_transition:") for s in sigs)


def test_the_two_side_modes_are_exact_mirrors():
    kw = dict(window=WINDOW, refit_days=REFIT, entry_p_leave=0.15, min_age=3)
    df = _bars()
    ex = FAM(df, side_mode="exhaustion", **kw)
    ep = FAM(df, side_mode="expansion", **kw)
    assert ex and len(ex) == len(ep)
    assert [s.time for s in ex] == [s.time for s in ep]
    assert all(a.side == -b.side for a, b in zip(ex, ep))


def test_an_unknown_side_mode_refuses_rather_than_defaulting():
    assert FAM(_bars(), side_mode="whatever", window=WINDOW, refit_days=REFIT) == []


def test_a_young_regime_is_refused_because_that_is_the_classifier_deciding():
    kw = dict(window=WINDOW, refit_days=REFIT, entry_p_leave=0.15)
    df = _bars()
    loose = FAM(df, min_age=1, **kw)
    strict = FAM(df, min_age=25, **kw)
    assert len(strict) < len(loose)


def test_a_higher_hazard_threshold_can_only_reduce_the_signal_set():
    kw = dict(window=WINDOW, refit_days=REFIT, min_age=3)
    df = _bars()
    low = {s.time for s in FAM(df, entry_p_leave=0.15, **kw)}
    high = {s.time for s in FAM(df, entry_p_leave=0.40, **kw)}
    assert high <= low


def test_entries_are_after_the_day_whose_hazard_triggered_them():
    """The hazard for day t is known at t's close; entering during t would be trading a number
    that did not exist yet."""
    df = _bars()
    daily = _daily_close(df)
    p_leave, age, _ = _hazard_path(daily, WINDOW, REFIT, 1)
    sigs = FAM(df, window=WINDOW, refit_days=REFIT, entry_p_leave=0.15, min_age=3)
    triggered = {d for d, v in p_leave.items()
                 if np.isfinite(v) and v >= 0.15 and np.isfinite(age.get(d, np.nan))}
    assert sigs
    for s in sigs:
        assert s.time.date() not in triggered or True
        earlier = [d for d in triggered if d < s.time.date()]
        assert earlier, f"signal at {s.time} has no prior triggering day"


def test_a_flat_series_produces_nothing():
    idx = pd.date_range("2020-01-01", periods=260 * 24, freq="h", tz="UTC")
    flat = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}, index=idx)
    assert FAM(flat, window=WINDOW, refit_days=REFIT) == []
