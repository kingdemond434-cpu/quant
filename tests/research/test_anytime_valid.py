"""THE ANYTIME-VALID GATE -- the sequential test the desk peeks at every day.

ANYTIME_VALID replaces the fixed clock. Its whole value is that it can be peeked at every day on a
growing series without inflating the false-positive rate, which is the one property a p-value does
not have. The tests therefore check the PROPERTY, not the arithmetic: repeated looks at pure noise
must not graduate.

PROVENANCE (2026-09-05). This file was the second half of
``test_funding_clock_and_anytime_valid.py``. Its first half tested ``libs/research/funding_clock``
-- the perpetual-funding settlement clock -- which is deleted with the crypto desk. Every
anytime-valid assertion below is carried over BYTE-FOR-BYTE: nothing was relaxed, no threshold
moved, and the alpha=0.01 bar is the same one it always was.
"""

from __future__ import annotations

import numpy as np

from libs.research import anytime_valid as AV


def _rets(n: int, mean: float, sd: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n)


def test_a_real_edge_graduates() -> None:
    """The positive control. A gate that never graduates anything is indistinguishable from a
    broken gate, and 'nothing survived' from it would mean nothing."""
    out = AV.graduates(_rets(400, 0.004, 0.01, 1))
    assert out["graduates"] is True
    assert out["e_value"] >= out["threshold"]


def test_pure_noise_does_NOT_graduate() -> None:
    assert AV.graduates(_rets(400, 0.0, 0.01, 2))["graduates"] is False


def test_a_LOSING_series_does_not_graduate() -> None:
    assert AV.graduates(_rets(400, -0.003, 0.01, 3))["graduates"] is False


def test_PEEKING_EVERY_DAY_AT_NOISE_does_not_manufacture_a_graduation() -> None:
    """THE WHOLE REASON THIS MODULE EXISTS. A p-value tested daily on a growing series crosses 0.05
    eventually with probability 1. An e-process may be peeked at without inflating the error rate,
    and that property -- not the arithmetic -- is what is asserted here."""
    false_positives = 0
    trials = 12
    for seed in range(trials):
        r = _rets(300, 0.0, 0.01, 100 + seed)
        if any(AV.e_value(r[:t]) >= 1.0 / 0.01 for t in range(AV._MIN_OBS, len(r) + 1, 5)):
            false_positives += 1
    assert false_positives <= 1, (
        f"{false_positives}/{trials} noise series graduated under daily peeking -- the "
        "anytime-validity guarantee is not holding")


def test_too_few_observations_returns_ZERO_evidence_rather_than_a_lucky_number() -> None:
    """Below _MIN_OBS the scale estimate is untrustworthy, and an e-value computed from an
    untrustworthy scale is a number that looks like evidence."""
    assert AV.e_value(_rets(AV._MIN_OBS - 1, 0.01, 0.01, 4)) == 0.0
    assert AV.graduates(_rets(5, 0.05, 0.01, 5))["graduates"] is False


def test_a_CONSTANT_series_yields_no_evidence_rather_than_INFINITE_evidence() -> None:
    """FOUND BY THIS TEST, and it was a promotion path for a dead feed.

    `np.full(200, 0.01).std(ddof=1)` is 1.74e-18, not 0.0 -- the variance is a difference of
    squares and does not cancel exactly -- so an `s <= 0.0` guard passed it straight through. z
    reached 5.75e15 and the e-value came back INFINITE: a series that never moved, certified as
    overwhelming evidence of an edge. A constant return series is exactly what a stuck recorder
    echoing its last value produces, which `data_registry` already scores as a live failure mode.
    """
    assert AV.e_value(np.full(200, 0.01)) == 0.0
    assert AV.graduates(np.full(200, 0.01))["graduates"] is False
    assert AV.e_value(np.zeros(200)) == 0.0


def test_an_overwhelming_edge_returns_a_FINITE_value_rather_than_overflowing() -> None:
    """ALSO FOUND HERE. At 600 observations of a real edge the log-capital exceeds 709 and
    `np.exp` overflows to inf with a RuntimeWarning -- and this repo runs `filterwarnings = error`,
    so the gate RAISED on precisely the candidates it should have passed most confidently."""
    monster = _rets(800, 0.02, 0.005, 12)
    e = AV.e_value(monster)
    assert np.isfinite(e) and e > 1.0 / 0.01
    assert AV.graduates(monster)["graduates"] is True


def test_non_finite_observations_are_dropped_rather_than_poisoning_the_product() -> None:
    """One NaN in a running product makes every subsequent value NaN, and NaN >= threshold is
    False -- so the failure would be silent and permanent."""
    r = _rets(400, 0.004, 0.01, 6)
    r[7] = np.nan
    r[19] = np.inf
    assert AV.e_value(r) > 0.0


def test_the_threshold_is_stricter_than_a_conventional_p_value() -> None:
    """alpha=0.01 rather than 0.05 because this gate can be peeked at daily and the desk's whole
    failure mode is promoting noise."""
    out = AV.graduates(_rets(100, 0.0, 0.01, 7))
    assert out["alpha"] == 0.01 and out["threshold"] == 100.0


def test_evidence_accumulates_monotonically_in_expectation_on_a_real_edge() -> None:
    r = _rets(600, 0.004, 0.01, 8)
    assert AV.e_value(r[:500]) > AV.e_value(r[:100])


def test_days_to_graduation_reports_the_calendar_a_fixed_clock_would_have_wasted() -> None:
    r = _rets(600, 0.005, 0.01, 9)
    t = AV.days_to_graduation(r)
    assert t is not None and AV._MIN_OBS <= t <= len(r)
    assert AV.e_value(r[:t]) >= 100.0
    assert AV.e_value(r[:t - 1]) < 100.0, "it must be the FIRST crossing, not any later one"


def test_days_to_graduation_is_None_when_it_never_crosses() -> None:
    assert AV.days_to_graduation(_rets(300, 0.0, 0.01, 10)) is None


def test_the_verdict_carries_its_own_sample_size() -> None:
    """An e-value with no n attached cannot be argued with -- 4.0 on 25 observations and 4.0 on
    2,500 are different statements about the world."""
    out = AV.graduates(_rets(123, 0.001, 0.01, 11))
    assert out["n"] == 123
