"""The two deflator inputs no forward artifact had ever published.

WHY THIS IS WORTH TESTING HARD. `regime_penalty(0)` and `regime_penalty(1)` are both 0.5, so
publishing a WRONG regime count is indistinguishable from publishing none until it is too high --
and too high halves the evidence requirement in effect. The tests that matter are therefore the
ones that would catch over-counting: a clock is credited only with the regimes ITS OWN
observations fell in, never the ones its price history happens to contain.
"""

from __future__ import annotations

import numpy as np

from libs.research.regime_coverage import (
    TREND_LOOKBACK,
    lag1_autocorr,
    regime_coverage,
)


def _series(n: int = 400, *, seed: int = 7) -> list[float]:
    """A path that genuinely visits both trend states and both volatility states."""
    rng = np.random.default_rng(seed)
    out, px = [], 100.0
    for i in range(n):
        vol = 0.01 if (i // 60) % 2 == 0 else 0.05        # alternating vol regimes
        drift = 0.004 if (i // 120) % 2 == 0 else -0.004  # alternating trend regimes
        px *= 1.0 + drift + float(rng.normal(0, vol))
        out.append(px)
    return out


# --------------------------------------------------------------------------- lag1_autocorr

def test_A_SERIES_TOO_SHORT_TO_ESTIMATE_RETURNS_NONE_NOT_ZERO() -> None:
    """Zero is the value at which the serial deflator credits the FULL raw count, so returning it
    for an unestimable series hands every new clock the most generous deflator on no evidence --
    the same defaulted-zero-reads-as-measurement defect that published a flat 213x gain."""
    assert lag1_autocorr([0.01, -0.02, 0.03]) is None
    assert lag1_autocorr([]) is None


def test_A_CONSTANT_SERIES_IS_NONE_NOT_ZERO() -> None:
    """A stuck recorder echoing one value has no measurable autocorrelation, and crediting it the
    full raw count is exactly the promotion path a dead feed must never get."""
    assert lag1_autocorr([0.01] * 50) is None


def test_A_STICKY_SERIES_REPORTS_POSITIVE_AUTOCORRELATION() -> None:
    rng = np.random.default_rng(3)
    x, prev = [], 0.0
    for _ in range(300):
        prev = 0.8 * prev + float(rng.normal(0, 0.01))
        x.append(prev)
    rho = lag1_autocorr(x)
    assert rho is not None and rho > 0.6


def test_NEGATIVE_AUTOCORRELATION_IS_RETURNED_HONESTLY() -> None:
    """The deflator clamps negatives itself. Clamping here as well would hide that a
    mean-reverting clock carries MORE information per observation than it is credited for."""
    x = [0.01 * (-1) ** i for i in range(200)]
    rho = lag1_autocorr(x)
    assert rho is not None and rho < -0.9


# --------------------------------------------------------------------------- regime_coverage

def test_TOO_SHORT_TO_LABEL_IS_ZERO_NOT_ONE() -> None:
    """'We could not tell' and 'we measured one regime' are different claims. Folding the first
    into the second is the substitution that left every clock paying the 0.5 penalty."""
    n, detail = regime_coverage([100.0] * (TREND_LOOKBACK - 5))
    assert n == 0 and detail["status"] == "UNMEASURED"


def test_A_PATH_THROUGH_SEVERAL_STATES_COUNTS_THEM() -> None:
    n, detail = regime_coverage(_series())
    assert n >= 2, detail
    assert detail["status"] == "MEASURED" and detail["cells"]


def test_A_CLOCK_IS_CREDITED_ONLY_WITH_THE_REGIMES_IT_OBSERVED() -> None:
    """THE OVER-COUNTING GUARD, and the one that costs money if it breaks. A clock born last week
    has not covered the regimes its two-year price history contains, and crediting them would
    halve an evidence requirement on observations that were never collected."""
    closes = _series()
    whole, _ = regime_coverage(closes)
    recent, _ = regime_coverage(closes, list(range(len(closes) - 12, len(closes))))
    assert recent <= whole
    assert recent <= 2, "twelve consecutive days cannot span four regime cells"


def test_OBSERVATIONS_BEFORE_THE_WINDOWS_FILL_ARE_UNMEASURED() -> None:
    """Bars the labeller cannot label are not silently dropped into a smaller count -- with none
    labellable the answer is UNMEASURED, not 'one regime'."""
    closes = _series()
    n, detail = regime_coverage(closes, list(range(0, 10)))
    assert n == 0 and detail["status"] == "UNMEASURED"


def test_OUT_OF_RANGE_INDICES_CANNOT_INFLATE_THE_COUNT() -> None:
    closes = _series()
    n, _ = regime_coverage(closes, [5_000, 6_000])
    assert n == 0


def test_THE_DEFINITION_IS_PUBLISHED_WITH_THE_COUNT() -> None:
    """A regime count whose definition is not carried with it is uncheckable six months later,
    and this desk already has one regime definition it must not silently fork."""
    _, detail = regime_coverage(_series())
    assert "crypto_regime.regime_labels" in detail["definition"]
    assert "L1.63" in detail["why"], (
        "a reader must be told this is a COVERAGE COUNT and not a robustness certificate")
