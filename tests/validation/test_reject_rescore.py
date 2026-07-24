"""Tests for the reject re-score planner (near-miss first, eligibility-filtered, capped)."""

from __future__ import annotations

from datetime import timedelta

from libs.core.time import to_iso8601, utcnow
from libs.validation.reject_rescore import plan_rescore


def _ago(days: float) -> str:
    return to_iso8601(utcnow() - timedelta(days=days))


class TestPlanRescore:
    def test_too_young_excluded(self) -> None:
        rejects = [("a", _ago(5), 1.0), ("b", _ago(10), 2.0)]
        plan = plan_rescore(rejects, min_age_days=30)
        assert plan.n_eligible == 0
        assert plan.n_too_young == 2
        assert plan.selected == ()

    def test_near_miss_ranked_first(self) -> None:
        rejects = [
            ("dead", _ago(60), 0.1),
            ("near", _ago(60), 1.9),
            ("mid", _ago(60), 0.8),
        ]
        plan = plan_rescore(rejects, min_age_days=30, limit=10)
        assert plan.selected[0] == "near"  # highest nearness first
        assert plan.selected == ("near", "mid", "dead")

    def test_batch_cap(self) -> None:
        rejects = [(f"c{i}", _ago(60), float(i)) for i in range(100)]
        plan = plan_rescore(rejects, min_age_days=30, limit=10)
        assert len(plan.selected) == 10
        assert plan.n_eligible == 100
        assert plan.n_capped == 90
        assert plan.selected[0] == "c99"  # highest nearness

    def test_deterministic_tie_break(self) -> None:
        rejects = [("b", _ago(60), 1.0), ("a", _ago(60), 1.0)]
        plan = plan_rescore(rejects, min_age_days=30, limit=10)
        assert plan.selected == ("a", "b")  # tie broken by id

    def test_bad_timestamp_skipped(self) -> None:
        rejects = [("bad", "nope", 1.0), ("good", _ago(60), 1.0)]
        plan = plan_rescore(rejects, min_age_days=30)
        assert plan.selected == ("good",)

    def test_empty(self) -> None:
        plan = plan_rescore([], min_age_days=30)
        assert plan.selected == ()
        assert "no eligible" in plan.verdict
