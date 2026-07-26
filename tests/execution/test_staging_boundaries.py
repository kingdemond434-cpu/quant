"""Boundary tests for the S1/S2 gates -- written because mutation testing said nobody had.

The 2026-07-26 mutation run scored `libs/execution/staging.py` at 63%, and every survivor was a
gate boundary: `>= 8.0` weeks mutated to `> 8.0` and no test noticed, same for `>= 10` rows,
`<= 1.25` cost, `<= 0.10` capital fraction and the 4-5 symbol window. The suite proved the gate
RUNS; nothing proved where it sits. On a go-live gate the exact boundary is the whole content of
the rule, so each one is pinned from both sides here.
"""

from __future__ import annotations

import pytest

from libs.execution import staging
from libs.execution.staging import s1_entry_met, s2_entry_met

S1_OK = {"principal_signoff": True, "capital_fraction": 0.10, "symbol_count": 4,
         "keys_present": True, "connector_verified": True}
S2_OK = {"live_weeks": 8.0, "calibration_rows": 10, "critical_drill_failures": 0,
         "cost_ratio": 1.25}


class TestS1Boundaries:
    def test_the_clean_sheet_passes(self) -> None:
        assert s1_entry_met(S1_OK)[0]

    @pytest.mark.parametrize("frac,expected", [(0.0999, True), (0.10, True), (0.1001, False)])
    def test_capital_fraction_boundary_is_inclusive_at_ten_percent(
        self, frac: float, expected: bool
    ) -> None:
        assert s1_entry_met({**S1_OK, "capital_fraction": frac})[0] is expected

    @pytest.mark.parametrize("n,expected", [(3, False), (4, True), (5, True), (6, False)])
    def test_the_symbol_window_is_exactly_four_to_five(self, n: int, expected: bool) -> None:
        assert s1_entry_met({**S1_OK, "symbol_count": n})[0] is expected

    @pytest.mark.parametrize("key", ["principal_signoff", "keys_present", "connector_verified"])
    def test_each_boolean_precondition_blocks_alone(self, key: str) -> None:
        assert not s1_entry_met({**S1_OK, key: False})[0]

    def test_missing_evidence_fails_closed(self) -> None:
        """An absent capital_fraction must not read as zero-and-therefore-safe by accident --
        it defaults to 1.0, which fails. Pinning this stops a 'tidy' default flip going unseen."""
        assert not s1_entry_met({})[0]

    def test_signoff_is_never_inferred(self) -> None:
        ok, why = s1_entry_met({k: v for k, v in S1_OK.items() if k != "principal_signoff"})
        assert not ok and "principal_signoff=False" in why


class TestS2Boundaries:
    def test_the_clean_sheet_passes(self) -> None:
        assert s2_entry_met(S2_OK)[0]

    @pytest.mark.parametrize("w,expected", [(7.99, False), (8.0, True), (8.01, True)])
    def test_live_weeks_boundary_is_inclusive_at_eight(self, w: float, expected: bool) -> None:
        assert s2_entry_met({**S2_OK, "live_weeks": w})[0] is expected

    @pytest.mark.parametrize("n,expected", [(9, False), (10, True), (11, True)])
    def test_calibration_rows_boundary_is_inclusive_at_ten(
        self, n: int, expected: bool
    ) -> None:
        assert s2_entry_met({**S2_OK, "calibration_rows": n})[0] is expected

    @pytest.mark.parametrize("r,expected", [(1.24, True), (1.25, True), (1.26, False)])
    def test_cost_ratio_boundary_is_inclusive_at_1_25(
        self, r: float, expected: bool
    ) -> None:
        assert s2_entry_met({**S2_OK, "cost_ratio": r})[0] is expected

    @pytest.mark.parametrize("n,expected", [(0, True), (1, False)])
    def test_a_single_critical_drill_failure_blocks(self, n: int, expected: bool) -> None:
        assert s2_entry_met({**S2_OK, "critical_drill_failures": n})[0] is expected

    def test_missing_evidence_fails_closed(self) -> None:
        assert not s2_entry_met({})[0]

    def test_every_condition_fails_closed_INDIVIDUALLY_on_empty_evidence(self) -> None:
        """Not just the gate as a whole -- each condition separately.

        `critical_drill_failures` defaulted to 0 and so PASSED on an empty dict: a broken
        drill-evidence pipeline read as "no failures". The aggregate test above still went red
        for other reasons, which is exactly how a fail-open condition hides inside a
        fail-closed gate.
        """
        _, why = s2_entry_met({})
        assert "critical_drill_failures_eq_0=False" in why
        assert "=True" not in why

    def test_every_failing_condition_is_named_in_the_reason(self) -> None:
        """The reason string is what a human reads at the gate; it has to be complete."""
        _, why = s2_entry_met({})
        for k in ("live_weeks_ge_8", "calibration_rows_ge_10",
                  "critical_drill_failures_eq_0", "realized_cost_le_1_25x"):
            assert k in why


class TestStatePersistence:
    """Survivors at the state-file layer: nothing tested what a MALFORMED stage file does."""

    def test_a_corrupt_state_file_falls_back_to_s0(self, tmp_path, monkeypatch) -> None:
        p = tmp_path / "stage_state.json"
        p.write_text("{ not json", "utf-8")
        monkeypatch.setattr(staging, "_STATE", p)
        assert staging.current_stage() == "S0"

    def test_a_state_file_with_an_unknown_stage_falls_back_to_s0(
        self, tmp_path, monkeypatch
    ) -> None:
        """`isinstance(d, dict) AND stage in _STAGES` -- mutating that `and` to `or` changed no
        test, meaning a file claiming stage 'S9' would have been accepted verbatim."""
        p = tmp_path / "stage_state.json"
        p.write_text('{"stage": "S9"}', "utf-8")
        monkeypatch.setattr(staging, "_STATE", p)
        assert staging.current_stage() == "S0"

    def test_a_non_dict_state_file_falls_back_to_s0(self, tmp_path, monkeypatch) -> None:
        p = tmp_path / "stage_state.json"
        p.write_text('["S2"]', "utf-8")
        monkeypatch.setattr(staging, "_STATE", p)
        assert staging.current_stage() == "S0"

    def test_a_missing_state_file_is_s0(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "absent.json")
        assert staging.current_stage() == "S0"


class TestPromotionReturnsAreLoadBearing:
    """`return False, "gate not met"` mutated to `return True, ...` survived: tests checked the
    stage had not moved, but nothing checked the BOOLEAN callers branch on."""

    def test_a_blocked_promotion_returns_false(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "s.json")
        ok, why = staging.promote({})
        assert ok is False and "gate not met" in why
        assert staging.current_stage() == "S0"

    def test_a_met_gate_returns_true_and_moves_exactly_one_stage(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "s.json")
        ok, why = staging.promote(S1_OK)
        assert ok is True and "promoted S0 -> S1" in why
        assert staging.current_stage() == "S1"

    def test_promotion_never_skips_to_s2(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "s.json")
        staging.promote({**S1_OK, **S2_OK})
        assert staging.current_stage() == "S1"

    def test_demotion_returns_the_new_stage_and_is_never_gated(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "s.json")
        staging.promote(S1_OK)
        ok, target = staging.demote("tripwire")
        assert ok is True and target == "S0"

    def test_demoting_at_the_floor_returns_false(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(staging, "_STATE", tmp_path / "s.json")
        ok, why = staging.demote("tripwire")
        assert ok is False and "already at S0" in why
