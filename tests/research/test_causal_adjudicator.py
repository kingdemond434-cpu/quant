"""The causal adjudicator: a planted true effect is SUPPORTED, a spurious common-factor
mechanism is REFUTED with the factor named, an unidentifiable one says so, and eligibility
needs the LAWS 5k contract (a falsifier and competing explanations) whatever the numbers say."""
from __future__ import annotations

import numpy as np

from libs.research import causal_adjudicator as ca

N = 1_500


def _planted(seed: int = 1, beta: float = 0.35) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=N)
    y = np.zeros(N)
    y[1:] = beta * x[:-1] + rng.normal(size=N - 1)     # y_{t+1} = beta x_t + noise
    return x, y


def test_a_planted_true_effect_is_supported_and_eligible() -> None:
    x, y = _planted()
    m = ca.Mechanism("planted", x, y, lag=1, claimed_sign=1,
                     placebo_predictors={"noise": np.random.default_rng(9).normal(size=N)},
                     subsets={"first": (np.arange(N) < N // 2).astype(float),
                              "second": (np.arange(N) >= N // 2).astype(float)},
                     simpler={"own_lag": np.concatenate([[0.0], y[:-1]])},
                     competing=("a common factor", "reverse causation"),
                     falsifier="the effect vanishes under the block null")
    adj = ca.adjudicate(m, seed=0, n_perm=200)
    assert adj.verdict == ca.SUPPORTED, adj.to_dict()
    assert adj.eligible and adj.failing_test == ""
    assert adj.estimate["sign"] == 1 and adj.estimate["p"] < 0.05
    assert adj.counterfactual["status"] == "MEASURED"
    assert adj.counterfactual["n_episodes"] > 0
    names = {r.name: r.passed for r in adj.refutations}
    assert names["placebo"] is True and names["subset"] is True
    assert names["simpler_explanation"] is True and names["negative_control"] is None


def test_a_spurious_common_factor_mechanism_is_refuted_with_the_factor_named() -> None:
    rng = np.random.default_rng(3)
    z = rng.normal(size=N)                       # the common factor
    x = 0.9 * z + 0.3 * rng.normal(size=N)       # x is a noisy copy of z
    y = np.zeros(N)
    y[1:] = 0.6 * z[:-1] + rng.normal(size=N - 1)   # y is driven by z, never by x
    without = ca.adjudicate(ca.Mechanism("spurious", x, y, lag=1), seed=0, n_perm=200)
    assert without.verdict == ca.SUPPORTED          # looks real until the factor is held
    with_z = ca.adjudicate(ca.Mechanism("spurious", x, y, lag=1, controls={"z": z}),
                           seed=0, n_perm=200)
    assert with_z.verdict == ca.REFUTED
    assert with_z.failing_test in ("common_factor", "estimation_null")
    if with_z.failing_test == "common_factor":
        assert "'z'" in with_z.eligibility_why


def test_an_unidentifiable_mechanism_says_so_and_a_null_one_is_refuted_at_estimation() -> None:
    x, y = _planted()
    named = ca.adjudicate(ca.Mechanism("named confounder", x, y, lag=1,
                                       confounders_named=("global_risk",)), seed=0, n_perm=50)
    assert named.verdict == ca.UNIDENTIFIABLE and named.failing_test == "identification"
    assert "global_risk" in named.identification["unobserved_confounders"]
    short = ca.adjudicate(ca.Mechanism("short", x[:30], y[:30], lag=1), seed=0, n_perm=50)
    assert short.verdict == ca.UNMEASURED
    rng = np.random.default_rng(5)
    null = ca.adjudicate(ca.Mechanism("null", rng.normal(size=N), rng.normal(size=N), lag=1),
                         seed=0, n_perm=200)
    assert null.verdict == ca.REFUTED and null.failing_test == "estimation_null"


def test_a_true_effect_without_the_candidate_contract_is_supported_but_ineligible() -> None:
    x, y = _planted(seed=2)
    adj = ca.adjudicate(ca.Mechanism("no contract", x, y, lag=1), seed=0, n_perm=200)
    assert adj.verdict == ca.SUPPORTED and not adj.eligible
    assert "no falsifier" in adj.eligibility_why and "competing" in adj.eligibility_why


def test_the_wrong_claimed_sign_and_a_placebo_that_predicts_refute() -> None:
    x, y = _planted(seed=4)
    wrong = ca.adjudicate(ca.Mechanism("wrong sign", x, y, lag=1, claimed_sign=-1),
                          seed=0, n_perm=200)
    assert wrong.verdict == ca.REFUTED and wrong.failing_test == "claimed_sign"
    twin = ca.adjudicate(ca.Mechanism("placebo twin", x, y, lag=1,
                                      placebo_predictors={"copy_of_x": x.copy()}),
                         seed=0, n_perm=200)
    assert twin.verdict == ca.REFUTED and twin.failing_test == "placebo"
    spec = {"name": "from spec", "cause": x.tolist(), "effect": y.tolist(), "lag": 1,
            "claimed_sign": 1, "competing": ["x"], "falsifier": "y"}
    assert ca.adjudicate(ca.mechanism_from_spec(spec), n_perm=100).verdict == ca.SUPPORTED
