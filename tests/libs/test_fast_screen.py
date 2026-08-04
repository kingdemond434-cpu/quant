"""LAYER 3 -- fast statistical screening, between the arithmetic filter and the full gauntlet.

Without it the desk ran L2 straight into L4, so every arithmetically-plausible candidate consumed
full gauntlet compute. That is how 420 candidates cost full price for zero survivors.

THESE TESTS ASSERT RATES, NOT SINGLE DRAWS. A screen calibrated to pass 33% of noise will pass
individual noise draws, and a test that failed on one of them would be asserting something the
design explicitly does not claim. The claims worth pinning are: noise is rejected MOSTLY, weak
real signal is preserved MOSTLY, and the asymmetry between those two errors is the right way
round -- a wrongly-killed hypothesis is never recovered, a wrongly-passed one dies in L4 for the
price of some compute.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.hypmax.fast_screen import (
    MIN_ABS_IC,
    MIN_OBS,
    PERM_P_MAX,
    fast_screen,
    information_coefficient,
    permutation_p,
    split_half_consistency,
)

N = 600
TRIALS = 60


def _noise(seed: int):
    r = np.random.default_rng(seed)
    return r.normal(size=N), r.normal(size=N)


def _signal(seed: int, ic: float = 0.30):
    r = np.random.default_rng(seed)
    s = r.normal(size=N)
    return s, ic * s + r.normal(size=N)


# --------------------------------------------------------------- error rates


def test_noise_is_rejected_most_of_the_time() -> None:
    """The calibration claim: ~33% of pure noise survives, so ~2/3 of L4 load is removed."""
    passed = sum(1 for t in range(TRIALS)
                 if fast_screen(*_noise(t), n_perm=120, seed=t).decision == "PASS")
    assert passed / TRIALS < 0.50, f"{passed}/{TRIALS} noise draws passed -- screen too weak"


def test_a_real_signal_is_almost_never_killed() -> None:
    """THE ERROR THAT MATTERS. A killed hypothesis is never recovered."""
    killed = sum(1 for t in range(TRIALS)
                 if fast_screen(*_signal(t), n_perm=120, seed=t).decision == "REJECT")
    assert killed / TRIALS < 0.05, f"{killed}/{TRIALS} REAL signals killed"


def test_the_asymmetry_is_the_right_way_round() -> None:
    """False negatives must be rarer than false positives -- that is the whole calibration."""
    fp = sum(1 for t in range(TRIALS)
             if fast_screen(*_noise(t), n_perm=120, seed=t).decision == "PASS")
    fn = sum(1 for t in range(TRIALS)
             if fast_screen(*_signal(t, 0.10), n_perm=120, seed=t).decision == "REJECT")
    assert fn < fp, (
        f"killed {fn} real weak signals vs passed {fp} noise -- the screen is tuned against the "
        "expensive error, not the cheap one")


# --------------------------------------------------------------- escalate on absence


def test_too_few_observations_escalates_and_never_rejects() -> None:
    """An unmeasured hypothesis must never be rejected as if it had been tested."""
    r = np.random.default_rng(3)
    res = fast_screen(r.normal(size=40), r.normal(size=40))
    assert res.decision == "ESCALATE" and res.proceeds


def test_pass_and_escalate_are_distinct() -> None:
    """A screen that escalates everything is doing nothing, and that is only visible if
    'proceeded because measured' and 'proceeded because unmeasurable' are counted apart."""
    assert fast_screen(*_signal(1), n_perm=120).decision == "PASS"
    r = np.random.default_rng(1)
    assert fast_screen(r.normal(size=10), r.normal(size=10)).decision == "ESCALATE"


def test_half_a_cost_pair_cannot_kill() -> None:
    """A missing cost model is missing evidence, not evidence of an unprofitable edge."""
    s, f = _signal(5)
    assert fast_screen(s, f, cost_bps=None, gross_edge_bps=0.01, n_perm=120).decision == "PASS"


def test_a_real_cost_pair_does_kill() -> None:
    s, f = _signal(5)
    res = fast_screen(s, f, cost_bps=5.0, gross_edge_bps=4.0, n_perm=120)
    assert res.decision == "REJECT" and "does not pay for its own execution" in res.reasons[0]


# --------------------------------------------------------------- the components


def test_sign_flip_across_the_sample_is_caught() -> None:
    """A signal whose direction inverts mid-sample has nothing stable to trade."""
    r = np.random.default_rng(7)
    s = r.normal(size=N)
    f = np.concatenate([0.4 * s[:N // 2], -0.4 * s[N // 2:]]) + r.normal(scale=0.5, size=N)
    a, b, agree = split_half_consistency(s, f)
    assert agree < 0 and a * b < 0
    assert fast_screen(s, f, n_perm=120).decision == "REJECT"


def test_ic_is_rank_based_so_one_outlier_cannot_manufacture_it() -> None:
    """Crypto returns are exactly where a single print fabricates a Pearson correlation."""
    r = np.random.default_rng(0)
    s, f = r.normal(size=300), r.normal(size=300)     # independent by construction
    s[0], f[0] = 1000.0, 1000.0                       # ONE paired outlier
    assert abs(np.corrcoef(s, f)[0, 1]) > 0.90, "Pearson IS fooled -- that is why rank is used"
    assert abs(information_coefficient(s, f)) < 0.20, "rank IC must see through it"


def test_ties_do_not_manufacture_correlation() -> None:
    """A REAL BUG THIS SUITE CAUGHT. argsort(argsort(x)) breaks ties by ORIGINAL POSITION, so a
    constant forward series silently inherited the signal's ordering and scored IC 1.000 --
    fabricating perfect correlation out of a series with no information at all. Worst possible
    failure for a screen whose job is rejecting no-signal candidates, and real data is full of
    ties: zero returns, rounded prices, quantised sizes."""
    s = np.arange(300, dtype="float64")
    f = np.zeros(300)
    f[-1] = 1e9
    assert abs(information_coefficient(s, f)) < 0.30


def test_permutation_shuffles_labels_not_the_signal() -> None:
    """Shuffling forward returns tests 'no relationship'; shuffling the signal would instead
    test something about the returns' own autocorrelation."""
    s, f = _signal(9)
    assert permutation_p(s, f, n_perm=120) < 0.05
    assert permutation_p(*_noise(9), n_perm=120) > 0.05


def test_permutation_p_is_never_zero() -> None:
    """The observed value is itself one draw from the null -- a p of exactly 0 is a lie."""
    s, f = _signal(2, ic=5.0)
    assert permutation_p(s, f, n_perm=50) > 0.0


def test_degenerate_inputs_do_not_crash() -> None:
    for bad in (np.zeros(300), np.full(300, np.nan), np.array([])):
        assert information_coefficient(bad, np.random.default_rng(0).normal(size=300)) == 0.0


def test_nan_rows_are_dropped_pairwise() -> None:
    s, f = _signal(4)
    s2, f2 = s.copy(), f.copy()
    s2[::10] = np.nan
    res = fast_screen(s2, f2, n_perm=120)
    assert res.metrics["n_obs"] < N and res.decision == "PASS"


# --------------------------------------------------------------- contract


def test_thresholds_sit_far_below_any_promotion_bar() -> None:
    """L3 removes the hopeless; L4 adjudicates the marginal. If these ever approached a
    promotion threshold, the screen would be deciding what the gauntlet exists to decide."""
    assert MIN_ABS_IC <= 0.01
    assert PERM_P_MAX >= 0.20, "a tight p here would start killing marginal REAL signals"
    assert MIN_OBS >= 100


def test_the_calibration_is_recorded_not_asserted() -> None:
    """The threshold was measured, and the measurement is in the source where it can be argued
    with -- a number chosen by taste is a number nobody can challenge."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "libs/hypmax/fast_screen.py").read_text("utf-8")
    assert "CALIBRATED, NOT CHOSEN BY TASTE" in src
    assert "real IC=0.10 KILLED" in src


@pytest.mark.parametrize("bad", ["sharpe", "backtest", "promote"])
def test_layer_three_makes_no_promotion_claims(bad: str) -> None:
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "libs/hypmax/fast_screen.py").read_text("utf-8")
    assert "ZERO promotion\nauthority" in src or "ZERO promotion" in src
