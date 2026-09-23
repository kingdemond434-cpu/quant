"""`conditional_information` (Tier-1 audit G7): the pairwise test with a confounder held fixed.

Every edge in the world causal graph was X_{t-lag} against Y's OWN lags only, so a common driver
Z that moves X first and Y later makes X look like a cause of Y -- and `incremental_information`
admits it, correctly, because X_{t-lag} carries Z's information that Y's own lags do not. What is
pinned here: on a planted common driver the pairwise test finds X informative and the
conditioned test (Z at its own lag in the base) finds it adds nothing; on a planted DIRECT link
beside the same confounder the conditioned test still finds it; the null is the same circular
shift; misaligned inputs are refused.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research import causal_graph as cg


def _confounded(n: int = 6000, seed: int = 3):
    """Z drives X at lag 1 and Y at lag 2, so X_{t-1} 'leads' Y_t through Z_{t-2} alone."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    x = 0.3 * rng.standard_normal(n)
    y = 0.3 * rng.standard_normal(n)
    x[1:] += 0.8 * z[:-1]
    y[2:] += 0.8 * z[:-2]
    return x, y, z


def test_a_common_driver_passes_the_pairwise_test_and_fails_the_conditioned_one() -> None:
    x, y, z = _confounded()
    pairwise = cg.incremental_information(x, y, 1)
    assert pairwise["delta_r2"] > 0.05 and pairwise["p_value"] <= cg.ALPHA, pairwise
    cond = cg.conditional_information(x, y, z, 1, z_lags=[2])
    assert cond["confounders"] == 1 and cond["z_lags"] == [2]
    assert cond["delta_r2"] < 0.01, cond
    assert cond["p_value"] > cg.ALPHA, cond
    assert cond["r2_base"] > pairwise["r2_base"], "Z in the base explains what X was credited for"


def test_a_direct_link_survives_conditioning_on_the_same_confounder() -> None:
    x, y, z = _confounded()
    y = y + 0.0
    y[1:] += 0.6 * x[:-1]                          # a genuine X -> Y at lag 1, beside Z
    cond = cg.conditional_information(x, y, z, 1, z_lags=[2])
    # Only the part of X that Z does not explain (0.3 of its scale) can count once Z is in the
    # base, so the deltaR2 is small in size and unmistakable in significance.
    assert cond["delta_r2"] > 0.0 and cond["p_value"] <= cg.ALPHA, cond
    confounded_only = cg.conditional_information(*_confounded(), 1, z_lags=[2])
    assert cond["delta_r2"] > 5 * confounded_only["delta_r2"]


def test_several_confounders_enter_at_their_own_lags() -> None:
    x, y, z = _confounded()
    rng = np.random.default_rng(9)
    w = rng.standard_normal(x.size)
    y = y + 0.0
    y[3:] += 0.5 * w[:-3]
    zmat = np.column_stack([z, w])
    cond = cg.conditional_information(x, y, zmat, 1, z_lags=[2, 3])
    assert cond["confounders"] == 2 and cond["z_lags"] == [2, 3]
    assert cond["p_value"] > cg.ALPHA
    # The default lag for every confounder is the edge's own lag.
    default = cg.conditional_information(x, y, zmat, 1)
    assert default["z_lags"] == [1, 1]


def test_refusals_and_the_short_sample() -> None:
    x, y, z = _confounded(n=200)
    with pytest.raises(ValueError):
        cg.conditional_information(x, y, z[:-1], 1)
    with pytest.raises(ValueError):
        cg.conditional_information(x, y, z, 0)
    with pytest.raises(ValueError):
        cg.conditional_information(x, y, z, 1, z_lags=[1, 2])
    short = cg.conditional_information(x[:20], y[:20], z[:20], 1)
    assert short["p_value"] == 1.0 and "too few" in short["note"]


def test_the_null_is_a_circular_shift_and_the_result_is_reproducible() -> None:
    x, y, z = _confounded()
    a = cg.conditional_information(x, y, z, 1, z_lags=[2], seed=5)
    b = cg.conditional_information(x, y, z, 1, z_lags=[2], seed=5)
    assert a == b
    assert a["n_perm"] == cg.N_PERM and a["own_lags"] == cg.OWN_LAGS
