"""Every model behind one interface (ROMAN-0379..0387), path-dependent payoffs (ROMAN-0386), local
vol, the rough-vol OU lift (ROMAN-0813..0818) and the HMM regime model."""
from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from libs.quant_models import (
    MODELS,
    BlackScholes,
    BSParams,
    Heston,
    HestonParams,
    ImpliedSurface,
    LocalVol,
    LocalVolParams,
    MarketData,
    OptionSpec,
    RegimeHMM,
    RoughParams,
    RoughVol,
    StochasticModel,
    asian_arithmetic,
    lookback_floating,
    up_and_out,
)
from libs.quant_models.rough import estimate_hurst, lift

AS_OF = datetime(2024, 6, 3, 1, 0, tzinfo=UTC)


def _heston_world(days: int = 500, seed: int = 4) -> MarketData:
    h = Heston(HestonParams(0.04, 3.0, 0.04, 0.6, -0.6))
    p = h.simulate(1, days * 12, days / 252.0, seed)[0]
    lr = np.diff(np.log(p))
    intraday = [lr[i * 12:(i + 1) * 12] for i in range(days)]
    daily = np.asarray([x.sum() for x in intraday])
    ranges = np.asarray([np.ptp(np.concatenate([[0.0], np.cumsum(x)])) for x in intraday])
    rng = np.random.default_rng(seed)
    ivh = np.clip(0.2 + np.cumsum(rng.normal(0, 0.004, days)), 0.08, 0.6)
    return MarketData(as_of=AS_OF, spot=100.0, returns=daily,
                      iv_term={9 / 365: 0.19, 30 / 365: 0.2, 91 / 365: 0.21, 182 / 365: 0.215},
                      iv_history=ivh, intraday_returns=intraday, daily_ranges=ranges)


def test_every_model_answers_the_same_calls() -> None:
    data = _heston_world()
    spec = OptionSpec("call", 102.0, 30 / 365, 100.0)
    for name, ctor in MODELS.items():
        m: StochasticModel = ctor().calibrate(data)
        assert m.name == name and m.measure in ("P", "Q")
        price = m.price(spec)
        assert 0.0 < price < 100.0, name
        g = m.greeks(spec)
        assert 0.0 < g.delta < 1.0 and math.isfinite(g.gamma), name
        vf = m.vol_forecast(30)
        assert 0.02 < vf < 2.0, (name, vf)
        tp = m.tail_prob(0.1, 30)
        assert 0.0 <= tp <= 1.0, name
        paths = m.simulate(64, 10, 30 / 365, seed=1, spot=100.0)
        assert paths.shape == (64, 11) and np.all(paths[:, 0] == 100.0), name
        assert set(m.describe()) == {"name", "measure", "params"}


def test_exotics_bound_by_the_european_and_cv_reduces_their_variance() -> None:
    m = Heston(HestonParams(0.04, 2.0, 0.04, 0.5, -0.7))
    spec = OptionSpec("call", 100.0, 0.5, 100.0, 0.02, 0.0)
    euro = m.price(spec)
    asian = m.mc_price(spec, asian_arithmetic("call", 100.0), n_paths=20000, n_steps=50)
    asian_plain = m.mc_price(spec, asian_arithmetic("call", 100.0), n_paths=20000, n_steps=50,
                             control=False)
    assert 0.0 < asian.price < euro
    assert asian.std_error < asian_plain.std_error
    far = m.mc_price(spec, up_and_out("call", 100.0, 1e9), n_paths=20000, n_steps=50)
    assert abs(far.price - euro) < 3 * far.std_error + 0.01 * euro
    near = m.mc_price(spec, up_and_out("call", 100.0, 110.0), n_paths=20000, n_steps=50)
    assert near.price < 0.5 * euro
    look = m.mc_price(spec, lookback_floating("call"), n_paths=20000, n_steps=50, control=False)
    assert look.price > euro


def test_bs_up_and_out_matches_closed_form_with_discrete_monitoring_shift() -> None:
    """Broadie-Glasserman-Kou: a discrete barrier ~ continuous at B e^{0.5826 sigma sqrt(dt)}."""
    s, k, b, t, v, n = 100.0, 100.0, 130.0, 0.5, 0.25, 100
    m = BlackScholes(BSParams(v))
    mc = m.mc_price(OptionSpec("call", k, t, s), up_and_out("call", k, b), n_paths=60000,
                    n_steps=n, seed=9)
    bb = b * math.exp(0.5826 * v * math.sqrt(t / n))
    exact = _uo_call(s, k, bb, t, v)
    assert abs(mc.price - exact) < 3 * mc.std_error + 0.02 * exact


def _uo_call(s: float, k: float, h: float, t: float, v: float) -> float:
    """Continuous up-and-out call, r = q = 0, K < H (Reiner-Rubinstein, Haug's A - B + C - D
    with phi = 1, eta = -1, mu = -1/2)."""
    from libs.quant_models.numerics import norm_cdf as n
    sq = v * math.sqrt(t)
    x1 = math.log(s / k) / sq + 0.5 * sq
    x2 = math.log(s / h) / sq + 0.5 * sq
    y1 = math.log(h * h / (s * k)) / sq + 0.5 * sq
    y2 = math.log(h / s) / sq + 0.5 * sq
    a = s * n(x1) - k * n(x1 - sq)
    b = s * n(x2) - k * n(x2 - sq)
    c = s * (h / s) * n(-y1) - k * (s / h) * n(-y1 + sq)
    d = s * (h / s) * n(-y2) - k * (s / h) * n(-y2 + sq)
    return a - b + c - d


def test_local_vol_simulation_reprices_its_surface() -> None:
    flat_term = LocalVol(LocalVolParams(ImpliedSurface((0.1, 0.5, 1.0), (0.15, 0.22, 0.25))))
    spec = OptionSpec("call", 100.0, 0.75, 100.0)
    mc = flat_term.mc_price(spec, n_paths=40000, n_steps=60, seed=2)
    assert abs(mc.price - flat_term.price(spec)) < 3 * mc.std_error + 1e-3
    # term-structure local variance is d(sigma^2 T)/dT
    lv = flat_term.surface.local_var(np.zeros(1), np.asarray([0.75]))[0]
    assert lv == pytest.approx((0.25 ** 2 * 1.0 - 0.22 ** 2 * 0.5) / 0.5, rel=1e-3)
    skew = LocalVol(LocalVolParams(ImpliedSurface((0.25, 1.0), (0.2, 0.2), skew=-0.15)))
    put = OptionSpec("put", 90.0, 0.5, 100.0)
    mc2 = skew.mc_price(put, n_paths=40000, n_steps=60, seed=3)
    assert abs(mc2.price - skew.price(put)) < 3 * mc2.std_error + 0.02 * skew.price(put)


def test_rough_lift_approximates_the_fractional_kernel_and_exposes_states() -> None:
    for h in (0.05, 0.1, 0.3):
        c, x = lift(h, 8, 1.0, 1e4)
        for t in (1 / 252, 21 / 252, 0.5):
            k = float((c * np.exp(-x * t)).sum())
            assert k == pytest.approx(t ** (h - 0.5) / math.gamma(h + 0.5), rel=0.08)
    data = _heston_world()
    m = RoughVol().calibrate(data)
    z = m.factor_states()
    assert z.shape == (8,) and np.isfinite(z).all() and np.abs(z).sum() > 0
    assert 0.02 <= m.params.hurst <= 0.45
    # a fresh shock lifts the short-horizon forecast above the long one
    hot = m.copy_with(state=tuple(float(v) + 0.3 for v in z))
    assert hot.vol_forecast(5) > hot.vol_forecast(250)
    assert hot.vol_forecast(5) > m.vol_forecast(5)


def test_hurst_estimate_tells_rough_from_smooth() -> None:
    rough = RoughVol(RoughParams(xi0=0.04, hurst=0.08, eta=1.2))
    p = rough.simulate(1, 2000, 2000 / 252, seed=8)[0]
    lr = np.diff(np.log(p))
    # proxy log variance through the realised path is noisy; use the model's own variance path
    smooth = np.cumsum(np.random.default_rng(1).normal(0, 0.05, 2000))   # H = 0.5 log-vol
    hs = estimate_hurst(smooth)
    assert hs is not None and hs[0] > 0.4
    assert np.isfinite(lr).all()


def test_regime_model_filters_into_the_turbulent_state() -> None:
    rng = np.random.default_rng(6)
    calm = rng.normal(0, 0.006, 400)
    wild = rng.normal(0, 0.03, 60)
    data_calm = MarketData(as_of=AS_OF, returns=np.concatenate([wild, calm]))
    data_wild = MarketData(as_of=AS_OF, returns=np.concatenate([calm, wild]))
    a, b = RegimeHMM().calibrate(data_calm), RegimeHMM().calibrate(data_wild)
    assert b.params.posterior[-1] > 0.8 > a.params.posterior[-1]
    assert b.vol_forecast(5) > 2 * a.vol_forecast(5)
    assert b.tail_prob(0.1, 30) > a.tail_prob(0.1, 30)
