"""Idea 612: never-judged cells supplied vs consumed per hour, and which side binds."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def test_no_prior_reading_is_unmeasured() -> None:
    out = jc.supply_vs_consume(prior_at=None, now=NOW, supplied=0, supplied_judged=0,
                               drained=None, carried=None, backlog=10)
    assert out["status"] == out["binding"] == "UNMEASURED"


def test_a_cell_left_waiting_means_the_judge_binds() -> None:
    out = jc.supply_vs_consume(prior_at=NOW - timedelta(hours=2), now=NOW, supplied=400,
                               supplied_judged=100, drained=300, carried=50, backlog=350)
    assert out["binding"] == "judge"
    assert (out["supplied_per_hour"], out["consumed_per_hour"]) == (200.0, 200.0)
    assert out["consumed_per_day"] == 4800.0


def test_an_empty_carried_cohort_means_intake_binds() -> None:
    out = jc.supply_vs_consume(prior_at=NOW - timedelta(hours=1), now=NOW, supplied=10,
                               supplied_judged=10, drained=5, carried=0, backlog=0)
    assert out["binding"] == "intake" and out["consumed"] == 15


def test_a_reading_under_fifteen_minutes_is_unmeasured() -> None:
    out = jc.supply_vs_consume(prior_at=NOW - timedelta(minutes=5), now=NOW, supplied=1,
                               supplied_judged=0, drained=0, carried=0, backlog=1)
    assert out["status"] == "UNMEASURED"
