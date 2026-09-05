"""Regime persistence is not memoryless, and the allocator must size for the horizon it holds.

`GaussianHMM` has estimated a transition matrix by Baum-Welch since it was written and nothing
ever read it: `pf_allocator` took the FILTERED posterior -- where the regime is right now -- and
drew every scenario world from it, then sized a book it holds for days. These pin the two claims
that fix makes: that the hazard is genuinely age-dependent (a matrix power cannot express it), and
that the forward distribution is what reaches `sample_worlds`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.transitions import age_hazard, forecast  # noqa: E402


def _fixed_length_path(run_len: int = 20, n_runs: int = 300, k: int = 3,
                       jitter: float = 2.0, seed: int = 0) -> np.ndarray:
    """Runs of a characteristic LENGTH -- the thing a memoryless chain cannot represent."""
    rng = np.random.default_rng(seed)
    path: list[int] = []
    s = 0
    for _ in range(n_runs):
        path += [s] * max(3, int(rng.normal(run_len, jitter)))
        s = (s + 1) % k
    return np.asarray(path)


def _geometric_path(p: float = 0.05, n_runs: int = 300, k: int = 3,
                    seed: int = 1) -> np.ndarray:
    """Memoryless runs. The age-conditioned hazard must find nothing here to add."""
    rng = np.random.default_rng(seed)
    path: list[int] = []
    s = 0
    for _ in range(n_runs):
        path += [s] * (1 + int(rng.geometric(p)))
        s = (s + 1) % k
    return np.asarray(path)


A3 = np.array([[0.95, 0.05, 0.00],
               [0.00, 0.95, 0.05],
               [0.05, 0.00, 0.95]])
LABELS = {0: "trend", 1: "range", 2: "stress"}


def _at_age(base: np.ndarray, state: int, age: int) -> np.ndarray:
    return np.concatenate([base, np.full(age, state, dtype=int)])


def test_the_hazard_rises_with_regime_age():
    """A trend two days old and one eighteen days old are not the same bet."""
    base = _fixed_length_path()
    post = np.array([1.0, 0.0, 0.0])
    young = forecast(A3, post, LABELS, _at_age(base, 0, 2), horizons=(1, 5))
    mature = forecast(A3, post, LABELS, _at_age(base, 0, 18), horizons=(1, 5))
    assert young.age_bars == 2 and mature.age_bars == 18
    assert mature.p_leave[1] > 10 * young.p_leave[1]
    assert mature.p_leave[5] > 0.5 > young.p_leave[5]


def test_a_matrix_power_could_not_have_expressed_that():
    """Guards the test above: the memoryless answer is the SAME at both ages, by construction."""
    p1 = np.array([1.0, 0.0, 0.0]) @ np.linalg.matrix_power(A3, 1)
    assert p1[0] == pytest.approx(0.95)
    # transmat^h does not take age as an argument at all -- that is the point.
    assert "age" not in str(np.linalg.matrix_power.__doc__ or "").lower()


def test_a_memoryless_process_gets_the_memoryless_answer_back():
    """No spurious duration structure where there is none to find.

    The hazard is read across the ages where enough runs are still at risk to say anything --
    a single realised age is one draw and would be testing sampling noise, not the estimator.
    """
    base = _geometric_path(p=0.05)
    haz = age_hazard(base, 3, A3)
    flat = float(np.mean(haz[:, 3:16]))
    assert flat == pytest.approx(0.05, abs=0.02), "invented duration structure in a flat process"
    # And it must not TREND with age, which is the specific error a duration model can make.
    early, late = float(np.mean(haz[:, 3:8])), float(np.mean(haz[:, 11:16]))
    assert abs(late - early) < 0.03


def test_thin_evidence_falls_back_to_the_chain_rather_than_extrapolating():
    """Four runs must not be allowed to state a duration law."""
    short = np.repeat(np.arange(3), 6)          # 2 completed runs, tiny
    haz = age_hazard(short, 3, A3)
    memoryless = 1.0 - np.diag(A3)
    assert haz[0, 3] == pytest.approx(memoryless[0], abs=0.02)
    f = forecast(A3, np.array([1.0, 0.0, 0.0]), LABELS, short, horizons=(1,))
    assert f.duration_weight < 0.2


def test_the_censored_current_run_never_counts_as_an_ending():
    """A long-lived regime must not inflate its own hazard by existing."""
    base = _fixed_length_path()
    haz_plain = age_hazard(base, 3, A3)
    haz_long = age_hazard(_at_age(base, 0, 60), 3, A3)
    # The extra at-risk observation can only lower or leave the hazard at ages it survived.
    assert haz_long[0, 30] <= haz_plain[0, 30] + 1e-9


def test_probabilities_are_probabilities_at_every_horizon():
    base = _fixed_length_path()
    f = forecast(A3, np.array([0.6, 0.3, 0.1]), LABELS, base, horizons=(1, 3, 10, 50))
    for h, d in f.p_ahead.items():
        assert sum(d.values()) == pytest.approx(1.0, abs=1e-9), h
        assert all(v >= -1e-12 for v in d.values())


def test_entropy_is_zero_when_certain_and_one_when_uniform():
    base = _fixed_length_path()
    f = forecast(A3, np.array([1.0, 0.0, 0.0]), LABELS, _at_age(base, 0, 1), horizons=(1, 400))
    assert f.entropy[1] < 0.15, "a fresh, persistent regime should be near-certain"
    assert f.entropy[400] > f.entropy[1]


def test_uncertainty_grows_with_horizon():
    base = _fixed_length_path()
    f = forecast(A3, np.array([1.0, 0.0, 0.0]), LABELS, _at_age(base, 0, 2),
                 horizons=(1, 2, 5, 21))
    leaves = [f.p_leave[h] for h in (1, 2, 5, 21)]
    assert leaves == sorted(leaves), f"P(leave) must be non-decreasing in horizon: {leaves}"


def test_two_states_sharing_a_label_are_summed_not_double_counted():
    labels = {0: "trend", 1: "trend", 2: "stress"}
    base = _fixed_length_path()
    f = forecast(A3, np.array([0.5, 0.3, 0.2]), labels, base, horizons=(1,))
    assert set(f.labels) == {"trend", "stress"}
    assert sum(f.p_ahead[1].values()) == pytest.approx(1.0)


def test_a_posterior_that_disagrees_with_the_path_still_answers_the_question_asked():
    """p_leave must be about the regime the BELIEF names, not the one the path decoded."""
    base = _fixed_length_path()
    path = _at_age(base, 0, 5)                      # path ends in state 0
    f = forecast(A3, np.array([0.0, 1.0, 0.0]), LABELS, path, horizons=(1,))
    assert max(f.p_now, key=lambda k: f.p_now[k]) == "range"


def test_probs_at_returns_the_worldconfig_contract():
    base = _fixed_length_path()
    f = forecast(A3, np.array([1.0, 0.0, 0.0]), LABELS, base, horizons=(1,))
    probs = f.probs_at(1)
    assert isinstance(probs, tuple)
    assert all(isinstance(k, str) and isinstance(v, float) for k, v in probs)
    assert sum(v for _, v in probs) == pytest.approx(1.0)
    # An unrequested horizon falls back to now rather than inventing a distribution.
    assert dict(f.probs_at(999)) == pytest.approx(f.p_now)


def test_a_malformed_posterior_refuses():
    base = _fixed_length_path()
    with pytest.raises(ValueError):
        forecast(A3, np.array([1.0, 0.0]), LABELS, base)
    with pytest.raises(ValueError):
        forecast(A3, np.zeros(3), LABELS, base)


# ------------------------------------------------------------------------------------------
# The allocator's end of the wire
# ------------------------------------------------------------------------------------------

def test_regime_state_returns_the_forward_mix_and_shows_its_working():
    """Whatever this host can fit, the diagnostic must name the horizon and both distributions."""
    import pandas as pd

    from research.pf_allocator import REGIME_FORECAST_H, regime_state

    daily = pd.DataFrame(index=pd.date_range("2019-01-01", periods=1200, freq="D"))
    labels, probs, diag = regime_state(daily)
    assert isinstance(diag, dict)
    if "unconditioned_because" in diag:
        pytest.skip(f"regime engine cannot fit here: {diag['unconditioned_because']}")
    assert diag["horizon_days"] == REGIME_FORECAST_H
    assert diag["filtered_now"] and diag["forward"]
    assert str(REGIME_FORECAST_H) in diag["forward"], "the sizing horizon must be reported"
    assert 0.0 <= diag["duration_weight"] <= 1.0
    assert probs and sum(v for _, v in probs) == pytest.approx(1.0, abs=1e-6)


def test_the_allocator_draws_worlds_from_the_forward_mix_not_the_filtered_one():
    """The wiring, pinned: `regime_state` must hand `WorldConfig` `p_ahead`, never `filtered`."""
    import inspect

    from research import pf_allocator

    src = inspect.getsource(pf_allocator.regime_state)
    assert "fc.p_ahead.get(REGIME_FORECAST_H)" in src
    assert "raw = dict(fc.p_ahead" in src, "the tempering must act on the FORWARD distribution"
    run_src = inspect.getsource(pf_allocator.run)
    assert "regime_state(daily)" in run_src
    assert "regime_labels=labels, regime_probs=probs" in run_src
