"""R0330: repair capacity -- the service rate behind the queue (L1.28b).

The tests that matter here are the three refusals. Every one of them corresponds to a number the
naive implementation would have published confidently and wrongly, measured on the real ledger
before the producer was written.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.research.repair_capacity import (
    HORIZON_DAYS,
    MIN_EVENTS,
    TERMINAL_STATUSES,
    km_median,
    measure,
    parse_ts,
)

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _row(*, raised_days_ago: float, status: str = "open",
         disposed_days_ago: float | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "raised": (_NOW - timedelta(days=raised_days_ago)).isoformat(),
        "status": status,
        "disposed": None,
    }
    if disposed_days_ago is not None:
        row["disposed"] = (_NOW - timedelta(days=disposed_days_ago)).isoformat()
    return row


# ----------------------------------------------------------------- the censoring trap (trap 1)


def test_km_median_exceeds_the_naive_median_when_censoring_is_interleaved() -> None:
    """THE HEADLINE DEFECT. The naive MTTR conditions on having been disposed, which is the very
    event whose timing it claims to measure.

    THE SHAPE MATTERS, and getting it wrong is how this test first passed for the wrong reason:
    if every fix lands BEFORE any row is censored, KM and the naive median agree exactly, because
    the waiting rows were still at risk when the fixes happened. The bias appears only when rows
    are censored AMONG the fixes -- which is the real ledger's shape, where 197 rows sit waiting at
    ages that interleave with the 263 completions. Three quick fixes, ten rows still waiting at
    4 days, two slow fixes at 10 and 11: the naive median reads 3 days while the censoring-aware
    answer is 10, because the naive figure simply never counts the rows that are still waiting.
    """
    rows: list[dict[str, Any]] = []
    for age in (1, 1, 2, 2, 3, 3):                      # six quick fixes
        rows.append(_row(raised_days_ago=age, status="implemented", disposed_days_ago=0))
    rows += [_row(raised_days_ago=4) for _ in range(6)]  # six still waiting, among the fixes
    for age in (10, 11):                                 # two slow fixes
        rows.append(_row(raised_days_ago=age, status="implemented", disposed_days_ago=0))
    cap = measure(rows, now=_NOW)
    assert cap.n_events == MIN_EVENTS
    assert cap.mttr_naive_days == pytest.approx(3.0)
    assert cap.mttr_days == pytest.approx(10.0)
    assert cap.mttr_days > cap.mttr_naive_days
    assert cap.censored_frac == pytest.approx(6 / 14, abs=1e-4)


def test_km_median_agrees_with_the_naive_one_when_every_fix_precedes_the_waiting() -> None:
    """The estimator must not move the answer where there is nothing to correct: rows censored
    AFTER every completion were still at risk throughout, so they change no denominator."""
    rows = [_row(raised_days_ago=1, status="implemented", disposed_days_ago=0) for _ in range(10)]
    rows += [_row(raised_days_ago=20) for _ in range(10)]
    cap = measure(rows, now=_NOW)
    assert cap.mttr_naive_days == pytest.approx(1.0)
    assert cap.mttr_days == pytest.approx(1.0)
    assert cap.censored_frac == pytest.approx(0.5)


def test_km_median_is_none_rather_than_extrapolated_past_the_last_observation() -> None:
    """NOT-REACHED is a real answer. Inventing a median from rows that have not finished waiting
    would manufacture a figure out of the exact ignorance the statistic exists to expose."""
    obs = [(5.0, 0)] * 10 + [(1.0, 1)]
    assert km_median(obs) is None


def test_km_median_equals_the_plain_median_when_nothing_is_censored() -> None:
    """The censoring-aware estimator must not move the answer when there is no censoring."""
    obs = [(float(i), 1) for i in range(1, 12)]
    assert km_median(obs) == pytest.approx(6.0)


def test_km_median_handles_an_empty_sample_without_inventing_zero() -> None:
    assert km_median([]) is None


# ------------------------------------------------------------------ the idle-day trap (trap 2)


def test_idle_days_do_not_dilute_the_flow_rate() -> None:
    """Four consecutive zero-event days really happened (2026-08-07..08-10). Averaging them in
    scores a quiet stretch as improving capacity, turning a capacity measure into a cadence one."""
    # Two active days, ten days apart: 4 arrivals, no departures.
    rows = [_row(raised_days_ago=12) for _ in range(2)]
    rows += [_row(raised_days_ago=2) for _ in range(2)]
    cap = measure(rows, now=_NOW)
    assert cap.n_active_days == 2
    assert cap.n_idle_days > 0
    # 4 net arrivals over 2 ACTIVE days = 2.0, not 4/13 calendar days = 0.31.
    assert cap.stock_growth_per_active_day == pytest.approx(2.0)


def test_idle_days_are_reported_not_hidden() -> None:
    rows = [_row(raised_days_ago=15), _row(raised_days_ago=0)]
    cap = measure(rows, now=_NOW)
    assert cap.n_idle_days == 14
    assert cap.n_active_days == 2


# ------------------------------------------------------------- fix is not disposition (trap 3)


def test_a_rejection_drains_the_queue_but_is_not_a_fix() -> None:
    """L1.28b(b) makes a reasoned rejection a conversion, and the queue really does drain. But a
    rejection consumes no repair capacity, so flooring the disposition rate would let the desk
    raise the number by rejecting more."""
    rows = [_row(raised_days_ago=20, status="implemented", disposed_days_ago=19)
            for _ in range(5)]
    rows += [_row(raised_days_ago=20, status="rejected", disposed_days_ago=19) for _ in range(5)]
    cap = measure(rows, now=_NOW)
    assert cap.p_fix == pytest.approx(0.5)
    assert cap.p_disposed == pytest.approx(1.0)
    assert cap.p_disposed > cap.p_fix


def test_rows_too_young_for_the_horizon_are_not_counted_as_misses() -> None:
    """Asking of a row raised yesterday whether it was fixed within 14 days is a question that
    cannot yet have an answer; counting it as a miss understates the rate."""
    old = [_row(raised_days_ago=HORIZON_DAYS + 5, status="implemented",
                disposed_days_ago=HORIZON_DAYS + 4) for _ in range(MIN_EVENTS)]
    young = [_row(raised_days_ago=1) for _ in range(50)]
    cap = measure(old + young, now=_NOW)
    assert cap.p_fix == pytest.approx(1.0)


# ---------------------------------------------------------------------------- other refusals


def test_negative_latency_rows_are_excluded_and_counted_not_clamped() -> None:
    """15 real rows are stamped disposed BEFORE raised (legacy backfills whose two stamps came
    from different sources). Averaging them in drags the mean toward zero; clamping to 0 does the
    same thing while looking tidy. The exclusion has to be visible."""
    rows = [_row(raised_days_ago=5, status="done", disposed_days_ago=6) for _ in range(3)]
    rows += [_row(raised_days_ago=10, status="implemented", disposed_days_ago=5)
             for _ in range(MIN_EVENTS)]
    cap = measure(rows, now=_NOW)
    assert cap.n_negative_latency == 3
    assert cap.n_events == MIN_EVENTS
    assert cap.mttr_days is not None and cap.mttr_days > 0


def test_a_thin_sample_refuses_to_publish_a_latency() -> None:
    rows = [_row(raised_days_ago=5, status="implemented", disposed_days_ago=4) for _ in range(3)]
    cap = measure(rows, now=_NOW)
    assert cap.status == "INSUFFICIENT"
    assert cap.mttr_days is None
    assert cap.p_fix is None


def test_an_empty_ledger_is_unmeasured_never_a_clean_board() -> None:
    cap = measure([], now=_NOW)
    assert cap.status == "UNMEASURED"
    assert cap.mttr_days is None
    assert cap.stock_growth_per_active_day is None


def test_rows_without_a_parseable_raised_stamp_are_skipped_not_defaulted() -> None:
    """An invented arrival time would land in the latency distribution as a real observation."""
    rows = [{"raised": "not a date", "status": "open", "disposed": None},
            {"status": "open"},
            _row(raised_days_ago=3)]
    cap = measure(rows, now=_NOW)
    assert cap.n_rows == 1


def test_scheduled_rows_stay_in_the_backlog() -> None:
    """check_conversion counts a scheduled row as still owed; a third definition of 'converted'
    on the same file would let two organs disagree about the same number."""
    assert "scheduled" not in TERMINAL_STATUSES
    rows = [_row(raised_days_ago=10, status="scheduled", disposed_days_ago=9)]
    cap = measure(rows, now=_NOW)
    assert cap.n_censored == 1
    assert cap.n_events == 0


def test_terminal_statuses_agree_with_the_other_two_organs() -> None:
    """Three modules carry this set. A copy is cheaper than importing a 1500-line module for one
    frozenset, but only if drift fails a test rather than passing silently."""
    from libs.research.capability_ratchet import TERMINAL_STATUSES as CAPABILITY_SET
    assert TERMINAL_STATUSES == CAPABILITY_SET
    src = (Path(__file__).resolve().parents[2] / "scripts/check_conversion.py").read_text("utf-8")
    for status in TERMINAL_STATUSES:
        assert f'"{status}"' in src


def test_parse_ts_coerces_naive_stamps_to_utc() -> None:
    assert parse_ts("2026-08-12T00:00:00").tzinfo is not None
    assert parse_ts("") is None
    assert parse_ts(None) is None
    assert parse_ts(12345) is None


# ------------------------------------------------------------------------------ the producer


def test_the_fence_refuses_an_unreadable_ledger(tmp_path: Path) -> None:
    """ABSENT must not resolve to a clean board (L1.55)."""
    from scripts.check_repair_capacity import build_report
    rep = build_report(tmp_path, now=_NOW)
    assert rep["status"] == "UNMEASURED"
    assert rep["n_rows"] == 0


def test_the_fence_publishes_its_denominators(tmp_path: Path) -> None:
    """L1.57: a rate whose denominator the reader cannot see is an opinion."""
    from scripts.check_repair_capacity import build_report
    led = tmp_path / "docs/research"
    led.mkdir(parents=True)
    rows = [_row(raised_days_ago=20, status="implemented", disposed_days_ago=18)
            for _ in range(MIN_EVENTS + 2)]
    (led / "recommendation_ledger.json").write_text(json.dumps({"recommendations": rows}), "utf-8")
    rep = build_report(tmp_path, now=_NOW)
    assert rep["status"] == "MEASURED"
    for key in ("n_rows", "n_events", "n_censored", "n_active_days", "n_idle_days",
                "n_negative_latency", "window_days", "horizon_days"):
        assert key in rep
