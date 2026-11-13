"""HMM / GARCH / empirical-Bayes as conditioners of many weak members (2026-11-13).

Pinned: empirical-Bayes shrinkage pulls noisy means toward the pooled mean and leaves a
well-separated set alone; the HMM state for day t is built from returns before t; the walk-forward
gross-matches the regime book to the bayes book; the judge Holm-adjusts and marks EARNS only with
a positive CI; the daily cycle runs it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import conditioner_study as C  # noqa: E402


def test_empirical_bayes_shrinks_noise_and_spares_signal() -> None:
    noisy = C.eb_shrink(np.array([0.5, -0.5, 0.1]), np.array([1.0, 1.0, 1.0]))
    assert np.allclose(noisy, noisy.mean())                       # pure noise: all to the pool
    sep = C.eb_shrink(np.array([5.0, -5.0, 0.0]), np.array([1e-4, 1e-4, 1e-4]))
    assert np.allclose(sep, [5.0, -5.0, 0.0], atol=1e-3)          # real spread: kept


def test_the_hmm_state_never_reads_the_day_it_conditions() -> None:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2018-01-01", periods=900, freq="D", tz="UTC")
    r = pd.Series(rng.normal(0, 0.01, 900), index=idx)
    a = C.hmm_high_vol(r)
    r2 = r.copy()
    r2.iloc[700] = 0.5
    b = C.hmm_high_vol(r2)
    assert np.allclose(a.iloc[:701].to_numpy(), b.iloc[:701].to_numpy(), equal_nan=True)


def _book(edge: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(4)
    n = C.MIN_TRAIN_DAYS + 3 * C.TEST_DAYS
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    M = pd.DataFrame({f"S.m{j}": rng.normal(edge if j < 3 else -edge, 0.01, n)
                      for j in range(8)}, index=idx)
    state = pd.DataFrame(0.2, index=idx, columns=M.columns)
    gw = pd.DataFrame(1.0, index=idx, columns=M.columns)
    return M, state, gw


def test_selection_beats_equal_weight_and_the_judge_says_so() -> None:
    M, state, gw = _book(0.002)
    book = C.walk_forward(M, state, gw)
    assert len(book["ew"]) == 3 * C.TEST_DAYS
    out = C.judge(book, reps=200)
    assert out["vs_ew"]["bayes"]["delta_vs_ew_yr"] > 0
    assert out["vs_ew"]["bayes"]["EARNS"] is True
    assert set(out["vs_ew"]) == set(C.TESTED) and out["variants_tested"] == len(C.TESTED)
    hb = book["hmm"].std() / book["bayes"].std()
    assert 0.8 < hb < 1.25                                        # gross-matched, not levered


def test_the_daily_cycle_runs_it() -> None:
    src = (_DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert '("conditioner_study", _conditioner_study)' in src
