"""GARCH(1,1) vol scale (ALLOC-13): recovers its own parameters, says 1.0 when it cannot know,
reads a burst as wider, and never looks past the day it stands on."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.portfolio import garch_vol as gv


def _sim(n: int, omega: float, alpha: float, beta: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n + 500)
    s2 = omega / (1 - alpha - beta)
    out = np.empty(n + 500)
    for t in range(n + 500):
        out[t] = np.sqrt(s2) * z[t]
        s2 = omega + alpha * out[t] ** 2 + beta * s2
    return out[500:]


@dataclass
class _Ev:
    name: str
    daily_r: np.ndarray


def test_recovers_simulated_parameters() -> None:
    r = _sim(4000, 0.05, 0.08, 0.90, seed=7)
    f = gv.fit_garch11(r)
    assert f.status == gv.MEASURED, f.why
    assert abs(f.alpha - 0.08) < 0.03
    assert abs(f.beta - 0.90) < 0.04
    assert abs(f.persistence - 0.98) < 0.02
    assert f.loglik is not None and np.isfinite(f.loglik)
    assert len(f.forecast_var) == gv.DEFAULT_HORIZON_DAYS
    assert f.param_se and all(v > 0 for v in f.param_se.values())


def test_constant_vol_ratio_near_one() -> None:
    r = np.random.default_rng(11).standard_normal(1500) * 0.7
    f = gv.fit_garch11(r)
    assert abs(f.ratio - 1.0) < 0.1, f.as_dict()


def test_high_recent_vol_ratio_above_one() -> None:
    r = _sim(1500, 0.05, 0.10, 0.85, seed=3)
    burst = np.random.default_rng(5).standard_normal(15) * 4.0 * r.std()
    f = gv.fit_garch11(np.concatenate([r, burst]))
    assert f.status == gv.MEASURED, f.why
    assert f.ratio_point is not None and f.ratio_point > 1.0
    assert f.ratio > 1.0                       # risk-reducing: applied as measured
    assert f.band is not None and f.band[0] < f.ratio_point < f.band[1]


def test_calm_ratio_only_applies_what_the_band_proves() -> None:
    r = _sim(1500, 0.05, 0.10, 0.85, seed=9)
    calm = np.random.default_rng(2).standard_normal(30) * 0.2 * r.std()
    f = gv.fit_garch11(np.concatenate([r, calm]))
    assert f.status == gv.MEASURED, f.why
    assert f.ratio_point < 1.0
    assert f.ratio == min(1.0, f.band[1])
    assert f.ratio >= f.ratio_point


def test_short_series_is_unmeasured_at_one() -> None:
    r = np.random.default_rng(1).standard_normal(gv.MIN_OBS - 1)
    f = gv.fit_garch11(r)
    assert f.status == gv.UNMEASURED and f.ratio == 1.0
    assert "MIN_OBS" in f.why


def test_nan_days_dropped_not_zeroed() -> None:
    r = _sim(1200, 0.05, 0.08, 0.90, seed=4)
    holed = r.copy()
    holed[::3] = np.nan
    a = gv.fit_garch11(holed)
    b = gv.fit_garch11(holed[np.isfinite(holed)])
    assert a.n == b.n == int(np.isfinite(holed).sum())
    assert a.ratio == b.ratio


def test_no_lookahead() -> None:
    r = _sim(1200, 0.05, 0.10, 0.85, seed=21)
    t = 900
    base = gv.forecast_at(r, t)
    poisoned = r.copy()
    poisoned[t + 1:] = poisoned[t + 1:] * 50.0 + 3.0
    again = gv.forecast_at(poisoned, t)
    assert base.status == gv.MEASURED
    assert base.ratio == again.ratio
    assert base.forecast_var == again.forecast_var
    assert base.n == t + 1


def test_vol_scale_by_sleeve_and_mean_untouched() -> None:
    ev = [_Ev("long", _sim(1500, 0.05, 0.10, 0.85, seed=8)),
          _Ev("short", np.random.default_rng(0).standard_normal(50))]
    scales, diag = gv.vol_scale_by_sleeve(ev, horizon_days=3)
    assert set(scales) == {"long", "short"}
    assert scales["short"] == 1.0
    assert diag["by_sleeve"]["short"]["status"] == gv.UNMEASURED
    assert diag["roles"] == ["VOLATILITY_SCALE", "UNCERTAINTY_WIDTH"]
    assert gv.scales_from(diag) == scales
    x = ev[0].daily_r
    y = gv.apply_vol_scale(x, 1.7)
    assert abs(np.mean(y) - np.mean(x)) < 1e-12
    assert abs(np.std(y) / np.std(x) - 1.7) < 1e-9
