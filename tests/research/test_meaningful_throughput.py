from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.research.funnel import CASCADE_STAGES, meaningful_research_throughput

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def _candidate(identifier: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": identifier,
        "generated_at": (NOW - timedelta(hours=1)).isoformat(),
        "substantive_changes": ["economic_mechanism"],
        "mechanism_id": identifier,
        "mechanism": identifier,
        "asset": "BTC",
        "research_methodology": "mechanism_first",
        "disposition": "TEST_NOW",
        "automatically_testable": True,
        "stages": {CASCADE_STAGES[0]: True, CASCADE_STAGES[1]: True},
    }
    row.update(updates)
    return row


def test_empty_throughput_is_unmeasured_not_zero_productivity() -> None:
    report = meaningful_research_throughput([], now=NOW)
    assert report["status"] == "UNMEASURED"
    assert report["dominant_bottleneck"] == "MEANINGFUL_GENERATION_UNMEASURED"
    with pytest.raises(ValueError, match="positive"):
        meaningful_research_throughput([], now=NOW, window_hours=0)


def test_daily_ledger_distinguishes_generation_testing_and_survival() -> None:
    completed_stages = dict.fromkeys(CASCADE_STAGES, True)
    candidates = [
        _candidate(
            "survivor",
            test_started_at=NOW.isoformat(),
            test_completed_at=NOW.isoformat(),
            valid_empirical_test=True,
            oos_tested=True,
            survivor=True,
            independent_survivor=True,
            compute_seconds=3600,
            data_loading_seconds=10,
            information_gain=2.0,
            stages=completed_stages,
        ),
        _candidate(
            "blocked",
            disposition="TEST_LATER_WITH_BLOCKER",
            blocker="missing data history",
            automatically_testable=False,
        ),
        _candidate(
            "reject",
            disposition="REJECT_BEFORE_TEST",
            failure_descendants=2,
            infrastructure_failure=True,
        ),
        _candidate("silent", disposition=""),
        _candidate("parameter", substantive_changes=[], pure_parameter_variant=True),
    ]
    report = meaningful_research_throughput(candidates, now=NOW)
    assert report["raw_generated_specifications"] == 5
    assert report["deduplicated_meaningful_candidates"] == 4
    assert report["parameter_variants"] == 1
    assert report["tests_executed"] == 1
    assert report["valid_empirical_tests"] == 1
    assert report["independent_survivors"] == 1
    assert report["survivor_yield_per_1000_meaningful_tests"] == 1000
    assert report["information_gain_per_compute_hour"] == 2
    assert report["failed_candidates_converted_to_hypotheses"] == 2
    assert report["undispositioned_candidates"] == ["silent"]
    assert report["generated_is_not_tested"] is True
    assert report["diversity"]["mechanism"]["effective_categories"] == 4


def test_positive_value_queue_is_the_bottleneck_and_oldest_is_named() -> None:
    older = _candidate(
        "old", generated_at=(NOW - timedelta(hours=12)).isoformat(), disposition="TEST_NOW"
    )
    newer = _candidate("new", disposition="TEST_NOW")
    report = meaningful_research_throughput([older, newer], now=NOW)
    assert report["dominant_bottleneck"] == "TEST_EXECUTION"
    assert report["oldest_valuable_untested_candidate"] == "old"
    assert report["oldest_valuable_untested_age_hours"] == 12


def test_old_rows_are_excluded_from_the_daily_window() -> None:
    old = _candidate("old", generated_at=(NOW - timedelta(days=3)).isoformat())
    current = _candidate("current", participant_behavior="forced seller")
    report = meaningful_research_throughput([old, current], now=NOW, window_hours=24)
    assert report["raw_generated_specifications"] == 1
