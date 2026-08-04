"""W3.2 cross-verification: the guard must actually bite, and must stay cheap enough to use.

Adversarial finding W3.2 -- "never trust a single bespoke engine" -- was stated in pyproject
and shipped in libs/backtest/cross_engine.py, then imported by nothing while ~20 screens each
hand-rolled the arithmetic that gates promotion to capital. These tests pin both halves of the
fix: the two independent computations really do disagree when one is wrong (a guard nobody has
seen fire is not a guard), and the primitive stays importable without the platform stack (the
import weight is why it went unused).
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

from libs.metrics.verified import (
    MetricsInputError,
    MetricsVerificationError,
    compare_metrics,
    metrics,
    metrics_or_zero,
    self_test,
)

_PPY = 365.0


def _series(n=2000, mu=0.0004, sd=0.01, seed=7):
    return np.random.default_rng(seed).normal(mu, sd, n)


# ---------------------------------------------------------------- the guard bites
def test_compare_metrics_raises_on_divergence():
    with pytest.raises(MetricsVerificationError, match="sharpe"):
        compare_metrics({"sharpe": 1.0}, {"sharpe": 1.5}, keys=("sharpe",))


def test_compare_metrics_passes_within_tolerance():
    assert compare_metrics({"a": 1.0}, {"a": 1.0 + 1e-12}, keys=("a",))["a"] < 1e-6


def test_self_test_proves_the_guard_fires():
    self_test()


def test_divergence_message_names_both_values():
    """A raise that does not say WHICH metric and what the two values were is not actionable."""
    with pytest.raises(MetricsVerificationError) as e:
        compare_metrics({"cagr": 0.5}, {"cagr": 0.2}, keys=("cagr",))
    msg = str(e.value)
    assert "cagr" in msg and "0.5" in msg and "0.2" in msg


# ---------------------------------------------------------------- agreement with what it replaces
def test_matches_the_bespoke_stats_it_replaces():
    """Drop-in: the ~20 hand-rolled `_stats()` copies must not change their answers."""
    r = _series()
    m = metrics(r, periods_per_year=_PPY)
    cum = np.cumprod(1.0 + r)
    assert m["sharpe"] == pytest.approx(
        float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(_PPY)), abs=1e-3)
    assert m["cagr"] == pytest.approx(float(cum[-1] ** (_PPY / len(r)) - 1.0), abs=1e-3)
    assert m["max_dd"] == pytest.approx(
        float((cum / np.maximum.accumulate(cum) - 1.0).min()), abs=1e-3)


def test_both_paths_agree_across_regimes():
    """Trending, choppy, and drawdown-heavy series must all verify."""
    for mu, sd, seed in ((0.002, 0.005, 1), (0.0, 0.03, 2), (-0.001, 0.02, 3)):
        m = metrics(_series(1500, mu, sd, seed), periods_per_year=_PPY)
        assert np.isfinite(m["sharpe"]) and m["max_dd"] <= 0.0


# ---------------------------------------------------------------- input honesty
def test_costs_are_applied_before_measurement():
    """A gross number is not a decision input -- carry harvested $113 against $876 of cost."""
    r = _series()
    t = np.abs(np.random.default_rng(3).normal(0.5, 0.2, len(r)))
    gross = metrics(r, periods_per_year=_PPY)["sharpe"]
    net = metrics(r, periods_per_year=_PPY, turnover=t, cost_per_turnover=3e-4)["sharpe"]
    assert net < gross


def test_percent_units_are_rejected_not_silently_computed():
    """A series in percent (-1.5 = -150%) makes equity non-positive; that must raise."""
    with pytest.raises(MetricsInputError, match="-100%"):
        metrics(np.array([0.1, -1.5] + [0.01] * 60), periods_per_year=_PPY)


def test_short_sample_raises_but_or_zero_degrades():
    with pytest.raises(MetricsInputError):
        metrics(_series(10), periods_per_year=_PPY)
    assert metrics_or_zero(_series(10), periods_per_year=_PPY)["sharpe"] == 0.0


def test_or_zero_never_swallows_a_verification_failure():
    """Bad input is normal; arithmetic the desk cannot verify is not. Only the former degrades."""
    with pytest.raises(MetricsVerificationError):
        metrics_or_zero(_series(), periods_per_year=_PPY, tolerance=-1.0)


def test_mismatched_turnover_shape_is_rejected():
    with pytest.raises(MetricsInputError, match="shape"):
        metrics(_series(200), periods_per_year=_PPY, turnover=np.ones(199),
                cost_per_turnover=1e-4)


# ---------------------------------------------------------------- it must stay cheap to import
def test_primitive_imports_without_the_platform_stack():
    """Import weight is WHY this went unwired: 20 screens cannot pay duckdb for a Sharpe."""
    code = ("import sys; from libs.metrics.verified import metrics; "
            "print(int(any(m in sys.modules for m in "
            "('duckdb', 'pydantic', 'pydantic_settings', 'scipy', 'pandas'))))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "0", f"heavy dependency pulled in: {out.stdout}"
