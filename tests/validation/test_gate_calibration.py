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
