"""ROMAN-0972: control variates for the validation Monte Carlos -- exactness, unbiasedness, and
the rule that a control variate can tighten a gate but never loosen one."""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from libs.validation import control_variates as cv
from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError
from libs.validation.random_baseline import monkey_test
from libs.validation.reality_check import hansen_spa, whites_reality_check


def _ar(seed: int, n: int, phi: float = 0.4) -> np.ndarray:
    g = np.random.default_rng(seed)
    e = g.normal(size=n)
    x = np.empty(n)
    x[0] = e[0]
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


# --- the known expectations are exact ---------------------------------------------------------

def test_stationary_bootstrap_variance_formula_matches_the_index_process() -> None:
    x = _ar(1, 80)
    exact = cv.stationary_bootstrap_mean_variance(x, 6)
    rng = np.random.default_rng(2)
    draws = np.array([x[stationary_block_indices(80, 6, rng)].mean() for _ in range(20_000)])
    # sampling error of a variance from 20k draws is ~1%; 4% is a real discrepancy
    assert abs(draws.var() / exact - 1.0) < 0.04
    assert abs(draws.mean() - x.mean()) < 4 * np.sqrt(exact / 20_000)


def test_variance_formula_limits() -> None:
    x = _ar(3, 50)
    # mean_block = 1 restarts every bar: the i.i.d. bootstrap, Var = c(0)/T
    assert cv.stationary_bootstrap_mean_variance(x, 1) == pytest.approx(x.var() / 50, rel=1e-12)
    assert cv.stationary_bootstrap_mean_variance(np.ones(10), 5) == pytest.approx(0.0, abs=1e-15)


def test_permutation_moments_are_exact_by_enumeration() -> None:
    p = np.array([1.0, 0.0, 1.0, -1.0, 0.5])
    r = np.array([0.3, -0.2, 0.1, 0.4, -0.5])
    m1, m11, m2 = [], [], []
    for perm in itertools.permutations(range(5)):
        x = p[list(perm)] * r
        m1.append(x.mean())
        m11.append(x.mean() ** 2)
        m2.append(np.mean(x * x))
    e1, e11, e2 = cv.permutation_control_moments(p, r)
    assert e1 == pytest.approx(np.mean(m1), abs=1e-15)
    assert e11 == pytest.approx(np.mean(m11), abs=1e-15)
    assert e2 == pytest.approx(np.mean(m2), abs=1e-15)


# --- the raw numbers are the production numbers -----------------------------------------------

@pytest.mark.parametrize("seed", [0, 7])
def test_raw_pvalue_is_bit_identical_to_reality_check(seed: int) -> None:
    f = np.random.default_rng(seed).normal(0, 1, (120, 5))
    f[:, 2] += 0.15
    assert cv.bootstrap_pvalue_cv(f, n_boot=150, seed=seed).p_raw == \
        hansen_spa(f, n_boot=150, seed=seed).p_value
    assert cv.bootstrap_pvalue_cv(f, method="white", n_boot=150, seed=seed).p_raw == \
        whites_reality_check(f, n_boot=150, seed=seed).p_value


def test_raw_monkey_pvalue_is_monkey_tests() -> None:
    pos, r = cv._planted_monkey(4, 0.05, 400)
    m = cv.monkey_pvalue_cv(pos, r, rng=np.random.default_rng(3), n_baselines=300)
    assert m is not None
    assert m.p_raw == monkey_test(pos, r, rng=np.random.default_rng(3),
                                  n_baselines=300)["p_value"]


# --- the estimator: unbiased, lower variance where it can be, raw where it cannot -------------

def test_cross_fitted_estimate_is_unbiased_for_a_nonlinear_indicator() -> None:
    """Y = 1{Z + noise > 1}, C = (Z, Z^2) with exact means: mean(controlled - raw) ~ 0."""
    diffs, raws, ctls = [], [], []
    for s in range(600):
        g = np.random.default_rng(s)
        z = g.normal(size=200)
        y = (z + 0.5 * g.normal(size=200) > 1.0).astype(float)
        e = cv.control_variate_mean(y, np.column_stack([z, z * z]), [0.0, 1.0])
        diffs.append(e.controlled - e.raw)
        raws.append(e.raw)
        ctls.append(e.controlled)
    d = np.asarray(diffs)
    assert abs(d.mean()) < 4 * d.std(ddof=1) / np.sqrt(d.size)
    assert np.var(ctls) < 0.8 * np.var(raws)     # and it actually reduces variance


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), rho=st.floats(-0.95, 0.95))
def test_linear_control_recovers_the_one_minus_rho_squared_law(seed: int, rho: float) -> None:
    g = np.random.default_rng(seed)
    c = g.normal(size=2_000)
    y = 3.0 + rho * c + np.sqrt(1 - rho**2) * g.normal(size=2_000)
    e = cv.control_variate_mean(y, c, [0.0])
    assert e.variance_ratio is not None
    assert e.variance_ratio == pytest.approx(1 - rho**2, abs=0.08)
    assert abs(e.controlled - 3.0) < 5 * np.sqrt(e.controlled_var)


def test_value_falls_back_to_raw_without_measured_gain() -> None:
    g = np.random.default_rng(0)
    y = g.normal(size=40)
    e = cv.control_variate_mean(y, g.normal(size=(40, 15)), np.zeros(15))
    assert not e.used and e.value == e.raw          # 15 junk controls on 40 draws cost variance
    tiny = cv.control_variate_mean([1.0, 0.0, 1.0], [0.1, 0.2, 0.3], [0.2])
    assert not tiny.used and tiny.value == tiny.raw and np.isnan(tiny.controlled)


def test_rejects_in_sample_beta_and_bad_shapes() -> None:
    with pytest.raises(ValidationError):
        cv.control_variate_mean([1.0, 2.0], [1.0, 2.0], [0.0], folds=1)
    with pytest.raises(ValidationError):
        cv.control_variate_mean([1.0, 2.0], [[1.0, 2.0]], [0.0])
    with pytest.raises(ValidationError):
        cv.control_variate_mean([1.0, np.nan, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0], [0.0])


# --- never loosen a bar ----------------------------------------------------------------------

@pytest.mark.parametrize("raw,ctl", list(itertools.product([True, False], [True, False, None])))
def test_guarded_decision_never_passes_what_raw_fails(raw: bool, ctl: bool | None) -> None:
    out = cv.guarded_decision(raw, ctl)
    assert out["passed"] == (raw and ctl is not False)
    if not raw:
        assert out["passed"] is False
    assert out["changed"] == (raw and ctl is False)


@settings(max_examples=15, deadline=None)
@given(seed=st.integers(0, 10_000), edge=st.floats(0.0, 0.4), alpha=st.floats(0.01, 0.5))
def test_bootstrap_decision_is_never_looser_than_raw(seed: int, edge: float,
                                                      alpha: float) -> None:
    f = np.random.default_rng(seed).normal(0, 1, (80, 4))
    f[:, 0] += edge
    bp = cv.bootstrap_pvalue_cv(f, n_boot=80, seed=seed)
    d = bp.decision(alpha)
    assert d["passed"] <= (bp.p_raw < alpha)
    if bp.p_controlled is not None:
        assert 0.0 <= bp.p_controlled <= 1.0
        assert bp.estimate is not None and bp.estimate.used


def test_zero_variance_strategies_carry_no_control() -> None:
    f = np.zeros((60, 3))
    f[:, 1] = np.random.default_rng(1).normal(size=60)
    bp = cv.bootstrap_pvalue_cv(f, n_boot=60)
    assert bp.control_strategies == (1,)
    assert cv.bootstrap_pvalue_cv(np.zeros((60, 2)), n_boot=30).estimate is None


# --- the planted-truth measurement the hourly leg publishes -----------------------------------

def test_planted_truth_report_measures_lower_variance_and_never_loosens(tmp_path: Path) -> None:
    doc = cv.write_report(tmp_path / "CONTROL_VARIATES.json", quick=True)
    assert (tmp_path / "CONTROL_VARIATES.json").exists()
    for arm in ("spa", "monkey"):
        s = doc[arm]["summary"]
        assert s["pooled_variance_ratio"] is not None and s["pooled_variance_ratio"] < 1.0
        assert s["max_abs_bias_t"] < 4.0
        assert s["correct_guarded"] <= s["correct_raw"] + s["gate_changed_stricter"]
        for c in doc[arm]["cells"].values():
            assert c["gate"]["guarded_pass"] <= c["gate"]["raw_pass"]
