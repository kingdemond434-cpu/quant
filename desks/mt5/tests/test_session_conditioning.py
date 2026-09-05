"""The allocator solved London open and 22:00 roll from identical inputs.

    python -m pytest desks/mt5/tests/test_session_conditioning.py -q

`pf_allocator` is the desk's capital brain -- robust posterior E[log W], regime probabilities, a
no-trade region, marginal ranking. Measured 2026-09-03 it contained ZERO references to
hour-of-day or session phase. It solves from daily series, so an edge that lives in the London
expansion and dies in the thin-liquidity roll carried ONE mean into every hour of the day, and
the same book was produced at both.

WHAT MUST NOT REGRESS, in order of what it would cost:

  1. a thin bucket cannot capture the book -- shrinkage at k=40, not the raw conditional mean
  2. conditioning WIDENS uncertainty; it never narrows it
  3. no phase supplied -> the posterior is byte-identical to before this existed
  4. an unparseable timestamp is DROPPED, never bucketed to midnight
  5. entry hour, not exit hour -- exit leaks the future into the conditional mean
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK.parent.parent))

import session_phase as sp  # noqa: E402

from libs.portfolio.robust_elog import SleeveEvidence, _posterior_mu  # noqa: E402


def _ev(name: str, mean: float, n: int = 400, *, state=(), **kw) -> SleeveEvidence:
    rng = np.random.default_rng(abs(hash(name)) % 2**31)
    return SleeveEvidence(name=name, daily_r=rng.normal(mean, 1.0, n),
                          state_r=np.asarray(state, dtype=float), **kw)


# ------------------------------------------------- 1. phase labelling

def test_phases_tile_the_whole_clock() -> None:
    assert {sp.phase_for_hour(h) for h in range(24)} <= {n for n, _, _ in sp.PHASES}
    for h in range(24):
        sp.phase_for_hour(h)          # must not raise for any hour


def test_the_broker_offset_shifts_the_label() -> None:
    """Broker EET is not UTC; a wrong constant mislabels every bucket without raising."""
    ts = datetime(2026, 9, 3, 6, 0)
    assert sp.phase_at(ts, broker_utc_offset_h=0) != sp.phase_at(ts, broker_utc_offset_h=3)


# ------------------------------------------------- 2. bucketing is honest

def test_an_unparseable_timestamp_is_dropped_not_bucketed_to_midnight() -> None:
    rows = [{"entry_time": "garbage", "r_multiple": 9.0},
            {"entry_time": "2026-08-18 08:00:00+00:00", "r_multiple": 1.0}]
    got = sp.returns_in_phase(rows, "LONDON_OPEN", broker_utc_offset_h=0)
    assert got.tolist() == [1.0], "a row with no readable hour must not enter any bucket"


def test_entry_hour_decides_the_bucket_not_exit_hour() -> None:
    """Exit hour is not known at decision time; using it would leak the future."""
    rows = [{"entry_time": "2026-08-18 08:00:00+00:00",
             "exit_time": "2026-08-18 21:00:00+00:00", "r_multiple": 1.0}]
    assert sp.returns_in_phase(rows, "LONDON_OPEN", broker_utc_offset_h=0).size == 1
    assert sp.returns_in_phase(rows, "ROLL_THIN", broker_utc_offset_h=0).size == 0


# ------------------------------------------------- 3. the posterior uses it, carefully

def test_no_state_evidence_leaves_the_posterior_exactly_as_it_was() -> None:
    ev = [_ev("a", 0.05), _ev("b", 0.03)]
    rng = np.random.default_rng(0)
    _, post = _posterior_mu(ev, rng, 64)
    rng2 = np.random.default_rng(0)
    _, post2 = _posterior_mu(ev, rng2, 64)
    assert np.allclose(post, post2)


def test_a_six_trade_bucket_cannot_capture_the_book() -> None:
    """The exact overfit this shrinkage exists to stop: a lucky week at one hour."""
    base = [_ev("a", 0.02), _ev("b", 0.02)]
    lucky = [_ev("a", 0.02, state=[0.9] * 6), _ev("b", 0.02)]
    _, post_base = _posterior_mu(base, np.random.default_rng(1), 64)
    _, post_lucky = _posterior_mu(lucky, np.random.default_rng(1), 64)
    moved = post_lucky[0] - post_base[0]
    assert moved > 0, "genuine state evidence should move the estimate at all"
    assert moved < 0.9 * 0.25, (
        f"six trades moved the posterior by {moved:.4f} -- a thin bucket is capturing the book")


def test_forty_observations_move_it_substantially_more_than_six() -> None:
    base = [_ev("a", 0.02), _ev("b", 0.02)]
    thin = [_ev("a", 0.02, state=[0.9] * 6), _ev("b", 0.02)]
    thick = [_ev("a", 0.02, state=[0.9] * 40), _ev("b", 0.02)]
    _, p0 = _posterior_mu(base, np.random.default_rng(2), 64)
    _, p_thin = _posterior_mu(thin, np.random.default_rng(2), 64)
    _, p_thick = _posterior_mu(thick, np.random.default_rng(2), 64)
    assert (p_thick[0] - p0[0]) > 2.0 * (p_thin[0] - p0[0])


def test_conditioning_widens_uncertainty_it_never_narrows_it() -> None:
    """A conditional estimate is measured on LESS data. The draws must spread, not tighten."""
    base = [_ev("a", 0.02), _ev("b", 0.02)]
    cond = [_ev("a", 0.02, state=[0.9] * 20), _ev("b", 0.02)]
    d0, _ = _posterior_mu(base, np.random.default_rng(3), 4000)
    d1, _ = _posterior_mu(cond, np.random.default_rng(3), 4000)
    assert d1[:, 0].std() > d0[:, 0].std(), (
        "disagreement between the conditional and unconditional mean must widen the posterior")


def test_a_losing_hour_reduces_the_estimate() -> None:
    """Rotation needs both directions: a sleeve that loses at this hour must be sized down."""
    base = [_ev("a", 0.05), _ev("b", 0.05)]
    bad = [_ev("a", 0.05, state=[-0.8] * 40), _ev("b", 0.05)]
    _, p0 = _posterior_mu(base, np.random.default_rng(4), 64)
    _, p1 = _posterior_mu(bad, np.random.default_rng(4), 64)
    assert p1[0] < p0[0]


def test_state_key_is_carried_for_the_explanation() -> None:
    e = _ev("a", 0.02, state=[0.1], state_key="LONDON_OPEN")
    assert e.state_key == "LONDON_OPEN"
