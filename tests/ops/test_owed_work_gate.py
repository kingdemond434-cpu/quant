"""The firing gate: when a queue-drainer session is worth its cost, and when it is not.

The two tests that matter most are the ones protecting ROI rather than cost -- the age floor (a
lone row must not rot behind a batch that never fills) and the fail-open (a gate that dies on a
malformed artifact must not silently stop the drainer). A cost gate that can starve the queue is
worse than no gate at all.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.owed_work_gate import (
    DEFAULT_BATCH,
    MAX_ROW_AGE_H,
    decide,
    gate_from_repo,
)


def _d(**kw):
    base = {"n_open": 0, "oldest_age_h": 0.0, "n_live_defects": 0}
    return decide(**{**base, **kw})


# ------------------------------------------------------------------ the three reasons to spend
def test_full_batch_fires() -> None:
    v = _d(n_open=DEFAULT_BATCH, oldest_age_h=0.1)
    assert v.fire and "FULL BATCH" in v.reason


def test_age_floor_fires_for_a_single_stale_row() -> None:
    """THE ROI GUARD. Without this a lone row waits forever for a batch that never fills."""
    v = _d(n_open=1, oldest_age_h=MAX_ROW_AGE_H + 0.1)
    assert v.fire and "AGE FLOOR" in v.reason


def test_live_defect_fires_regardless_of_batch_or_age() -> None:
    v = _d(n_open=0, oldest_age_h=0.0, n_live_defects=1)
    assert v.fire and "LIVE DEFECT" in v.reason


# ------------------------------------------------------------------ and the hold
def test_shallow_fresh_queue_holds_and_says_what_would_flip_it() -> None:
    v = _d(n_open=3, oldest_age_h=2.0)
    assert not v.fire
    assert "5 more row(s)" in v.reason and "18.0h" in v.reason


def test_empty_queue_holds() -> None:
    assert not _d(n_open=0).fire


def test_hold_never_drops_a_row_it_only_defers() -> None:
    """The gate reports the rows it is holding, so a hold can never be mistaken for a drain."""
    v = _d(n_open=3, oldest_age_h=2.0)
    assert v.n_open == 3


# ------------------------------------------------------------------ fail-open, never fail-silent
def test_unreadable_ledger_fires_rather_than_stalling(tmp_path: Path) -> None:
    v = gate_from_repo(tmp_path)
    assert v.fire and "unreadable" in v.reason


def test_row_with_no_timestamp_is_treated_as_old_not_new(tmp_path: Path) -> None:
    """L1.41: unknown is not zero. An unparseable date must not let a row hide below the floor."""
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / "docs/research/recommendation_ledger.json").write_text(json.dumps(
        {"recommendations": [{"id": "R1", "status": "open", "raised": "not-a-date"}]}), "utf-8")
    v = gate_from_repo(tmp_path)
    assert v.fire and "AGE FLOOR" in v.reason


def test_naive_timestamps_are_treated_as_utc_not_crashed_on(tmp_path: Path) -> None:
    (tmp_path / "docs/research").mkdir(parents=True)
    fresh = (datetime.now(tz=UTC) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    (tmp_path / "docs/research/recommendation_ledger.json").write_text(json.dumps(
        {"recommendations": [{"id": "R1", "status": "open", "raised": fresh}]}), "utf-8")
    v = gate_from_repo(tmp_path)
    assert not v.fire and 0.5 < v.oldest_age_h < 2.0


# ------------------------------------------------------------------ the saving, stated
def test_steady_state_holds_far_more_often_than_it_fires() -> None:
    """THE WHOLE POINT, simulated honestly over a week rather than asserted.

    At the measured ~5 rows/day refill and batch 8, hourly ticks supply 192 row-slots/day against
    5 arriving. A correct gate fires only when a batch fills or the age floor bites, and DRAINS on
    each fire -- so the simulation must reset the queue when it spends, or it double-counts one
    trigger as four.
    """
    per_hour = 5 / 24
    pending = 0.0
    oldest = 0.0
    fires = 0
    for _ in range(24 * 7):                      # one week of hourly ticks
        pending += per_hour
        oldest = oldest + 1.0 if pending >= 1 else 0.0
        v = decide(n_open=int(pending), oldest_age_h=oldest, n_live_defects=0)
        if v.fire:
            fires += 1
            pending = max(0.0, pending - DEFAULT_BATCH)
            oldest = 0.0
    assert fires <= 12, f"{fires} fires in 168 ticks -- the gate is not saving sessions"
    assert fires >= 5, f"only {fires} fires in a week -- the age floor is not protecting latency"
