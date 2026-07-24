"""Regression guards for the max_audit reconciliation checks (charter §31 coverage-not-volume,
§32 depth-breadth parity). These are standing laws -- lock their monitor behavior."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.max_audit as m


def _mk(tmp: Path) -> None:
    (tmp / "data/lake/bronze").mkdir(parents=True)
    (tmp / "reports/reconstructed_oos").mkdir(parents=True)
    (tmp / "web").mkdir(parents=True)


class TestDepthParity:
    def test_flags_shallow_unbackfilled_axes(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/kimchi_premium.jsonl").write_text("\n".join(["{}"] * 30))
        (tmp_path / "data/cny_premium.jsonl").write_text("\n".join(["{}"] * 40))
        (tmp_path / "data/stablecoin_supply.jsonl").write_text("\n".join(["{}"] * 200))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        assert defects and defects[0][0] == "depth-parity"
        msg = defects[0][1]
        assert "kimchi_premium(30d)" in msg and "cny_premium(40d)" in msg
        assert "stablecoin_supply" not in msg  # deep -> exempt
        assert "§32" in msg

    def test_backfilled_axis_is_exempt(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/onchain_activity.jsonl").write_text("\n".join(["{}"] * 20))
        (tmp_path / "data/kimchi_premium.jsonl").write_text("\n".join(["{}"] * 20))
        (tmp_path / "data/cny_premium.jsonl").write_text("\n".join(["{}"] * 20))
        # onchain has a reconstructed-OOS report -> backfilled -> deep -> exempt
        (tmp_path / "reports/reconstructed_oos/onchain_activity.json").write_text("{}")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        msg = defects[0][1] if defects else ""
        assert "onchain_activity" not in msg  # backfilled -> not flagged

    def test_too_few_clocks_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "data/kimchi_premium.jsonl").write_text("{}")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_depth_parity(defects)
        assert defects == []  # < 3 clocks -> not enough to judge


class TestDataUtilizationCoverage:
    def test_fires_on_idle_axes_with_coverage_not_volume_remedy(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _mk(tmp_path)
        for a in ["cny_premium", "onchain_activity", "dev_factor", "npm_downloads",
                  "pypi_downloads", "funding_skew", "basis_term", "options_flow", "social_vel"]:
            (tmp_path / "data/lake/bronze" / a).mkdir()
        # only 3 converted via a forward-shadow registry
        (tmp_path / "web/axis_shadows.json").write_text(json.dumps({"axes": [
            {"axis": "cny_premium"}, {"axis": "onchain_activity"}, {"axis": "dev_factor"}]}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_data_utilization(defects)
        assert defects and defects[0][0] == "data-utilization-paralysis"
        msg = defects[0][1]
        assert "MECHANISM-FIRST" in msg and "Do NOT clear this by" in msg
        # the old volume-machine remedy must never come back
        assert "combinatorial/mutation/forced-mechanism generation" not in msg

    def test_converted_axes_credit_all_three_sources(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/axis_shadows.json").write_text(json.dumps(
            {"axes": [{"axis": "kimchi_premium"}]}))
        (tmp_path / "reports/reconstructed_oos/onchain_throughput.json").write_text(
            json.dumps({"results": [{"sleeve": "onchain_activity"}]}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        conv = m._converted_axes()
        assert "kimchi_premium" in conv  # forward shadow
        assert "onchain_activity" in conv  # OOS sleeve
        assert "onchain_throughput" in conv  # OOS report stem


class TestRejectionShadowCheck:
    def test_flags_over_strict_gate(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 6, "n_pending_rescore": 0,
            "audit": {"over_strict": True, "n_rejects": 6, "n_would_have_paid": 4,
                      "leak_frac": 0.667}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        ids = [d[0] for d in defects]
        assert "rejection-shadow-overstrict" in ids
        assert "leaking survivors" in dict(defects)["rejection-shadow-overstrict"]

    def test_flags_unscored_backlog(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 8, "n_pending_rescore": 8,
            "audit": {"over_strict": False}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert "rejection-shadow-unscored" in [d[0] for d in defects]

    def test_no_report_no_op(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert defects == []

    def test_calibrated_gate_no_defect(self, tmp_path: Path, monkeypatch) -> None:
        _mk(tmp_path)
        (tmp_path / "web/reject_shadow.json").write_text(json.dumps({
            "n_eligible": 6, "n_pending_rescore": 0,
            "audit": {"over_strict": False, "n_rejects": 6, "n_would_have_paid": 0}}))
        monkeypatch.setattr(m, "ROOT", tmp_path)
        defects: list[tuple[str, str]] = []
        m.check_rejection_shadow(defects)
        assert defects == []
