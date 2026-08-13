"""Tests for the rejection-shadow orchestration (audit layer over the reject ledger)."""

from __future__ import annotations

from datetime import timedelta

from libs.core.time import to_iso8601, utcnow
from libs.validation.rejection_shadow import build_shadow_report


def _iso_days_ago(days: float) -> str:
    return to_iso8601(utcnow() - timedelta(days=days))


class TestBuildShadowReport:
    def test_young_rejects_are_not_eligible(self) -> None:
        # rejected 5 days ago, min age 30 -> too young to judge
        rejects = [("c1", _iso_days_ago(5)), ("c2", _iso_days_ago(10))]
        r = build_shadow_report(rejects, {}, deploy_threshold=0.5, min_age_days=30)
        assert r.n_rejects_total == 2
        assert r.n_eligible == 0
        assert r.audit.over_strict is False

    def test_eligible_unscored_reports_pending(self) -> None:
        rejects = [(f"c{i}", _iso_days_ago(60)) for i in range(6)]
        r = build_shadow_report(rejects, {}, deploy_threshold=0.5, min_age_days=30)
        assert r.n_eligible == 6
        assert r.n_pending_rescore == 6
        assert "NONE re-scored" in r.verdict

    def test_over_strict_when_scored_rejects_would_pay(self) -> None:
        rejects = [(f"c{i}", _iso_days_ago(60)) for i in range(6)]
        # 4 of 6 would clear the 0.5 deploy bar out-of-sample -> gate leaking
        scores = {"c0": 1.2, "c1": 0.9, "c2": 0.7, "c3": 0.6, "c4": 0.0, "c5": -0.3}
        r = build_shadow_report(rejects, scores, deploy_threshold=0.5, min_age_days=30)
        assert r.n_pending_rescore == 0
        assert r.audit.over_strict is True
        assert bool(r) is False
        assert r.audit.n_would_have_paid == 4

    def test_calibrated_when_few_would_pay(self) -> None:
        rejects = [(f"c{i}", _iso_days_ago(60)) for i in range(6)]
        scores = {f"c{i}": -0.2 for i in range(6)}
        r = build_shadow_report(rejects, scores, deploy_threshold=0.5, min_age_days=30)
        assert r.audit.over_strict is False
        assert r.audit.n_would_have_paid == 0

    def test_partial_scoring_reports_remaining_pending(self) -> None:
        rejects = [(f"c{i}", _iso_days_ago(60)) for i in range(6)]
        scores = {"c0": 0.1, "c1": 0.2}  # only 2 of 6 scored
        r = build_shadow_report(rejects, scores, deploy_threshold=0.5, min_age_days=30)
        assert r.n_pending_rescore == 4
        assert "awaiting a forward score" in r.verdict

    def test_bad_timestamp_skipped(self) -> None:
        rejects = [("c1", "not-a-date"), ("c2", _iso_days_ago(60))]
        r = build_shadow_report(rejects, {"c2": 0.1}, deploy_threshold=0.5, min_age_days=30)
        assert r.n_eligible == 1  # the bad one is skipped, not crashed

    def test_dict_scores_carry_their_sample_size_to_the_noise_bar(self) -> None:
        """The rescorer's {"sharpe", "n_fwd_bars"} form judges at the noise-adjusted bar: a
        31-bar annualized Sharpe of 1.2 is inside the zero-edge envelope and must not read as
        a leaked survivor, while the same Sharpe at n=4000 must."""
        rejects = [(f"c{i}", _iso_days_ago(60)) for i in range(6)]
        short = {f"c{i}": {"sharpe": 1.2 + 0.01 * i, "n_fwd_bars": 31} for i in range(6)}
        r = build_shadow_report(rejects, short, deploy_threshold=0.5, min_age_days=30)
        assert r.audit.noise_adjusted is True
        assert r.audit.n_would_have_paid == 0
        assert r.audit.over_strict is False
        powered = {f"c{i}": {"sharpe": 1.2 + 0.01 * i, "n_fwd_bars": 4000} for i in range(6)}
        r2 = build_shadow_report(rejects, powered, deploy_threshold=0.5, min_age_days=30)
        assert r2.audit.n_would_have_paid == 6
        assert r2.audit.over_strict is True

    def test_unreadable_dict_score_counts_as_pending_not_paid(self) -> None:
        rejects = [("c1", _iso_days_ago(60))]
        r = build_shadow_report(rejects, {"c1": {"wrong_key": 1.0}},
                                deploy_threshold=0.5, min_age_days=30)
        assert r.n_pending_rescore == 1
        assert r.audit.n_rejects == 0
