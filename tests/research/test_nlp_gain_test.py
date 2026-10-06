"""The admission test: a planted index shows GAIN, a null does not, and a shuffled-date placebo
of the planted index does not either."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research import nlp_gain_test as gt


def _world(n: int = 700, beta: float = 0.004, seed: int = 3) -> tuple[pd.Series, pd.Series]:
    """An AR(1) index and a price whose return from the first close AFTER day d loads on it."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2023-01-02", periods=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + rng.normal()
    r = rng.normal(0.0, 0.006, n)
    r[2:] += beta * x[:-2]           # close d+1 -> d+2 carries index(d): the tradable return
    close = pd.Series(100.0 * np.exp(np.cumsum(r)), index=days)
    return pd.Series(x, index=days), close


def test_a_planted_index_is_admitted_with_gain() -> None:
    idx, close = _world()
    grid = gt.gain_grid({"planted": idx}, {"SYM": close}, [("planted", "SYM")], horizons=(1,),
                        n_placebo=200, n_boot=200, seed=1)
    t = grid["tests"][0]
    assert grid["verdict"] == gt.GAIN and t["gain"] is True
    assert t["ic"] > 0.2 and t["p_placebo"] < 0.01 and t["ci90"][0] > 0


def test_a_null_index_is_not_admitted() -> None:
    _, close = _world()
    rng = np.random.default_rng(99)
    null = pd.Series(rng.normal(size=len(close)), index=close.index)
    grid = gt.gain_grid({"null": null}, {"SYM": close}, [("null", "SYM")], horizons=(1, 5),
                        n_placebo=200, n_boot=200, seed=2)
    assert grid["verdict"] == gt.NO_GAIN and grid["n_trials"] == 2
    assert not any(t["gain"] for t in grid["tests"])


def test_placebo_control_the_planted_index_on_shuffled_dates_shows_nothing() -> None:
    idx, close = _world()
    rng = np.random.default_rng(5)
    shuffled = pd.Series(rng.permutation(idx.to_numpy()), index=idx.index)
    grid = gt.gain_grid({"shuffled": shuffled}, {"SYM": close}, [("shuffled", "SYM")],
                        horizons=(1,), n_placebo=200, n_boot=200, seed=3)
    assert grid["verdict"] == gt.NO_GAIN


def test_the_same_day_return_is_never_the_target() -> None:
    """An index that only 'predicts' the return of its OWN day (knowable only after the close)
    must not be admitted: the aligner starts from the first close after d."""
    rng = np.random.default_rng(11)
    days = pd.bdate_range("2023-01-02", periods=600)
    r = rng.normal(0.0, 0.006, 600)
    close = pd.Series(100.0 * np.exp(np.cumsum(r)), index=days)
    same_day = pd.Series(np.r_[0.0, np.diff(np.log(close.to_numpy()))], index=days)
    grid = gt.gain_grid({"peek": same_day}, {"SYM": close}, [("peek", "SYM")], horizons=(1,),
                        n_placebo=100, n_boot=100, seed=4)
    assert grid["verdict"] == gt.NO_GAIN


def test_short_or_missing_series_are_unmeasured_not_no_gain() -> None:
    idx, close = _world(n=40)
    grid = gt.gain_grid({"short": idx}, {"SYM": close}, [("short", "SYM"), ("absent", "SYM")],
                        horizons=(1,))
    assert grid["verdict"] == gt.UNMEASURED and grid["n_trials"] == 0
    assert {t["state"] for t in grid["tests"]} == {gt.UNMEASURED}


def test_bh_qvalues_are_monotone_in_p_and_never_below_it() -> None:
    p = [0.001, 0.2, 0.01, 0.04, 0.9]
    q = gt.bh_qvalues(p)
    assert all(qi >= pi for qi, pi in zip(q, p, strict=True))
    order = np.argsort(p)
    assert all(q[order[i]] <= q[order[i + 1]] for i in range(len(p) - 1))


def test_index_days_outside_the_bar_history_are_not_paired_with_a_stale_return() -> None:
    idx, close = _world(n=300)
    early = pd.Series(np.arange(200, dtype=float),
                      index=pd.bdate_range("2015-01-01", periods=200))   # years before the bars
    x, _y = gt.align(pd.concat([early, idx]), close, 1)
    assert x.size == len(idx) - 2, "an index day with no nearby close must not be paired"
    const = pd.Series(1.0, index=idx.index)
    row = gt.one_test(const, close, 1)
    assert row["state"] == gt.UNMEASURED and "constant" in row["why"]
