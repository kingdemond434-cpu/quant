"""Tests for evidence-adjustable thresholds -- bounded, direction-guarded, logged, reversible."""

from __future__ import annotations

from pathlib import Path

from libs.self_improvement.adaptive_thresholds import ThresholdBook, registry


class TestThresholdBook:
    def test_defaults_when_no_store(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        assert book.get("depth_deep_days") == 180.0
        assert book.get("reject_deploy_threshold") == 0.5

    def test_apply_within_bounds(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        val, changed, why = book.propose("depth_deep_days", 250.0, reason="more archive available")
        assert changed is True and val == 250.0
        assert book.get("depth_deep_days") == 250.0  # persisted
        assert "applied" in why

    def test_clamped_to_ceiling(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        val, _c, _w = book.propose("depth_deep_days", 99999.0, reason="x")
        assert val == 730.0  # ceiling, never beyond

    def test_clamped_to_floor(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        val, _, _ = book.propose("depth_deep_days", 1.0, reason="x")
        assert val == 90.0  # floor

    def test_tighten_only_rejects_loosening(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        # deploy threshold is tighten_only, tighten_is_up=True -> lowering (loosening) is rejected
        val, changed, why = book.propose("reject_deploy_threshold", 0.35, reason="loosen attempt")
        assert changed is False
        assert val == 0.5  # unchanged
        assert "rejected" in why and "loosen" in why

    def test_tighten_only_allows_tightening(self, tmp_path: Path) -> None:
        book = ThresholdBook(tmp_path / "t.json")
        val, changed, _ = book.propose("reject_deploy_threshold", 0.8, reason="raise bar")
        assert changed is True and val == 0.8

    def test_leak_tolerance_tighten_is_down(self, tmp_path: Path) -> None:
        # leak_tolerance is tighten_only with tighten_is_up=False -> LOWER is stricter (allowed),
        # raising it (dulling leak detection) is rejected
        book = ThresholdBook(tmp_path / "t.json")
        v1, c1, _ = book.propose("reject_leak_tolerance", 0.07, reason="stricter")
        assert c1 is True and v1 == 0.07
        v2, c2, why = book.propose("reject_leak_tolerance", 0.20, reason="looser")
        assert c2 is False and v2 == 0.07
        assert "rejected" in why

    def test_get_reclamps_hand_edited_store(self, tmp_path: Path) -> None:
        store = tmp_path / "t.json"
        store.write_text('{"depth_deep_days": 100000}')  # out-of-envelope hand edit
        book = ThresholdBook(store)
        assert book.get("depth_deep_days") == 730.0  # re-clamped to ceiling on read

    def test_log_written(self, tmp_path: Path) -> None:
        log = tmp_path / "log.jsonl"
        book = ThresholdBook(tmp_path / "t.json", log=log)
        book.propose("depth_deep_days", 200.0, reason="evidence")
        assert log.exists() and "evidence" in log.read_text()

    def test_registry_specs_are_bounded(self) -> None:
        for name, spec in registry().items():
            assert spec.floor <= spec.default <= spec.ceiling, name
            assert spec.direction in ("free", "tighten_only", "loosen_only")
