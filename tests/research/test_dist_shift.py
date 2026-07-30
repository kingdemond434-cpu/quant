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
