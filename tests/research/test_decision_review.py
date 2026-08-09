"""Decision-ledger maturity. The load-bearing property is what this module REFUSES to do:
derive dates, never outcomes. A calibration ledger of machine-guessed outcomes is worse than an
empty one, because the Brier score then reports confidently on judgement that was never tested."""

from __future__ import annotations

from datetime import date

from libs.research.decision_review import (
    DEFAULT_HORIZON_D,
    backfill_plan,
    confidence_profile,
    decision_date,
    health,
    is_scored,
    review_for,
    stated_horizon_days,
)

TODAY = date(2026, 7, 26)


def _row(rid: str = "2026-07-01-thing", **kw) -> dict:
    return {"id": rid, "decision": "d", "hypothesis": "h", "confidence": 0.8,
            "success_metric": "it works", **kw}


class TestHorizonParsing:
    def test_no_horizon_stated(self) -> None:
        assert stated_horizon_days("funding rises without drift") is None

    def test_day_form(self) -> None:
        assert stated_horizon_days("by day 90: sim vs real comparison") == 90

    def test_days_weeks_months(self) -> None:
        assert stated_horizon_days("holds for 14d") == 14
        assert stated_horizon_days("stable over 6 weeks") == 42
        assert stated_horizon_days("2 months of clean runs") == 60

    def test_the_LONGEST_horizon_wins(self) -> None:
        """A metric reading 'rises within 7d and holds 90d' is not settled at day 7. Taking the
        first match would score decisions early and systematically flatter the desk, because the
        early reading is the one taken while the change is still fresh."""
        assert stated_horizon_days("rises within 7d and holds 90d") == 90

    def test_absurd_numbers_are_ignored(self) -> None:
        assert stated_horizon_days("target 10000 days") is None
        assert stated_horizon_days("0 days") is None


class TestScoredDetection:
    def test_a_real_outcome_counts(self) -> None:
        assert is_scored({"outcome": "SHIPPED + verified: molded +114"})

    def test_a_placeholder_does_not_count(self) -> None:
        """'pending' in the outcome field is an intention, not a score. Counting it would let
        the ledger report progress it has not made."""
        for v in ("pending", "TBD", "", "  ", "n/a", "-", "open"):
            assert not is_scored({"outcome": v}), v

    def test_a_missing_field_does_not_count(self) -> None:
        assert not is_scored({})


class TestClassification:
    def test_an_undated_decision_gets_the_default_horizon(self) -> None:
        r = review_for(_row("2026-07-01-x"), TODAY)
        assert r.source == "default" and r.horizon_d == DEFAULT_HORIZON_D
        assert r.due == date(2026, 7, 31) and r.state == "maturing"

    def test_a_matured_unscored_decision_is_due(self) -> None:
        r = review_for(_row("2026-06-01-x"), TODAY)
        assert r.state == "due" and r.days_overdue == 25 and r.actionable

    def test_a_scored_decision_is_never_due(self) -> None:
        r = review_for(_row("2026-06-01-x", outcome="correct: it held"), TODAY)
        assert r.state == "scored" and not r.actionable

    def test_an_explicit_date_beats_the_derivation(self) -> None:
        r = review_for(_row("2026-07-01-x", review_due="2026-12-01"), TODAY)
        assert r.source == "explicit" and r.due == date(2026, 12, 1)

    def test_a_stated_horizon_beats_the_default(self) -> None:
        r = review_for(_row("2026-07-01-x", success_metric="by day 90: compare"), TODAY)
        assert r.source == "success_metric" and r.horizon_d == 90

    def test_an_unparseable_id_with_no_date_is_undatable_not_due(self) -> None:
        """Reported honestly rather than defaulted to today -- silently making it due would put
        a row on the worklist that no derivation can actually justify."""
        r = review_for({"id": "no-date-here"}, TODAY)
        assert r.state == "undatable" and r.due is None

    def test_a_malformed_explicit_date_falls_back_to_derivation(self) -> None:
        r = review_for(_row("2026-07-01-x", review_due="not-a-date"), TODAY)
        assert r.due == date(2026, 7, 31)

    def test_decision_date_reads_the_id_prefix(self) -> None:
        assert decision_date({"id": "2026-07-04-cashcarry"}) == date(2026, 7, 4)
        assert decision_date({"id": "2026-13-99-bad"}) is None


class TestBackfillNeverOverwritesAHumanDate:
    def test_only_undated_rows_are_planned(self) -> None:
        rows = [_row("2026-07-01-a"), _row("2026-07-01-b", review_due="2026-09-09")]
        plan = backfill_plan(rows, TODAY)
        assert [p[0] for p in plan] == ["2026-07-01-a"]

    def test_the_plan_carries_its_provenance(self) -> None:
        plan = backfill_plan([_row("2026-07-01-a", success_metric="by day 45")], TODAY)
        assert plan[0][2] == "success_metric"

    def test_backfill_is_idempotent(self) -> None:
        rows = [_row("2026-07-01-a")]
        _rid, iso, _src = backfill_plan(rows, TODAY)[0]
        rows[0]["review_due"] = iso
        assert backfill_plan(rows, TODAY) == []


class TestHealth:
    def test_the_missing_date_verdict_leads(self) -> None:
        """175 undated rows was the whole reason the queue was empty, so that fact outranks the
        due count in the verdict -- fixing the dates is what makes the due count meaningful."""
        h = health([_row(f"2026-07-0{i}-x") for i in range(1, 5)], TODAY)
        assert h.no_review_date == 4 and "never come due" in h.verdict

    def test_a_dated_backlog_reports_the_due_count(self) -> None:
        rows = [_row("2026-06-01-a", review_due="2026-06-30"),
                _row("2026-06-01-b", review_due="2026-06-30", outcome="wrong: assumption 2")]
        h = health(rows, TODAY)
        assert h.due == 1 and h.scored == 1 and "matured and unscored" in h.verdict

    def test_a_clean_queue_says_so(self) -> None:
        rows = [_row("2026-07-20-a", review_due="2026-12-01")]
        assert "still maturing" in health(rows, TODAY).verdict


class TestConfidenceProfile:
    def test_it_surfaces_the_modal_anchor(self) -> None:
        rows = [_row(confidence=0.8) for _ in range(9)] + [_row(confidence=0.3)]
        p = confidence_profile(rows)
        assert p["modal_bucket"] == "0.8" and p["modal_share_pct"] == 90.0

    def test_an_empty_ledger_does_not_raise(self) -> None:
        assert confidence_profile([])["n"] == 0
