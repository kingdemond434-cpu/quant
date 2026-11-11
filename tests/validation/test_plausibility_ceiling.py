"""The plausibility ceiling: a too-good-to-be-true series is refused as SUSPECT_LEAK."""
from __future__ import annotations

import numpy as np

from libs.validation.plausibility import MAX_ANNUAL_SHARPE, plausibility_stage


def test_an_ordinary_weak_edge_passes() -> None:
    rng = np.random.default_rng(7)
    r = rng.normal(0.03, 1.0, 750)  # ~0.5 annual Sharpe: what real cells look like
    st = plausibility_stage(r)
    assert st["passed"] is True and st["verdict"] == "PLAUSIBLE"


def test_a_leaked_series_is_refused() -> None:
    rng = np.random.default_rng(7)
    r = np.abs(rng.normal(0.5, 0.2, 500))  # wins nearly every day: reads the future
    st = plausibility_stage(r)
    assert st["passed"] is False and st["verdict"] == "SUSPECT_LEAK"
    assert st["annual_sharpe"] > MAX_ANNUAL_SHARPE


def test_win_share_alone_trips_even_below_the_sharpe_ceiling() -> None:
    r = np.array([0.1] * 97 + [-3.0] * 3 + [0.0] * 50)
    st = plausibility_stage(r)
    assert st["annual_sharpe"] < MAX_ANNUAL_SHARPE
    assert st["passed"] is False and "winning days" in st["why"]


def test_empty_and_flat_series_do_not_crash() -> None:
    assert plausibility_stage([])["passed"] is True
    assert plausibility_stage([0.0] * 100)["passed"] is True
