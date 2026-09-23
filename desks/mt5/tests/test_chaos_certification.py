"""Chaos on the certification path: a corrupted tape judged as if it were the tape it names.

test_no_lookahead corrupts the FUTURE and demands the past not change. This corrupts the TAPE
ITSELF -- a random 5% of bars deleted and every remaining stamp moved one hour -- and asks the
one door that grants certificates, `external_gauntlet.run_gauntlet`, what it does with it. The
classes injected here are the two the audit found never injected anywhere on the certification
path: missing bars and a clock error. Both are silent in production: a parquet with a hole in it
and a feed stamped in the wrong zone both LOOK like charts.

MEASURED 2026-09-08 on this tree, on one session_range_breakout cell over 400 synthetic days:

    rows                 9,600 clean  ->  9,120 corrupted
    families.bar_minutes 60           ->  60     (95% of the gaps are still the modal hour)
    families._h1         returned on its own clock, no resample, both tapes
    build_cell           built both (800 signals clean, 766 corrupted)
    cell id              IDENTICAL -- the identity is symbol, family and params; the tape is
                         not part of it
    run_gauntlet         JUDGED both: 361 vs 345 daily observations, in-sample Sharpe
                         -0.1392 vs -0.1369, ten gates evaluated on each, neither UNMEASURED

So the certifier has no reading of tape integrity at all: a corrupted tape produces a numerically
different verdict under the clean cell's name, and nothing between the parquet and the certificate
can tell the two apart. The refusal this should produce is asserted below as a STRICT xfail --
external_gauntlet.py is sealed against this lane, so the gap is recorded here where CI reads it,
and the day a bar-integrity refusal lands the xfail flips to XPASS and fails until someone
promotes it to a real assertion.

`corrupt_tape` is the reusable harness: any test that wants a torn or mis-clocked tape imports it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "scripts"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402
from mt5desk import families  # noqa: E402

N_DAYS = 400
DELETE_FRAC = 0.05
CLOCK_SHIFT = pd.Timedelta("1h")
SYMBOL, FAMILY = "XAUUSD", "session_range_breakout"
#: A gold-shaped contract for the cost model; the cell is synthetic and the number only has to be
#: the same on both tapes.
META = {SYMBOL: {"contract_size": 100.0, "tick_size": 0.01, "median_spread_pts": 16.0,
                 "tick_value": 1.0}}


def synthetic_tape(seed: int = 4, n_bars: int = 24 * N_DAYS) -> pd.DataFrame:
    """A tz-aware hourly random walk with intrabar structure -- test_no_lookahead's fixture,
    long enough for the certifier's 60-observation floor with room to lose 5% of it."""
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.2, n_bars)
    close = 2000.0 + np.cumsum(step)
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.9, n_bars))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.9, n_bars))
    idx = pd.date_range("2024-01-01", periods=n_bars, freq="1h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "spread": rng.integers(10, 40, n_bars).astype(float)}, index=idx)


def corrupt_tape(df: pd.DataFrame, *, seed: int = 7, frac: float = DELETE_FRAC,
                 shift: pd.Timedelta = CLOCK_SHIFT) -> pd.DataFrame:
    """THE HARNESS. Delete a random `frac` of the bars and move every surviving stamp by `shift`.

    Two corruptions in one tape on purpose: a hole alone is caught by nothing on this desk and a
    clock error alone is caught by nothing on this desk, and a real feed fault (a reconnect that
    dropped an hour and came back in the wrong zone) delivers both. The rows kept are chosen by
    seed so the same tape is corrupted the same way on every run.
    """
    rng = np.random.default_rng(seed)
    keep = np.sort(rng.choice(len(df), size=int(len(df) * (1.0 - frac)), replace=False))
    out = df.iloc[keep].copy()
    out.index = out.index + shift
    return out


@pytest.fixture
def corrupted():
    """The harness as a fixture, for tests that want a corrupted copy of their own tape."""
    return corrupt_tape


def judge(bars: pd.DataFrame, label: str) -> dict:
    """One cell, built on `bars` exactly as the hourly sweep builds it, through the ten gates."""
    cell = eg.build_cell(SYMBOL, FAMILY, {}, META, h1_override=bars)
    assert cell is not None, f"{label}: build_cell refused the tape"
    out = eg.run_gauntlet([cell], label, META)
    (verdict,) = out["verdicts"]
    return verdict


@pytest.fixture(scope="module")
def tapes():
    clean = synthetic_tape()
    dirty = corrupt_tape(clean)
    return clean, dirty, judge(clean, "chaos-clean"), judge(dirty, "chaos-corrupted")


def test_the_corruption_is_real_and_every_tape_check_accepts_it(tapes, corrupted) -> None:
    """Five percent of the bars are gone and the clock is an hour out, and the ladder check,
    the normaliser and the cell builder all take the tape as a regular H1 chart."""
    clean, dirty, _, _ = tapes
    assert len(dirty) == int(len(clean) * (1.0 - DELETE_FRAC)) < len(clean)
    assert set(dirty.index - CLOCK_SHIFT) <= set(clean.index)
    assert not set(dirty.index) <= set(clean.index), "the clock was not shifted"
    assert families.bar_minutes(dirty) == families.bar_minutes(clean) == 60
    assert len(families._h1(dirty)) == len(dirty), "the normaliser resampled the torn tape"
    assert corrupted(clean, seed=7).equals(dirty), "the harness is not deterministic"


def test_a_corrupted_tape_is_never_certified(tapes) -> None:
    """The fear named by the audit: a numerically different PASS. Neither tape may pass, and a
    one-cell docket structurally cannot (PBO and SPA fail on fewer than two strategies), so the
    guard here is the direction, pinned where it can be pinned."""
    _, _, v_clean, v_dirty = tapes
    assert v_dirty["passed"] is False and v_clean["passed"] is False
    assert v_dirty["stages"]["pbo"]["passed"] is False


def test_the_judge_judges_the_corrupted_tape_under_the_clean_cells_identity(tapes) -> None:
    """THE MEASURED GAP. Same cell id, different numbers, no refusal: the certifier reads a
    torn, mis-clocked tape as the cell it was asked about and reports ten gates on it."""
    _, _, v_clean, v_dirty = tapes
    assert v_dirty["cell"] == v_clean["cell"]
    assert v_dirty["days"] != v_clean["days"]
    assert (v_dirty["stages"]["in_sample_screen"]["sharpe"]
            != v_clean["stages"]["in_sample_screen"]["sharpe"])
    assert not v_dirty.get("unmeasured") and not v_clean.get("unmeasured")
    assert set(v_dirty["stages"]) == set(v_clean["stages"]), "a gate went missing on one tape"


@pytest.mark.xfail(
    strict=True,
    reason="MEASURED 2026-09-08: external_gauntlet.run_gauntlet has no bar-integrity reading; "
           "a tape with 5% of its bars deleted and its clock shifted 1h is JUDGED (345 daily "
           "observations, ten gates) under the clean cell's id, not refused and not UNMEASURED. "
           "external_gauntlet.py is sealed against this lane; the refusal is recorded here as "
           "owed. Strict: the day it lands, this XPASSes and must become a real assertion.")
def test_a_corrupted_tape_yields_an_unmeasured_or_refused_verdict(tapes) -> None:
    _, _, _, v_dirty = tapes
    assert v_dirty.get("unmeasured") or v_dirty.get("refused"), v_dirty["cell"]
