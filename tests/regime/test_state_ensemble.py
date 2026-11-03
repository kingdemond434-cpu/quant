"""The state-engine ensemble: point-in-time by construction, scored on identical days, and honest
about the engines a host cannot run.

Pinned here:
  * NO LOOKAHEAD. The forecast, the fused weights and the day's label at t are bit-identical
    whether or not the bars after t exist -- every engine, the fusion and the labels.
  * On a series whose volatility genuinely clusters, the fused forecast beats the plain base rate
    on walk-forward log score (the only reason the module exists).
  * Calibration compares two forecasters on the SAME days or not at all.
  * Without `arch`, GARCH is reported unavailable -- never imitated by a hand-rolled recursion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.regime import ensemble as E

NO_GARCH = tuple(e for e in E.ENGINES if e != "garch")


def _closes(days: int = 820, seed: int = 5) -> pd.Series:
    rng = np.random.default_rng(seed)
    # Two volatility regimes with persistent, random-length spells: real clustering to forecast.
    vol = np.empty(days)
    t, hi = 0, False
    while t < days:
        n = int(rng.integers(15, 60))
        vol[t:t + n] = 0.02 if hi else 0.006
        hi = not hi
        t += n
    r = rng.normal(scale=vol)
    idx = pd.bdate_range("2020-01-01", periods=days).strftime("%Y-%m-%d")
    return pd.Series(100.0 * np.exp(np.cumsum(r)), index=idx)


def test_gauss_tiers_is_a_distribution() -> None:
    p = E.gauss_tiers(np.array([0.005, 0.01, 0.05]), np.full(3, 0.004), np.full(3, 0.009))
    assert p.shape == (3, 3)
    assert np.allclose(p.sum(axis=1), 1.0)
    assert (p >= 0).all()
    assert p[2, 2] > p[0, 2]                    # a wider sd puts more mass in the high tier


def test_tier_outcomes_use_only_the_prior_day_thresholds() -> None:
    r = np.random.default_rng(1).normal(size=400)
    y, q1, _q2 = E.tier_outcomes(r)
    assert np.isnan(y[: E.RANK_WIN]).all()
    t = 300
    assert y[t] == (0.0 if abs(r[t]) < q1[t - 1] else y[t])
    r2 = r.copy()
    r2[t + 1:] = 99.0                           # the future cannot move y[t]
    assert E.tier_outcomes(r2)[0][t] == y[t]


@pytest.mark.parametrize("cut", [610, 700])
def test_no_lookahead_in_any_engine_the_fusion_or_the_labels(cut: int) -> None:
    c = _closes()
    full = E.fit_ensemble(c, NO_GARCH)
    part = E.fit_ensemble(c.iloc[: cut + 2], NO_GARCH)
    i = cut                                     # the return index of the last day in `part`
    assert full.days[i] == part.days[i]
    for name in full.engines:
        assert np.array_equal(full.engines[name][i], part.engines[name][i]), name
    assert np.array_equal(full.weights[i], part.weights[i])
    assert np.array_equal(full.fused[i], part.fused[i])
    day = full.days[i]
    for col in ("vol", "trend", "split"):
        assert full.labels.loc[day, col] == part.labels.loc[day, col], col


def test_fused_beats_the_plain_base_rate_on_clustered_volatility() -> None:
    res = E.fit_ensemble(_closes(days=1100, seed=9), NO_GARCH)
    keep = E.common_mask(res.y, res.fused, res.engines["climatology"])
    fused = E.calibration(res.fused, res.y, keep)
    plain = E.calibration(res.engines["climatology"], res.y, keep)
    got = E.compare(fused, plain)
    assert got["status"] == "MEASURED"
    assert got["verdict"] == "WIN", got
    assert set(res.labels["vol"].unique()) >= {"low", "mid", "high"}


def test_comparison_is_on_identical_days_or_unmeasured() -> None:
    res = E.fit_ensemble(_closes(), NO_GARCH)
    a = E.calibration(res.fused, res.y)
    short = res.engines["climatology"].copy()
    short[: 500] = np.nan
    b = E.calibration(short, res.y)
    assert a["n"] != b["n"]
    assert E.compare(a, b)["status"] == "UNMEASURED"
    keep = E.common_mask(res.y, res.fused, short)
    assert E.compare(E.calibration(res.fused, res.y, keep),
                     E.calibration(short, res.y, keep))["status"] == "MEASURED"
    assert E.calibration(res.fused[:10], res.y[:10])["status"] == "UNMEASURED"


def test_garch_absent_is_named_never_imitated(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    real = builtins.__import__

    def no_arch(name: str, *a: object, **k: object) -> object:
        if name == "arch" or name.startswith("arch."):
            raise ImportError("arch not installed")
        return real(name, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_arch)
    assert "garch" not in E.available_engines()
    res = E.fit_ensemble(_closes(days=620))
    assert "garch" not in res.engines
    assert "garch" in res.unavailable


def test_garch_engine_runs_where_arch_exists() -> None:
    pytest.importorskip("arch")
    c = _closes(days=620)
    res = E.fit_ensemble(c, ("climatology", "garch"))
    assert "garch" in res.engines
    assert np.isfinite(res.engines["garch"][E.MIN_FIT:]).all()
    part = E.fit_ensemble(c.iloc[:452], ("climatology", "garch"))
    assert np.array_equal(res.engines["garch"][450], part.engines["garch"][450])


def test_label_cache_is_keyed_on_the_data() -> None:
    c = _closes(days=620)
    a = E.label_days_cached(pd.DataFrame({"close": c}))
    b = E.label_days_cached(pd.DataFrame({"close": c * 1.5}))
    assert list(a.columns) == ["vol", "trend", "liq", "split"]
    assert (a["liq"] == "").all()
    assert len(E._LABEL_CACHE) >= 2
    assert len(a) == len(b)
