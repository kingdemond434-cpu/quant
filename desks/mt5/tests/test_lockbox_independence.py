"""Gate 9 was gate 7 read twice, and the certificates said so in their own numbers.

    python -m pytest desks/mt5/tests/test_lockbox_independence.py -q

`stages["lockbox"]` passed on `wf_oos >= 0` -- the walk-forward gate's own out-of-sample Sharpe.
A certified survivor therefore printed WF OOS 0.3708 and "lockbox" 0.3708, the identical number,
and the desk counted ten independent hurdles where it had nine. Every certificate issued under
that path overstates its evidence by one gate.

WHAT MUST NOT REGRESS:

  1. the lockbox is carved BEFORE the program matrix, or PBO/SPA have already read it
  2. every cell holds out the SAME calendar dates (same-ruler law)
  3. the lockbox statistic is not the walk-forward statistic
  4. too short to reserve anything -> the gate FAILS; absence of evidence is not permission
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK.parent.parent))

import universal_gate as ug  # noqa: E402


def _series(start: str, n: int, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="D")
    return pd.Series(rng.normal(0.02, 1.0, n), index=idx)


# ------------------------------------------------- 1. the cut is one shared calendar date

def test_the_cut_is_a_single_date_shared_by_every_cell() -> None:
    """A per-series fraction would hold out different periods per cell and break comparability."""
    a = _series("2024-01-01", 400, 1)
    b = _series("2024-03-01", 400, 2)          # different start, different length of overlap
    cut = ug._lockbox_cut([a, b])
    assert cut is not None
    # the same instant partitions both
    assert len(a[a.index < cut]) + len(a[a.index >= cut]) == len(a)
    assert len(b[b.index < cut]) + len(b[b.index >= cut]) == len(b)


def test_the_cut_reserves_the_final_fraction_of_the_union_calendar() -> None:
    s = _series("2024-01-01", 500, 3)
    cut = ug._lockbox_cut([s])
    held = s[s.index >= cut]
    assert ug.LOCKBOX_MIN_DAYS <= len(held)
    assert abs(len(held) / len(s) - ug.LOCKBOX_FRAC) < 0.03


def test_a_campaign_too_short_reserves_nothing_rather_than_a_token_slice() -> None:
    assert ug._lockbox_cut([_series("2024-01-01", 50, 4)]) is None
    assert ug._lockbox_cut([]) is None


# ------------------------------------------------- 2. the gate no longer echoes walk-forward

def _verdict(dev: np.ndarray, lock: np.ndarray) -> dict:
    return ug._ug_verdict((
        "cell1", "EURUSD", dev, dev, lock,
        True, 0.1, True, 0.01, 10, 0.25,
    ))


def test_the_lockbox_statistic_is_not_the_walk_forward_statistic() -> None:
    """The defect in one assertion: a held-out slice with the OPPOSITE sign must disagree."""
    rng = np.random.default_rng(11)
    dev = rng.normal(0.15, 1.0, 400)            # profitable development window
    lock = rng.normal(-0.60, 1.0, 120)          # held-out window that lost money
    v = _verdict(dev, lock)
    st = v["stages"]
    assert st["lockbox"]["lockbox_sharpe"] != st["walk_forward"]["oos_sharpe"], (
        "the lockbox is echoing walk-forward again")
    assert st["lockbox"]["passed"] is False, "a losing held-out window must fail the gate"


def test_a_profitable_held_out_window_passes_on_its_own_evidence() -> None:
    rng = np.random.default_rng(12)
    v = _verdict(rng.normal(0.15, 1.0, 400), rng.normal(0.20, 1.0, 120))
    assert v["stages"]["lockbox"]["passed"] is True
    assert v["stages"]["lockbox"]["n_days"] == 120


def test_no_held_out_data_fails_closed() -> None:
    """The campaign was too short to reserve anything -- that is not a pass."""
    rng = np.random.default_rng(13)
    v = _verdict(rng.normal(0.15, 1.0, 400), np.array([]))
    lb = v["stages"]["lockbox"]
    assert lb["passed"] is False
    assert lb["lockbox_sharpe"] is None
    assert "no lockbox evidence" in lb["why"]


def test_a_slice_under_the_floor_fails_rather_than_measuring_noise() -> None:
    rng = np.random.default_rng(14)
    v = _verdict(rng.normal(0.15, 1.0, 400), rng.normal(5.0, 0.1, ug.LOCKBOX_MIN_DAYS - 1))
    assert v["stages"]["lockbox"]["passed"] is False, (
        "a tiny window with a flattering mean must not buy the tenth gate")


def test_ten_gates_are_still_all_reported() -> None:
    rng = np.random.default_rng(15)
    v = _verdict(rng.normal(0.15, 1.0, 400), rng.normal(0.20, 1.0, 120))
    assert set(v["stages"]) == set(ug.GATES), "the gate list must stay exactly the ten"
