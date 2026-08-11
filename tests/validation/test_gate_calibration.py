"""Tests for the gate-calibration audits (rejection-shadow recovery + reconstruction verifier)."""

from __future__ import annotations

from libs.validation.gate_calibration import (
    reconstruction_verified,
    rejection_shadow_audit,
)


class TestRejectionShadowAudit:
    def test_insufficient_sample_never_judges(self) -> None:
        r = rejection_shadow_audit(
            [("a", 2.0), ("b", 3.0)], deploy_threshold=1.0, min_sample=5
        )
        assert r.over_strict is False
        assert "insufficient" in r.verdict

    def test_over_strict_when_many_rejects_would_pay(self) -> None:
        # 4 of 6 decided rejects clear the deploy bar -> gate is leaking survivors.
        rejects = [("a", 2.0), ("b", 1.5), ("c", 1.2), ("d", 1.1), ("e", 0.1), ("f", -0.5)]
        r = rejection_shadow_audit(rejects, deploy_threshold=1.0, leak_tolerance=0.10)
        assert r.over_strict is True
        assert bool(r) is False
        assert r.n_would_have_paid == 4
        assert set(r.would_have_paid) == {"a", "b", "c", "d"}
        assert "OVER-STRICT" in r.verdict

    def test_calibrated_when_few_would_pay(self) -> None:
        rejects = [("a", 0.1), ("b", -0.2), ("c", 0.0), ("d", -0.5), ("e", 0.3), ("f", -0.1)]
        r = rejection_shadow_audit(rejects, deploy_threshold=1.0, leak_tolerance=0.10)
        assert r.over_strict is False
        assert r.n_would_have_paid == 0
        assert "calibrated" in r.verdict

    def test_none_forward_metrics_excluded(self) -> None:
        # Rejects without enough forward data yet do not count toward the sample.
        rejects = [("a", None), ("b", None), ("c", 2.0)]
        r = rejection_shadow_audit(rejects, deploy_threshold=1.0, min_sample=5)
        assert r.n_rejects == 1  # only the decided one
        assert r.over_strict is False

    # --- R0439: the pay bar must be noise-adjusted at the entry's forward sample size -------

    def test_short_window_noise_does_not_fire_over_strict(self) -> None:
        """The live false-fire, reproduced: 25 rejects scored on ~31 forward D1 bars, 8 with
        annualized Sharpes 1.2-4.6 -- all inside the zero-edge noise envelope (SE ~3.4).
        Under the raw 0.5 bar this read 32% leaked and fired; noise-adjusted it must not."""
        sharpes = [4.578, 4.213, 3.406, 1.954, 1.568, 1.347, 1.243, 1.130]
        sharpes += [-0.5 - 0.1 * i for i in range(17)]  # the rest lose money forward
        rejects = [(f"c{i}", s, 31) for i, s in enumerate(sharpes)]
        r = rejection_shadow_audit(rejects, deploy_threshold=0.5, leak_tolerance=0.10)
        assert r.noise_adjusted is True
        assert r.over_strict is False, r.verdict
        # at n=31 the 10%-false-pay bar is ~4.40 annualized -- only the 4.578 can clear it
        assert r.n_would_have_paid <= 1

    def test_powered_window_keeps_full_sensitivity(self) -> None:
        """As n grows the noise bar decays to the raw threshold: a genuinely paying reject
        population at n=4000 must still fire the audit -- the fix must not weld the gate shut."""
        rejects = [(f"c{i}", m, 4000) for i, m in
                   enumerate([2.0, 1.5, 1.2, 1.1, 0.1, -0.5])]
        r = rejection_shadow_audit(rejects, deploy_threshold=1.0, leak_tolerance=0.10)
        assert r.over_strict is True
        assert r.n_would_have_paid == 4

    def test_bit_identical_forward_series_collapse_to_one(self) -> None:
        """Two ids carrying the SAME forward metric to the last digit are one bet (the live
        artifact held two DOGE rejects at 1.2429320833719768) -- the denominator dedupes."""
        rejects = [("doge_a", 1.2429320833719768, 31), ("doge_b", 1.2429320833719768, 31),
                   ("x1", -0.5, 31), ("x2", -0.7, 31), ("x3", -0.9, 31), ("x4", -1.1, 31)]
        r = rejection_shadow_audit(rejects, deploy_threshold=0.5, leak_tolerance=0.10)
        assert r.n_duplicates_collapsed == 1
        assert r.n_rejects == 5

    def test_two_tuple_form_keeps_raw_bar(self) -> None:
        """Callers without a sample size keep the raw-threshold contract unchanged."""
        r = rejection_shadow_audit(
            [(f"c{i}", 0.6 + 0.01 * i) for i in range(6)], deploy_threshold=0.5,
            leak_tolerance=0.10,
        )
        assert r.noise_adjusted is False
        assert r.n_would_have_paid == 6


class TestReconstructionVerified:
    def _matching(self, n: int) -> dict[str, float]:
        return {f"t{i}": float(i) for i in range(n)}

    def test_verified_when_matches_over_enough_overlap(self) -> None:
        gt = self._matching(50)
        recon = dict(gt)
        r = reconstruction_verified(reconstructed=recon, ground_truth=gt, min_overlap=30)
        assert r.verified is True
        assert bool(r) is True
        assert r.n_overlap == 50
        assert r.max_abs_err == 0.0

    def test_rejected_when_overlap_too_small(self) -> None:
        gt = self._matching(10)
        recon = dict(gt)
        r = reconstruction_verified(reconstructed=recon, ground_truth=gt, min_overlap=30)
        assert r.verified is False
        assert "overlap" in r.verdict

    def test_rejected_when_disagrees(self) -> None:
        gt = self._matching(50)
        recon = dict(gt)
        recon["t25"] = gt["t25"] * 2.0  # a large disagreement on one point
        r = reconstruction_verified(
            reconstructed=recon, ground_truth=gt, rel_tol=0.01, min_overlap=30
        )
        assert r.verified is False
        assert "REJECTED" in r.verdict

    def test_within_tolerance_passes(self) -> None:
        gt = {f"t{i}": 100.0 for i in range(40)}
        recon = {f"t{i}": 100.5 for i in range(40)}  # 0.5% off, under 1% tol
        r = reconstruction_verified(
            reconstructed=recon, ground_truth=gt, rel_tol=0.01, min_overlap=30
        )
        assert r.verified is True

    def test_zero_ground_truth_point_exact_match_ok(self) -> None:
        gt = {f"t{i}": 0.0 for i in range(40)}
        recon = {f"t{i}": 0.0 for i in range(40)}
        r = reconstruction_verified(reconstructed=recon, ground_truth=gt, min_overlap=30)
        assert r.verified is True

    def test_only_overlap_counts(self) -> None:
        gt = self._matching(50)
        recon = {**dict(gt), "extra": 999.0}  # extra key not in ground truth is ignored
        r = reconstruction_verified(reconstructed=recon, ground_truth=gt, min_overlap=30)
        assert r.n_overlap == 50
        assert r.verified is True
