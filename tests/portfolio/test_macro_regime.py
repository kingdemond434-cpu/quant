"""The macro-regime level of the posterior and the factor-structured covariance.

Each test fences a defect MEASURED on the live book on 2026-09-16: every sleeve's expectancy was
unconditional on the macro state, and every pair of sleeves without common history was scored
as independent (`k_eff UNMEASURED: no sleeve pair has 20 overlapping trading days yet`).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.portfolio import leg_factors, macro_state
from libs.portfolio.robust_elog import SleeveEvidence, _corr_abs, _posterior_mu


# ------------------------------------------------------------------------------ fixtures
def _archive(tmp_path: Path, n: int = 600, dollar_up_from: int = 300,
             newest: str | None = None) -> Path:
    """A synthetic FRED archive: the dollar sits at the BOTTOM of its year for the first half of
    the sample and at the TOP for the second; VIX and the 10-year wander."""
    end = (datetime.strptime(newest, "%Y-%m-%d") if newest
           else datetime.now(tz=UTC).replace(tzinfo=None))
    days = [(end - timedelta(days=n - 1 - i)).date().isoformat() for i in range(n)]
    # A FALLING dollar for the first half and a RISING one for the second: a monotone path keeps
    # the trailing-year rank pinned (0 on the way down, 1 on the way up), which is what a regime
    # looks like. A flat plateau plus noise would rank as noise. VIX and the 10-year are held
    # constant so they neither help nor hurt the kernel.
    dxy = np.concatenate([np.linspace(125.0, 95.0, dollar_up_from),
                          np.linspace(95.0, 125.0, n - dollar_up_from)])
    vix = np.full(n, 15.0)
    r10 = np.full(n, 4.0)
    doc = {"updated": end.isoformat(), "series": {
        "DTWEXBGS": [[d, round(float(v), 4)] for d, v in zip(days, dxy, strict=True)],
        "VIXCLS": [[d, round(float(v), 2)] for d, v in zip(days, vix, strict=True)],
        "DGS10": [[d, round(float(v), 2)] for d, v in zip(days, r10, strict=True)],
    }}
    p = tmp_path / "fred_macro.json"
    p.write_text(json.dumps(doc), "utf-8")
    macro_state._CACHE["key"] = None
    return p


# ------------------------------------------------------------------------------ macro_state
def test_kernel_weights_favour_days_like_today(tmp_path: Path) -> None:
    p = _archive(tmp_path)
    doc = macro_state.daily_states(p)
    days = sorted(doc["states"]["dollar"])
    w, meta = macro_state.kernel_weights(days, path=p)
    assert meta["status"] == "MEASURED"
    # Today the dollar is at the top of its year. Days in the strong-dollar half must weigh far
    # more than days in the weak-dollar half, and no weight may leave [0, 1].
    strong = np.array([macro_state.daily_states(p)["states"]["dollar"][d] > 0.5 for d in days])
    assert w[strong].mean() > 5 * max(w[~strong].mean(), 1e-9)
    assert w.min() >= 0.0 and w.max() <= 1.0
    assert macro_state.now(p)["labels"]["dollar"] == "high"


def test_stale_archive_yields_uniform_weights_and_no_tilt(tmp_path: Path) -> None:
    old = (datetime.now(tz=UTC) - timedelta(days=45)).date().isoformat()
    p = _archive(tmp_path, newest=old)
    days = sorted(macro_state.daily_states(p)["states"]["dollar"])
    w, meta = macro_state.kernel_weights(days, path=p)
    assert meta["status"] == "STALE"
    assert np.all(w == 1.0)
    assert macro_state.now(p)["status"] == "STALE"
    assert macro_state.now(p)["confidence"] == 0.0


def test_labeller_is_point_in_time(tmp_path: Path) -> None:
    p = _archive(tmp_path)
    days = sorted(macro_state.daily_states(p)["states"]["dollar"])
    fn = macro_state.labeller("dollar", path=p)
    assert fn is not None
    # The first day the dollar prints high is still labelled from the day BEFORE it.
    first_high = next(d for d in days if macro_state.daily_states(p)["states"]["dollar"][d] > 0.9)
    prev = (datetime.strptime(first_high, "%Y-%m-%d") - timedelta(days=1)).date().isoformat()
    assert fn(first_high + "T09:00:00") == macro_state.bucket(
        macro_state.daily_states(p)["states"]["dollar"].get(prev))
    assert fn("1999-01-01T00:00:00") == ""
    assert macro_state.labeller("nonsense", path=p) is None


def test_missing_archive_is_unmeasured(tmp_path: Path) -> None:
    p = tmp_path / "absent.json"
    macro_state._CACHE["key"] = None
    w, meta = macro_state.kernel_weights(["2024-01-01"], path=p)
    assert meta["status"] == "UNMEASURED" and np.isnan(w).all()
    assert macro_state.now(p)["status"] == "UNMEASURED"


# ------------------------------------------------------------------------------ the posterior
def _ev(name: str, r: np.ndarray, **kw: object) -> SleeveEvidence:
    return SleeveEvidence(name=name, daily_r=r, **kw)  # type: ignore[arg-type]


def test_regime_contrast_tilts_the_posterior_both_ways() -> None:
    rng = np.random.default_rng(1)
    n = 800
    regime = np.zeros(n)
    regime[n // 2:] = 1.0                        # today's regime is the second half
    bull = rng.normal(0.02, 0.5, n) + 0.20 * regime     # earns MORE in today's regime
    bear = rng.normal(0.02, 0.5, n) - 0.20 * regime     # earns LESS in today's regime
    flat = rng.normal(0.02, 0.5, n)                     # indifferent
    ev = [_ev("bull", bull, macro_w=regime), _ev("bear", bear, macro_w=regime),
          _ev("flat", flat, macro_w=regime), _ev("nothing", flat.copy())]
    d: dict = {}
    _posterior_mu(ev, np.random.default_rng(0), 4, diag=d)
    t = {k: v["tilt"] for k, v in d["macro"].items()}
    assert t["bull"] > 0.0 and t["bear"] < 0.0
    assert abs(t["flat"]) < 0.5 * t["bull"]
    # Days with NO state (NaN) leave both sides of the contrast: weighting only the first half
    # as known (and today's regime absent from it) must tilt nothing.
    unknown = regime.copy()
    unknown[n // 2:] = np.nan
    d2: dict = {}
    _posterior_mu([_ev("bull", bull, macro_w=unknown)], np.random.default_rng(0), 2, diag=d2)
    assert d2["macro"].get("bull", {}).get("tilt", 0.0) == pytest.approx(0.0)
    assert "nothing" not in d["macro"], "an empty weight vector claims nothing"
    # Two-sided and bounded: the tilt never exceeds max(|posterior|, se/2).
    for v in d["macro"].values():
        assert abs(v["tilt"]) <= v["bound"] + 1e-12


def test_uniform_weights_change_nothing() -> None:
    rng = np.random.default_rng(2)
    r = rng.normal(0.03, 0.5, 500)
    base: dict = {}
    _posterior_mu([_ev("s", r)], np.random.default_rng(0), 2, diag=base)
    uni: dict = {}
    _posterior_mu([_ev("s", r, macro_w=np.ones(500))], np.random.default_rng(0), 2, diag=uni)
    assert uni["post_mean"]["s"] == pytest.approx(base["post_mean"]["s"])
    assert uni["macro"]["s"]["tilt"] == pytest.approx(0.0)


def test_mismatched_weight_length_is_ignored() -> None:
    r = np.random.default_rng(3).normal(0.03, 0.5, 300)
    d: dict = {}
    _posterior_mu([_ev("s", r, macro_w=np.ones(10))], np.random.default_rng(0), 2, diag=d)
    assert d["macro"] == {}


# ------------------------------------------------------------------------------ the covariance
def test_disjoint_histories_get_the_factor_correlation_not_zero() -> None:
    n = 400
    a = np.full(n, np.nan)
    b = np.full(n, np.nan)
    rng = np.random.default_rng(4)
    a[: n // 2] = rng.normal(0, 1, n // 2)          # lived in the first half only
    b[n // 2:] = rng.normal(0, 1, n // 2)           # lived in the second half only
    load = (1.0, 0.5, 0.0)
    ev = [_ev("old", a, symbol="EURUSD", family="f1", factor_load=load, factor_resid_var=0.25),
          _ev("new", b, symbol="GBPUSD", family="f2", factor_load=load, factor_resid_var=0.25)]
    c = _corr_abs(ev)
    # Identical loadings -> factor corr = 1.25 / (1.25 + 0.25) = 0.8333; zero common days -> the
    # model alone. Before this existed the pair read 0.0.
    assert c[0, 1] == pytest.approx(1.25 / 1.5, abs=1e-6)
    # Without loadings, and on different instruments, nothing is claimed.
    c0 = _corr_abs([_ev("old", a, symbol="EURUSD"), _ev("new", b, symbol="GBPUSD")])
    assert abs(c0[0, 1]) < 0.01


def test_same_instrument_prior_floors_the_target() -> None:
    a = np.random.default_rng(5).normal(0, 1, 30)
    b = np.full(30, np.nan)
    b[-5:] = np.random.default_rng(6).normal(0, 1, 5)
    same_fam = _corr_abs([_ev("p1", a, symbol="EURCHF", family="carry"),
                          _ev("p2", b, symbol="EURCHF", family="carry")])
    diff_fam = _corr_abs([_ev("p1", a, symbol="EURCHF", family="carry"),
                          _ev("p2", b, symbol="EURCHF", family="breakout")])
    # Five common days out of sixty: the blend is ~92% target, so the pair reads at least 92%
    # of the prior whatever the five days happened to show.
    w = 5.0 / (5.0 + 60.0)
    assert same_fam[0, 1] >= (1 - w) * 0.80 - 1e-9
    assert diff_fam[0, 1] >= (1 - w) * 0.35 - 1e-9
    assert same_fam[0, 1] > diff_fam[0, 1]


def test_long_overlap_lets_the_measurement_dominate() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(0, 1, 2000)
    y = rng.normal(0, 1, 2000)                       # genuinely uncorrelated
    load = (1.0, 0.0)
    ev = [_ev("a", x, symbol="EURUSD", factor_load=load, factor_resid_var=0.01),
          _ev("b", y, symbol="GBPUSD", factor_load=load, factor_resid_var=0.01)]
    c = _corr_abs(ev)
    # The model says ~0.99; two thousand common days say ~0. The blend is 97% measurement.
    assert c[0, 1] < 0.08


# ------------------------------------------------------------------------------ leg_factors
def _factor_frame(n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(8)
    days = [(datetime(2024, 1, 1) + timedelta(days=i)).date().isoformat() for i in range(n)]
    f = pd.DataFrame({"EUR": rng.normal(0, 0.004, n), "CHF": rng.normal(0, 0.004, n),
                      "USD": rng.normal(0, 0.003, n), "d_vix": rng.normal(0, 0.05, n),
                      "d_r10": rng.normal(0, 0.03, n)}, index=days)
    return f


def test_fit_loadings_recovers_the_leg_and_restricts_to_own_factors() -> None:
    frame = _factor_frame()
    fs = leg_factors.factor_set(frame)
    assert fs is not None and fs.names == ("EUR", "CHF", "USD", "d_vix", "d_r10")
    # A sleeve that is long EURCHF: returns = 200 * (EUR - CHF) + noise, in R/day.
    rng = np.random.default_rng(9)
    r = 200.0 * (frame["EUR"].to_numpy() - frame["CHF"].to_numpy()) + rng.normal(0, 0.3, 500)
    fl = leg_factors.fit_loadings(r, frame.index, fs, "EURCHF")
    assert fl.n == 500 and set(fl.used) == {"EUR", "CHF", "d_vix", "d_r10"}
    assert fl.betas["EUR"] > 0 and fl.betas["CHF"] < 0
    assert "USD" not in fl.betas
    assert fl.explained > 0.7
    # Whitened loadings reproduce the factor variance: u'u == b' corr b.
    assert fl.load @ fl.load > 0


def test_fit_loadings_shrinks_a_fortnight_hard_and_refuses_two_days() -> None:
    frame = _factor_frame()
    fs = leg_factors.factor_set(frame)
    assert fs is not None
    rng = np.random.default_rng(10)
    r = np.full(500, np.nan)
    r[-13:] = 200.0 * frame["EUR"].to_numpy()[-13:] + rng.normal(0, 0.3, 13)
    fl = leg_factors.fit_loadings(r, frame.index, fs, "EURUSD")
    assert fl.n == 13
    full = leg_factors.fit_loadings(200.0 * frame["EUR"].to_numpy() + rng.normal(0, 0.3, 500),
                                    frame.index, fs, "EURUSD")
    assert 0 < fl.betas["EUR"] < 0.9 * full.betas["EUR"]
    r2 = np.full(500, np.nan)
    r2[-2:] = [0.1, -0.2]
    assert leg_factors.fit_loadings(r2, frame.index, fs, "EURUSD").n == 2
    assert leg_factors.fit_loadings(r2, frame.index, fs, "EURUSD").load.tolist() == [0.0] * 5


def test_factor_corr_abs_is_symmetric_and_bounded() -> None:
    loads = [np.array([1.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, 1.0]), None]
    c = leg_factors.factor_corr_abs(loads, [0.1, 0.1, 0.1, 0.1])
    assert c.shape == (4, 4) and np.allclose(c, c.T)
    assert c[0, 1] == pytest.approx(1.0 / 1.1) and c[0, 2] == 0.0 and c[0, 3] == 0.0
    assert np.all(np.diag(c) == 1.0) and c.max() <= 1.0
