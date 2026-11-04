"""Per-member alpha half-life: the fitted decay of a member's daily R (report only)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_half_life as ahl


def _series(edge: np.ndarray, noise: float = 0.0, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=len(edge))
    return pd.Series(edge + noise * rng.standard_normal(len(edge)), index=idx)


def test_a_linearly_fading_edge_reads_decaying_with_its_true_half_life():
    n = 252 * 6
    years = np.arange(n) / 252.0
    edge = 0.002 * (1 - years / 8.0)               # halves at 4 years
    r = ahl.member_half_life(_series(edge, noise=0.0005))
    assert r["verdict"] == "DECAYING"
    assert r["half_life_years"] == pytest.approx(4.0, rel=0.15)
    assert r["retained"] == pytest.approx(1 - 5.75 / 8.0, abs=0.08)


def test_a_flat_edge_reads_stable_and_has_no_half_life():
    r = ahl.member_half_life(_series(np.full(252 * 5, 0.001), noise=0.01, seed=3))
    assert r["verdict"] == "STABLE"


def test_short_or_edgeless_series_are_unmeasured_not_clean():
    assert ahl.member_half_life(_series(np.full(300, 0.001)))["verdict"] == "UNMEASURED"
    neg = ahl.member_half_life(_series(np.full(252 * 4, -0.001), noise=0.0001))
    assert neg["verdict"] == "UNMEASURED" and "start edge" in neg["why"]


def test_pool_summary_counts_every_member():
    n = 252 * 6
    years = np.arange(n) / 252.0
    doc = ahl.pool_half_lives({
        "A": _series(0.002 * (1 - years / 8.0), noise=0.0005),
        "B": _series(np.full(n, 0.001), noise=0.01, seed=1),
        "C": _series(np.full(100, 0.001)),
    })
    assert doc["members"] == 3
    assert sum(doc["verdicts"].values()) == 3
    assert doc["verdicts"]["UNMEASURED"] == 1
    assert doc["median_half_life_years"] is not None
