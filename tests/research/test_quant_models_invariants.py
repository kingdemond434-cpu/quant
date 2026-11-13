"""Seeded-defect invariants of the shared pricing math (cards QG-QFIN-005, QG-ADH-003; ROMAN-0969).

Every check here is paired with the published defect it exists to catch: a test that cannot
tell the defective formula from the right one is not a test (the card's falsifier: "a regression
test that seeds the defect and is not caught")."""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from libs.quant_models import (
    BlackScholes,
    BSParams,
    Garch,
    GarchParams,
    Heston,
    HestonParams,
    Merton,
    MertonParams,
    OptionSpec,
    bs_greeks,
    bs_price,
    fd_greeks,
    fit_garch,
    implied_vol,
)
from libs.quant_models.garch import simulate_garch
from libs.quant_models.numerics import cf_price, gbm_paths, mc_estimate, normals

GRID = [(k, t, v) for k in (70.0, 95.0, 100.0, 110.0, 140.0) for t in (0.05, 0.5, 2.0)
        for v in (0.1, 0.3, 0.8)]
S, R, Q = 100.0, 0.03, 0.01


# ------------------------------------------------------------------ parity
def _parity_gap(call: float, put: float, k: float, t: float) -> float:
    return abs(call - put - (S * math.exp(-Q * t) - k * math.exp(-R * t)))


def _qfin_put(k: float, t: float, v: float) -> float:
    """The Q-Fin defect: K e^{-rT} N(d1) - S N(d2)."""
    d1 = (math.log(S / k) + (R - Q + 0.5 * v * v) * t) / (v * math.sqrt(t))
    d2 = d1 - v * math.sqrt(t)
    return k * math.exp(-R * t) * norm.cdf(d1) - S * norm.cdf(d2)


def test_put_call_parity_holds_and_catches_the_qfin_put() -> None:
    worst = max(_parity_gap(bs_price("call", S, k, t, R, Q, v), bs_price("put", S, k, t, R, Q, v),
                            k, t) for k, t, v in GRID)
    assert worst < 1e-8
    seeded = max(_parity_gap(bs_price("call", S, k, t, R, Q, v), _qfin_put(k, t, v), k, t)
                 for k, t, v in GRID)
    assert seeded > 1.0


def test_parity_for_every_closed_or_cf_model() -> None:
    models = [Heston(HestonParams(0.05, 2.0, 0.04, 0.6, -0.7)),
              Merton(MertonParams(0.2, 0.8, -0.08, 0.12))]
    for m in models:
        for k in (80.0, 100.0, 125.0):
            c = m.price(OptionSpec("call", k, 0.75, S, R, Q))
            p = m.price(OptionSpec("put", k, 0.75, S, R, Q))
            assert _parity_gap(c, p, k, 0.75) < 1e-8


# ------------------------------------------------------------------ greeks
def _fd_gamma(k: float, t: float, v: float) -> float:
    h = 1e-2
    return (bs_price("call", S + h, k, t, R, Q, v) - 2 * bs_price("call", S, k, t, R, Q, v)
            + bs_price("call", S - h, k, t, R, Q, v)) / (h * h)


def test_gamma_uses_the_pdf_and_a_cdf_gamma_is_caught() -> None:
    for k, t, v in GRID:
        g = bs_greeks("call", S, k, t, R, Q, v)["gamma"]
        assert abs(g - _fd_gamma(k, t, v)) < 1e-4
    k, t, v = 100.0, 0.5, 0.3
    d1 = (math.log(S / k) + (R - Q + 0.5 * v * v) * t) / (v * math.sqrt(t))
    cdf_gamma = math.exp(-Q * t) * norm.cdf(d1) / (S * v * math.sqrt(t))   # the seeded defect
    assert abs(cdf_gamma - _fd_gamma(k, t, v)) > 1e-3


@pytest.mark.parametrize("kind", ["call", "put"])
def test_fd_greeks_match_closed_form(kind: str) -> None:
    for k, t, v in GRID:
        if t < 0.1 and abs(k - S) > 25:
            continue                      # deep OTM short-dated: all greeks ~ 0, FD is noise
        spec = OptionSpec(kind, k, t, S, R, Q)  # type: ignore[arg-type]
        m = BlackScholes(BSParams(v))
        cf, fd = m.greeks(spec), fd_greeks(m, spec, rel_spot=2e-4)
        assert cf.method == "closed_form" and fd.method == "central_fd"
        assert abs(cf.delta - fd.delta) < 1e-5
        assert abs(cf.gamma - fd.gamma) < 1e-4
        assert abs(cf.vega - fd.vega) < 1e-3 * max(1.0, cf.vega)
        assert abs(cf.rho - fd.rho) < 1e-3 * max(1.0, abs(cf.rho))
        assert abs(cf.theta - fd.theta) < 2e-2 * max(1.0, abs(cf.theta))


# ------------------------------------------------------------------ model limits
def test_heston_collapses_to_bs_when_vol_of_vol_vanishes() -> None:
    for k in (80.0, 100.0, 120.0):
        for t in (0.1, 1.0):
            bs = bs_price("call", S, k, t, R, Q, 0.2)
            exact = Heston(HestonParams(0.04, 1.5, 0.04, 1e-7, -0.7))      # degenerate branch
            near = Heston(HestonParams(0.04, 1.5, 0.04, 1e-4, -0.7))       # the CF itself
            spec = OptionSpec("call", k, t, S, R, Q)
            assert abs(exact.price(spec) - bs) < 1e-7
            assert abs(near.price(spec) - bs) < 1e-3          # O(rho * sigma) correction


def test_merton_with_zero_jumps_is_bs_and_series_equals_cf() -> None:
    spec = OptionSpec("put", 95.0, 0.6, S, R, Q)
    m0 = Merton(MertonParams(0.25, 0.0, -0.1, 0.1))
    assert abs(m0.price(spec) - bs_price("put", S, 95.0, 0.6, R, Q, 0.25)) < 1e-12
    assert abs(cf_price(m0.cf(0.6), "put", S, 95.0, 0.6, R, Q, 0.25 ** 2 * 0.6)
               - m0.price(spec)) < 1e-7
    mj = Merton(MertonParams(0.2, 1.2, -0.1, 0.15))
    for k in (70.0, 100.0, 130.0):
        sp = OptionSpec("call", k, 0.6, S, R, Q)
        series = mj.price(sp)
        cf = cf_price(mj.cf(0.6), "call", S, k, 0.6, R, Q, mj.expected_var(0.6) * 0.6)
        assert abs(series - cf) < 1e-6


def test_heston_cf_price_matches_its_own_monte_carlo() -> None:
    h = Heston(HestonParams(0.04, 2.0, 0.04, 0.5, -0.7))
    spec = OptionSpec("call", 105.0, 0.5, S, R, Q)
    mc = h.mc_price(spec, n_paths=60000, n_steps=100, seed=5)
    # full-truncation Euler bias is small at 100 steps; allow 3 s.e. plus a 1% bias band
    assert abs(mc.price - h.price(spec)) < 3 * mc.std_error + 0.01 * h.price(spec)


# ------------------------------------------------------------------ Monte Carlo
def test_control_variates_hit_closed_form_and_reduce_variance() -> None:
    m = BlackScholes(BSParams(0.3))
    spec = OptionSpec("call", 100.0, 1.0, S, R, Q)
    exact = m.price(spec)
    cv = m.mc_price(spec, n_paths=40000, n_steps=1, seed=3, antithetic=False, control=True)
    plain = m.mc_price(spec, n_paths=40000, n_steps=1, seed=3, antithetic=False, control=False)
    assert abs(cv.price - exact) < 3 * cv.std_error
    assert abs(plain.price - exact) < 3 * plain.std_error
    assert cv.std_error ** 2 < 0.5 * plain.std_error ** 2
    anti = m.mc_price(spec, n_paths=40000, n_steps=1, seed=3, antithetic=True, control=False)
    assert abs(anti.price - exact) < 3 * anti.std_error


def test_mc_variance_step_uses_sigma_squared_and_the_sqrt_defect_is_caught() -> None:
    v, t, n = 0.3, 1.0, 100000
    z = normals(np.random.default_rng(11), n, 1, False)
    exact = bs_price("call", S, 100.0, t, R, Q, v)
    disc = math.exp(-R * t)

    def est(vol_path: np.ndarray) -> tuple[float, float]:
        p = gbm_paths(S, vol_path, t, R, Q, z)
        r = mc_estimate(disc * np.maximum(p[:, -1] - 100.0, 0.0))
        return r.price, r.std_error
    good, se = est(np.full_like(z, v))
    assert abs(good - exact) < 3 * se
    # Q-Fin: inst_var = sqrt(sigma). Feed a vol whose square is sqrt(sigma).
    bad, se_b = est(np.full_like(z, math.sqrt(math.sqrt(v))))
    assert abs(bad - exact) > 10 * se_b


# ------------------------------------------------------------------ GARCH and IV
def test_garch_mle_recovers_simulated_parameters() -> None:
    truth = GarchParams(omega=2e-6, alpha=0.08, beta=0.9, h_next=1e-4)
    r = simulate_garch(truth, 1, 6000, seed=21)[0]
    got = fit_garch(r - r.mean())
    assert abs(got.alpha - 0.08) < 0.03
    assert abs(got.beta - 0.9) < 0.04
    lr_true = math.sqrt(truth.long_run_var * 252)
    lr_got = math.sqrt(got.long_run_var * 252)
    assert abs(lr_got - lr_true) / lr_true < 0.2
    g = Garch(got)
    assert math.isfinite(g.vol_forecast(30)) and g.vol_forecast(30) > 0


def test_implied_vol_round_trips_and_refuses_arbitrage() -> None:
    for kind in ("call", "put"):
        for k, t, v in GRID:
            p = bs_price(kind, S, k, t, R, Q, v)
            iv = implied_vol(p, kind, S, k, t, R, Q)
            itm = max((S * math.exp(-Q * t) - k * math.exp(-R * t)) * (1 if kind == "call" else -1),
                      0.0)
            if p - itm < 1e-8:
                continue               # no time value left: the price carries no vol
            assert iv is not None and abs(iv - v) < 1e-6, (kind, k, t, v, iv)
    assert implied_vol(1e-9, "call", S, 50.0, 1.0, R, Q) is None        # below intrinsic
    assert implied_vol(S * 2, "call", S, 100.0, 1.0, R, Q) is None      # above the spot bound


# ------------------------------------------------------------------ the clock (QG-ADH-003)
def test_expiry_comes_from_the_injected_clock_never_today() -> None:
    now = datetime(2019, 1, 2, 21, 0, tzinfo=UTC)
    expiry = datetime(2019, 3, 15, 21, 0, tzinfo=UTC)
    spec = OptionSpec.from_dates("call", 100.0, expiry, now, S)
    # computed from today (2026+) this expiry is long past and T would be 0
    assert spec.expiry_years == pytest.approx(72 / 365.0, abs=1e-12)
    a = BlackScholes(BSParams(0.2)).price(spec)
    b = BlackScholes(BSParams(0.2)).price(OptionSpec.from_dates("call", 100.0, expiry, now, S))
    assert a == b and a > 1.0
    with pytest.raises(ValueError):
        OptionSpec.from_dates("call", 100.0, expiry.replace(tzinfo=None), now, S)


def test_no_model_reads_the_wall_clock() -> None:
    pkg = Path(__file__).resolve().parents[2] / "libs" / "quant_models"
    bad = re.compile(r"datetime\.now\(|date\.today\(|time\.time\(|utcnow\(|time\.monotonic\(")
    hits = [f"{p.name}:{i}" for p in pkg.glob("*.py")
            for i, line in enumerate(p.read_text("utf-8").splitlines(), 1)
            if bad.search(line) and not line.lstrip().startswith("#")]
    assert hits == []
