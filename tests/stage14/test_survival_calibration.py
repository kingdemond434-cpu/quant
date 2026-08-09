"""What the survival gate's defaults actually reject, pinned so the number cannot go stale.

`libs/discovery/monte_carlo_survival.monte_carlo_survival` has no production caller -- its only
importers are libs/stage14/{growth,analytics}.py, which are imported only by their own tests. It
is inert, which is exactly why its defaults have never been checked against anything real. An
inert gate with unreachable defaults is a landmine: the day someone wires it, the campaign returns
zero survivors and the reading will be "price space is picked clean" rather than "the limit was
never calibrated".

These tests do not assert that the defaults are RIGHT. They assert what the defaults DO, so that
the next person to wire this sees the number instead of discovering it in a dead campaign.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND

_PPY = 365.0
#: Daily standard deviation of a crypto perp -- roughly 57% annualised. The desk trades these, so
#: this is the volatility the limit has to be correct at, not equity volatility.
_CRYPTO_DAILY_SD = 0.03


def _series(true_sharpe: float, *, n: int = 1000, seed: int = 7) -> np.ndarray:
    """Daily returns with a given true annualised Sharpe and crypto-like fat tails."""
    rng = np.random.default_rng(seed)
    mu = true_sharpe * _CRYPTO_DAILY_SD / np.sqrt(_PPY)
    # t(4) scaled to unit variance: fat tails, which is what drives drawdown.
    return mu + _CRYPTO_DAILY_SD * rng.standard_t(4, size=n) / np.sqrt(2.0)


@pytest.mark.parametrize("true_sharpe", [0.5, 1.0, 1.5])
def test_the_default_drawdown_limit_rejects_the_entire_real_edge_band(true_sharpe):
    """THE CALIBRATION FACT. 0.5-1.5 is REAL_EDGE_OOS_SHARPE_BAND -- where an external 131,441
    backtest sweep observed genuine verified edge to live. At dd_limit=0.20 the survival
    probability is 0.000 across all of it, so the gate is not strict, it is unreachable.

    If this test starts FAILING, that is good news and means someone recalibrated the default.
    Update the number here to whatever was measured; do not delete the check."""
    lo, hi = REAL_EDGE_OOS_SHARPE_BAND
    assert lo <= true_sharpe <= hi, "the parametrisation drifted out of the recorded band"
    res = monte_carlo_survival(_series(true_sharpe), n_sims=600, seed=3)
    assert not res.passed
    assert res.survival_probability < 0.01, (
        f"survival at true Sharpe {true_sharpe} is {res.survival_probability:.3f} -- the default "
        "dd_limit has been recalibrated, update this test with the new measurement")


def test_realistic_crypto_drawdowns_are_multiples_of_the_default_limit():
    """Why the gate is unreachable, stated as the underlying quantity rather than a pass rate.
    An external 350,000-backtest Bitcoin sweep found zero walk-forward survivors under a 40%
    drawdown cap and its best survivor ran a 42% drawdown at OOS Sharpe 1.08."""
    res = monte_carlo_survival(_series(1.08), n_sims=600, seed=3)
    assert res.median_drawdown > 0.40, (
        f"median drawdown {res.median_drawdown:.3f} -- the fixture stopped being crypto-like")


def test_loosening_the_limit_alone_does_not_rescue_it():
    """The tempting fix, measured and rejected. survival_min=0.95 asks for the 95th-PERCENTILE
    drawdown to clear the limit, so even a 60% cap leaves a Sharpe-1.08 strategy far short. A
    limit that has to be widened until something passes is being fitted to the violation."""
    res = monte_carlo_survival(_series(1.08), dd_limit=0.60, n_sims=600, seed=3)
    assert not res.passed and res.survival_probability < 0.95


def test_the_gate_still_works_where_it_was_designed_to():
    """The control: this is not a broken function, it is a mis-set constant. At equity-like
    volatility with a strong edge the gate passes, which is what makes the crypto reading a
    calibration finding rather than a bug report."""
    rng = np.random.default_rng(11)
    calm = 0.004 * rng.standard_t(8, size=1500) / np.sqrt(8 / 6)
    calm = calm + 2.5 * 0.004 / np.sqrt(_PPY)
    res = monte_carlo_survival(calm, n_sims=600, seed=3)
    assert res.passed, f"survival {res.survival_probability:.3f} on a calm, strong-edge series"
