"""Tests for the extraction-parity reconciliation (coverage-not-volume, earned expansion,
effective trial count)."""

from __future__ import annotations

from libs.autodiscovery.extraction_parity import (
    axis_coverage,
    effective_trial_count,
    expansion_licensed,
)


class TestAxisCoverage:
    def test_paralysis_clears_on_coverage_not_volume(self) -> None:
        # Every ingested axis has >=1 screened hypothesis -> cleared, regardless of how few.
        r = axis_coverage(axes=["cn_premium", "onchain", "dev"], screened_axes=["cn_premium",
                          "onchain", "dev"])
        assert r.cleared is True
        assert bool(r) is True
        assert r.idle == ()
        assert r.coverage_frac == 1.0

    def test_volume_on_one_axis_does_not_clear_paralysis(self) -> None:
        # 100 hypotheses on ONE axis leaves the other two idle -> still not cleared.
        r = axis_coverage(
            axes=["cn_premium", "onchain", "dev"],
            screened_axes=["cn_premium"] * 100,
        )
        assert r.cleared is False
        assert set(r.idle) == {"onchain", "dev"}
        assert r.n_covered == 1
        assert "MECHANISM-FIRST" in r.verdict

    def test_idle_axes_listed(self) -> None:
        r = axis_coverage(axes=["a", "b", "c", "d"], screened_axes=["a"])
        assert set(r.idle) == {"b", "c", "d"}
        assert r.coverage_frac == 0.25

    def test_no_axes(self) -> None:
        r = axis_coverage(axes=[], screened_axes=[])
        assert r.cleared is True
        assert r.n_axes == 0

    def test_screened_axis_not_in_universe_ignored(self) -> None:
        # A hypothesis screening an axis we don't actually ingest covers nothing.
        r = axis_coverage(axes=["a", "b"], screened_axes=["a", "ghost"])
        assert set(r.idle) == {"b"}
        assert r.n_covered == 1

    def test_dedup_axes(self) -> None:
        r = axis_coverage(axes=["a", "a", "b"], screened_axes=["a", "b"])
        assert r.n_axes == 2
        assert r.cleared is True


class TestExpansionLicensed:
    def test_unscreened_not_licensed(self) -> None:
        d = expansion_licensed(axis="dev", screened=False, screen_metric=None, threshold=0.02)
        assert d.licensed is False
        assert "unscreened" in d.reason

    def test_screened_flat_not_licensed(self) -> None:
        d = expansion_licensed(axis="dev", screened=True, screen_metric=0.005, threshold=0.02)
        assert d.licensed is False
        assert bool(d) is False
        assert "DSR deflation" in d.reason

    def test_screened_with_signal_licensed(self) -> None:
        d = expansion_licensed(axis="dev", screened=True, screen_metric=0.05, threshold=0.02)
        assert d.licensed is True
        assert bool(d) is True
        assert "earned" in d.reason

    def test_negative_metric_uses_magnitude(self) -> None:
        # A strong negative IC is still signal.
        d = expansion_licensed(axis="dev", screened=True, screen_metric=-0.05, threshold=0.02)
        assert d.licensed is True

    def test_none_metric_even_if_screened_flag_true(self) -> None:
        d = expansion_licensed(axis="dev", screened=True, screen_metric=None, threshold=0.02)
        assert d.licensed is False


class TestEffectiveTrialCount:
    def test_distinct_mechanisms_are_independent_trials(self) -> None:
        r = effective_trial_count(["funding", "carry", "momentum"])
        assert r.raw == 3
        assert r.effective == 3
        assert r.inflation == 1.0

    def test_variations_of_one_mechanism_collapse(self) -> None:
        # 200 variants of one mechanism == ~1 independent trial, not 200.
        r = effective_trial_count(["funding"] * 200)
        assert r.raw == 200
        assert r.effective == 1
        assert r.inflation == 200.0
        assert "unclearable" in r.verdict

    def test_mixed(self) -> None:
        mechs = ["funding"] * 10 + ["carry"] * 5 + ["momentum"] * 5
        r = effective_trial_count(mechs)
        assert r.raw == 20
        assert r.effective == 3
        assert r.top_clusters[0] == ("funding", 10)

    def test_empty(self) -> None:
        r = effective_trial_count([])
        assert r.raw == 0
        assert r.effective == 0
        assert r.inflation == 0.0

    def test_blank_mechanisms_ignored(self) -> None:
        r = effective_trial_count(["funding", "", "carry"])
        assert r.effective == 2
