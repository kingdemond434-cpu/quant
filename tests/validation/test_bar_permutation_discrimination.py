"""Does the permutation test actually DISCRIMINATE? The positive and negative controls.

The module's own tests prove the permutation preserves what it claims and destroys what it
claims. That is necessary and nowhere near sufficient: a test can be perfectly implemented and
still be useless, either because it flags everything or because it flags nothing. This file is
the instrument certification -- the same role `libs/validation/positive_control.py` plays for the
gauntlet, and written for the same reason (R0017: a "0 survivors" result is uninterpretable until
you have shown the instrument can produce a survivor).

Three ground truths, because each one fails differently:

    a rule with NO timing skill      must land near p = 0.5   (else the null is biased)
    a rule on REAL serial dependence must land low            (else the test has no power)
    a rule on a PURE RANDOM WALK     must not be systematically low (else it is a p-value machine)

The third is the calibration check and it is the one that would catch the failure that matters:
a test that hands out small p-values on random walks would certify noise as edge, which is the
exact failure the whole gauntlet exists to prevent.
"""
from __future__ import annotations

import numpy as np

from libs.validation.bar_permutation import (
    Bars,
    permutation_pvalue,
    permute_bars,
    to_log_bars,
)

_N_PERM = 150          # above MIN_PERMUTATIONS; p resolution 1/151, ample for a 0.10 threshold


def _ohlc_from_returns(r: np.ndarray, *, seed: int, level: float = 100.0):
    """Wrap a return series in plausible bar geometry so the permutation has gaps and ranges."""
    rng = np.random.default_rng(seed)
    close = level * np.cumprod(1.0 + r)
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1.0 + rng.normal(0, 0.002, len(r)))
    span = np.abs(rng.normal(0, 0.006, len(r))) + 0.001
    high = np.maximum(open_, close) * (1.0 + span)
    low = np.minimum(open_, close) * (1.0 - span)
    return open_, high, low, close


def _ar1(n: int, *, phi: float, seed: int, sigma: float = 0.015) -> np.ndarray:
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = phi * r[i - 1] + rng.normal(0, sigma)
    return r


def _momentum_sharpe(b: Bars, *, lookback: int = 5) -> float:
    """Lag-1 causal momentum. Position from information available at the close of bar t-1."""
    c = b.close                                    # already log
    ret = np.diff(c)                               # ret[i] is the move from bar i to i+1
    if len(ret) <= lookback + 2:
        return float("nan")
    sig = np.sign(c[lookback:-1] - c[:-lookback - 1])
    pnl = sig * ret[lookback:]
    sd = float(np.std(pnl, ddof=1))
    if sd <= 1e-12:
        return float("nan")
    return float(np.mean(pnl) / sd)


def _buy_and_hold_sharpe(b: Bars) -> float:
    r = np.diff(b.close)
    sd = float(np.std(r, ddof=1))
    return float("nan") if sd <= 1e-12 else float(np.mean(r) / sd)


def _pvalue(bars: Bars, stat_fn, *, seed: int, n_perm: int = _N_PERM) -> float:
    rng = np.random.default_rng(seed)
    real = stat_fn(bars)
    perm = np.array([stat_fn(permute_bars(bars, rng=rng)) for _ in range(n_perm)])
    return permutation_pvalue(real, perm)


# ------------------------------------------------------------------ 1. the no-skill control

def test_the_permuted_return_distribution_is_the_real_one_reordered():
    """THE INVARIANT the bias fix rests on, asserted directly rather than through a p-value.

    Close-to-close log return decomposes as gap + intra-bar close move. Because each gap travels
    with its OWN bar, those come back as an exact multiset permutation of the real returns -- so
    mean, variance and every higher moment are preserved, and the only thing destroyed is order.

    Tolerance rather than equality because reassembly is a cumulative sum and accumulates rounding
    at the 1e-12 level; the mathematical statement is exact, the float one is not."""
    o, h, low, c = _ohlc_from_returns(_ar1(1500, phi=0.0, seed=1) + 0.0008, seed=1)
    b = to_log_bars(o, h, low, c)
    rng = np.random.default_rng(101)
    real = np.sort(np.diff(b.close))
    for _ in range(20):
        p = np.sort(np.diff(permute_bars(b, rng=rng).close))
        assert np.allclose(real, p, atol=1e-9), "the return multiset was not preserved"


def test_buy_and_hold_is_never_handed_significance():
    """THE BIAS CHECK, AND THE TEST THAT FOUND THE DEFECT. Buy-and-hold has zero timing skill by
    construction, and by the invariant above its Sharpe is preserved to floating precision on
    every draw -- so its p-value is decided by rounding dust and must sit high, never small.

    This is why the module departs from its source. With the source's two INDEPENDENT permutations
    the gap/intra-bar covariance is dropped, permuted variance inflates, and this exact rule
    scored p = 0.007: significance manufactured entirely by the construction, on a rule that
    cannot possibly have any. A small p here means that bias is back and every other p-value in
    the module is inflated with it."""
    for seed, drift in ((1, 0.0008), (2, 0.004)):
        o, h, low, c = _ohlc_from_returns(_ar1(1500, phi=0.0, seed=seed) + drift, seed=seed)
        b = to_log_bars(o, h, low, c)
        p = _pvalue(b, _buy_and_hold_sharpe, seed=100 + seed)
        assert p > 0.4, f"buy-and-hold scored p={p:.4f} at drift {drift} -- the null is biased"

        # The reason it is not exactly 1.0, pinned so a future real bias cannot hide behind it.
        rng = np.random.default_rng(7)
        real = _buy_and_hold_sharpe(b)
        for _ in range(10):
            got = _buy_and_hold_sharpe(permute_bars(b, rng=rng))
            assert abs(got - real) < 1e-9, "the Sharpe moved by more than rounding"


# ------------------------------------------------------------------ 2. the power control

def test_a_rule_on_real_serial_dependence_is_detected():
    """THE POWER CHECK. An AR(1) series with phi=0.35 genuinely rewards momentum, and the reward
    lives entirely in the ORDER of the bars. The permutation destroys exactly that and nothing
    else, so the real result must sit far out in the permuted distribution."""
    o, h, low, c = _ohlc_from_returns(_ar1(1500, phi=0.35, seed=3), seed=3)
    p = _pvalue(to_log_bars(o, h, low, c), _momentum_sharpe, seed=103)
    assert p < 0.02, f"a real, strong timing edge was not detected (p={p:.3f})"


def test_detection_survives_a_weaker_signal():
    o, h, low, c = _ohlc_from_returns(_ar1(2500, phi=0.18, seed=4), seed=4)
    p = _pvalue(to_log_bars(o, h, low, c), _momentum_sharpe, seed=104)
    assert p < 0.10, f"a moderate timing edge was not detected (p={p:.3f})"


# ------------------------------------------------------------------ 3. the calibration check

def test_it_does_not_manufacture_significance_on_random_walks():
    """THE ONE THAT MATTERS. A test that hands out small p-values on pure random walks would
    certify noise as edge -- the exact failure the gauntlet exists to prevent, arriving through
    the instrument meant to detect it. Twelve independent walks, nominal 10% threshold: a
    correctly calibrated test rejects about 1 in 10 by definition, so the bar is set at 'not
    wildly inflated' rather than at an exact rate the sample size cannot resolve."""
    hits = 0
    for k in range(12):
        o, h, low, c = _ohlc_from_returns(_ar1(900, phi=0.0, seed=200 + k), seed=200 + k)
        if _pvalue(to_log_bars(o, h, low, c), _momentum_sharpe, seed=300 + k) < 0.10:
            hits += 1
    assert hits <= 4, (
        f"{hits}/12 pure random walks were flagged at the 10% level -- the test is a p-value "
        "machine and would certify noise as edge")


def test_a_pure_drift_asset_does_not_certify_a_momentum_rule():
    """Asset drift is the desk's named contamination: a rule that is simply long a trending asset
    must not certify. The permutation preserves the drift exactly, so the rule keeps all of its
    return on every draw and has nothing left to be special about."""
    o, h, low, c = _ohlc_from_returns(_ar1(1500, phi=0.0, seed=5) + 0.005, seed=5)
    p = _pvalue(to_log_bars(o, h, low, c), _momentum_sharpe, seed=105)
    assert p > 0.05, f"a pure-drift asset certified a momentum rule at p={p:.3f}"
