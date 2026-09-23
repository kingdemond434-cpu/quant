"""Distribution-shift monitor -- must stay quiet on a stationary series, fire on vol and level
moves, never recommend an UPWARD confidence change, and refuse to conclude from one marginal
indicator."""
from __future__ import annotations

import numpy as np

from libs.research.dist_shift import distribution_shift, split_and_check

_RNG = np.random.default_rng(11)


def test_stationary_series_is_stable() -> None:
    a = _RNG.normal(0, 1, 300)
    b = _RNG.normal(0, 1, 300)
    out = distribution_shift(a, b, name="stationary")
    assert out["verdict"] == "STABLE"
    assert out["haircut"] == 0.0
    assert out["action"] == "none"


def test_variance_collapse_is_shift() -> None:
    # Vol compression: every vol-scaled threshold the desk calibrated is now mis-sized.
    out = distribution_shift(_RNG.normal(0, 1, 200), _RNG.normal(0, 0.15, 200), name="vol-collapse")
    assert out["verdict"] == "SHIFT"
    assert out["var_ratio"] < 0.25


def test_level_move_is_shift() -> None:
    out = distribution_shift(_RNG.normal(0, 1, 200), _RNG.normal(4.0, 1, 200), name="level")
    assert out["verdict"] == "SHIFT"
    assert out["level_move_mads"] > 2.5


def test_thin_windows_refuse_to_conclude() -> None:
    out = distribution_shift(_RNG.normal(0, 1, 8), _RNG.normal(9, 1, 8), name="thin")
    assert out["verdict"] == "INSUFFICIENT-DATA"   # a huge apparent move on n=8 concludes nothing
    assert out["haircut"] == 0.0


def test_haircut_is_never_negative_and_bounded() -> None:
    cases = [
        distribution_shift(_RNG.normal(0, 1, 150), _RNG.normal(0, 1, 150), name="a"),
        distribution_shift(_RNG.normal(0, 1, 150), _RNG.normal(0, 0.1, 150), name="b"),
        distribution_shift(_RNG.normal(0, 1, 150), _RNG.normal(3, 2, 150), name="c"),
    ]
    for out in cases:
        assert 0.0 <= out["haircut"] <= 0.5   # downward-only, bounded: never an alpha claim


def test_split_and_check_finds_a_tail_break() -> None:
    body = _RNG.normal(0, 1, 300)
    tail = _RNG.normal(0, 5, 100)
    out = split_and_check(np.concatenate([body, tail]), recent_frac=0.25, name="tail")
    assert out["verdict"] == "SHIFT"


def test_marginal_single_indicator_is_drift_not_shift() -> None:
    # Same spread and level, only a mild shape difference -> flag, do not conclude.
    a = _RNG.normal(0, 1, 400)
    b = np.concatenate([_RNG.normal(-0.45, 1.0, 200), _RNG.normal(0.45, 1.0, 200)])
    out = distribution_shift(a, b, name="shape-only")
    assert out["verdict"] in {"DRIFT", "STABLE"}
    assert out["verdict"] != "SHIFT"


# --- detector 2 (CUSUM) and the agreement rule ---------------------------------------------------

def test_second_detector_is_quiet_on_a_stationary_series_and_the_haircut_stays_zero() -> None:
    # One seeded draw; the RATE on stationary noise is asserted separately below, because a
    # single null draw sits in the 5% tail one time in twenty by construction.
    rng = np.random.default_rng(23)
    out = distribution_shift(rng.normal(0, 1, 300), rng.normal(0, 1, 300), name="stationary")
    assert out["cusum_verdict"] == "STABLE"
    assert out["agreement"] is True and out["agreed_verdict"] == "STABLE"
    assert out["haircut"] == 0.0 and out["cusum_crossed_at"] is None


def test_both_detectors_see_a_level_break_and_the_haircut_is_what_it_was() -> None:
    rng = np.random.default_rng(22)
    out = distribution_shift(rng.normal(0, 1, 200), rng.normal(4.0, 1, 200), name="level")
    assert out["verdict"] == "SHIFT" and out["cusum_verdict"] == "SHIFT"
    assert out["agreement"] is True
    assert out["haircut"] == out["haircut_single_detector"] == 0.35
    assert out["cusum_level"] > out["cusum_h_break"] if "cusum_h_break" in out else True


def test_both_detectors_see_a_vol_collapse() -> None:
    rng = np.random.default_rng(23)
    out = distribution_shift(rng.normal(0, 1, 200), rng.normal(0, 0.15, 200), name="vol")
    assert out["verdict"] == "SHIFT" and out["cusum_verdict"] == "SHIFT"
    assert out["haircut"] == 0.35


def test_haircut_never_exceeds_what_the_single_detector_recommended() -> None:
    """THE DIRECTION OF THE CHANGE. Requiring agreement can only withhold a haircut, never add
    one -- across nulls, drifts, breaks and fat tails alike."""
    rng = np.random.default_rng(24)
    gens = [lambda: rng.normal(0, 1, 80), lambda: rng.normal(0.6, 1, 80),
            lambda: rng.normal(0, 1.6, 80), lambda: rng.standard_t(3, 80),
            lambda: rng.normal(0, 0.5, 80), lambda: rng.normal(2.5, 3, 80)]
    for _ in range(60):
        a, b = gens[0](), gens[int(rng.integers(len(gens)))]()
        out = distribution_shift(a, b, name="x")
        assert 0.0 <= out["haircut"] <= out["haircut_single_detector"] <= 0.5
        table = {"STABLE": 0.0, "DRIFT": 0.15, "SHIFT": 0.35}
        assert out["haircut"] == table[out["agreed_verdict"]]


def test_agreed_verdict_is_the_weaker_reading() -> None:
    from libs.research.dist_shift import agreed_verdict

    assert agreed_verdict("SHIFT", "SHIFT") == "SHIFT"
    assert agreed_verdict("SHIFT", "DRIFT") == "DRIFT"
    assert agreed_verdict("DRIFT", "SHIFT") == "DRIFT"
    assert agreed_verdict("SHIFT", "STABLE") == "STABLE"
    assert agreed_verdict("STABLE", "SHIFT") == "STABLE"
    assert agreed_verdict("DRIFT", "INSUFFICIENT-DATA") == "STABLE"
    assert agreed_verdict("STABLE", "STABLE") == "STABLE"


def test_a_ks_flag_without_cusum_corroboration_withholds_the_haircut() -> None:
    """Constructed disagreement: a recent window whose SHAPE differs (bimodal) but whose level
    and spread match. If the KS side flags, the haircut must wait for the CUSUM."""
    rng = np.random.default_rng(25)
    a = rng.normal(0, 1, 400)
    b = np.concatenate([rng.normal(-0.45, 1.0, 200), rng.normal(0.45, 1.0, 200)])
    out = distribution_shift(a, b, name="shape-only")
    if out["verdict"] != "STABLE" and out["cusum_verdict"] == "STABLE":
        assert out["haircut"] == 0.0
        assert "WITHHELD" in out["action"]
    # Either way the invariant holds.
    assert out["haircut"] <= out["haircut_single_detector"]


def test_cusum_localises_a_late_break_inside_the_recent_window() -> None:
    """A bag comparison says whether; the sequential chart says WHEN. A break that starts at
    observation 120 of the recent window must cross after it, not before."""
    from libs.research.dist_shift import cusum_shift

    rng = np.random.default_rng(26)
    ref = rng.normal(0, 1, 200)
    recent = np.concatenate([rng.normal(0, 1, 120), rng.normal(3.0, 1, 80)])
    out = cusum_shift(ref, recent, name="late")
    assert out["verdict"] == "SHIFT"
    assert out["cusum_crossed_at"] is not None and 120 < out["cusum_crossed_at"] <= 200


def test_cusum_null_alarm_rate_is_bounded_under_fat_tails() -> None:
    """The reason the scale chart reads its constants from the reference: on raw z^2 with
    normal-theory constants, stationary t(3) noise alarmed 72% of the time at n=60. Measured
    5.0% at the DRIFT bar after the fix; the test allows generous slack over that."""
    from libs.research.dist_shift import cusum_shift

    rng = np.random.default_rng(27)
    trials, alarms = 300, 0
    for _ in range(trials):
        out = cusum_shift(rng.standard_t(3, 60), rng.standard_t(3, 60))
        alarms += out["verdict"] != "STABLE"
    assert alarms / trials <= 0.12, f"{alarms}/{trials} stationary t(3) windows alarmed"


def test_insufficient_data_carries_both_detectors_and_no_haircut() -> None:
    out = distribution_shift(np.arange(5.0), np.arange(5.0), name="thin")
    assert out["verdict"] == out["cusum_verdict"] == "INSUFFICIENT-DATA"
    assert out["agreed_verdict"] == "INSUFFICIENT-DATA"
    assert out["haircut"] == 0.0 and out["haircut_single_detector"] == 0.0


def test_a_reference_with_no_spread_cannot_be_standardised_and_says_so() -> None:
    from libs.research.dist_shift import cusum_shift

    out = cusum_shift(np.full(50, 1.0), np.random.default_rng(28).normal(0, 1, 50))
    assert out["verdict"] == "INSUFFICIENT-DATA"
    assert "no spread" in out["detail"]
