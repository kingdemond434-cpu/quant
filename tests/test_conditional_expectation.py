"""The law of total expectation by state: causal, exact in sample, finds a planted state mean."""
from __future__ import annotations

import numpy as np

from libs.research import conditional_expectation as ce


def _planted(n: int = 6000, h: int = 3, seed: int = 0):
    rng = np.random.default_rng(seed)
    state = rng.integers(0, 3, n)
    fwd = rng.normal(0, 1, n) + np.where(state == 2, 0.4, 0.0)
    return fwd, state, h


def test_decomposition_is_the_law_of_total_expectation():
    fwd, state, _ = _planted()
    dec = ce.decomposition(fwd, state, 3)
    assert abs(dec["total_from_states"] - dec["total_mean"]) < 1e-12
    assert 0.02 < dec["between_share"] < 0.06          # (0.4^2 * 2/9) / ~1.04


def test_causal_means_admit_an_outcome_only_after_its_horizon():
    fwd, state, h = _planted()
    full = ce.causal_state_means(fwd, state, h, 3, min_n=30)
    cut = 4000
    poisoned = fwd.copy()
    poisoned[cut - h:] = 1e6                            # outcomes not complete by row cut
    part = ce.causal_state_means(poisoned, state, h, 3, min_n=30)
    assert np.allclose(full.mean[:cut], part.mean[:cut], equal_nan=True)
    assert np.allclose(full.total[:cut], part.total[:cut], equal_nan=True)


def test_planted_state_is_found_and_the_null_states_are_not():
    fwd, state, h = _planted()
    m = ce.causal_state_means(fwd, state, h, 3, min_n=30)
    z = (m.mean - m.total) / m.se
    late = slice(5000, None)
    assert np.nanmin(z[late][state[late] == 2]) > 3
    null = late.start + np.flatnonzero(state[late] == 0)
    assert np.nanmax(np.abs(m.mean[null] / m.se[null])) < 4      # its own mean is zero
    assert np.nanmax(z[null]) < 0                                 # and sits below the total
