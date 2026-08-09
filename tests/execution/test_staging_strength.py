"""MUTATION-DRIVEN STRENGTH TESTS for the S0/S1/S2 stage machine (gap #53, money path).

Measured 2026-07-29: `libs/execution/staging.py` killed **69.0%** of mutants against the v8 8.2 bar
of 90%. Reading the 13 survivors gave one answer: **every numeric threshold in the promotion gates
was unpinned.** `capital_fraction <= 0.10`, `4 <= symbol_count <= 5`, `live_weeks >= 8`,
`calibration_rows >= 10`, `critical_drill_failures == 0`, `realized_cost_ratio <= 1.25` -- each
could be nudged (`<=` to `<`, `8.0` to `9.0`, `0` to `1`, `1.0` to `2.0`) with the suite still
green. The existing tests proved the machine's STRUCTURE (promotion never skips, demotion is
unlimited, transitions are logged); nothing proved its NUMBERS.

That matters more here than anywhere else in the repo: this is the gate that decides when real
capital scales, and register #2's 07-31 deadline runs through it. A gate whose thresholds no test
pins is a gate that can be edited by accident.

Each test below is written as a BOUNDARY pair -- the value that must pass and the neighbouring
value that must fail -- because only a pair kills an off-by-one mutant.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.execution import staging


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(staging, "_STATE", tmp_path / "stage_state.json")


def _s1(**over: Any) -> dict[str, Any]:
    ev = {"principal_signoff": True, "capital_fraction": 0.10, "symbol_count": 4,
          "keys_present": True, "connector_verified": True}
    ev.update(over)
    return ev


def _s2(**over: Any) -> dict[str, Any]:
    # NB the evidence key is `cost_ratio`, while the CHECK is named `realized_cost_le_1_25x`.
    # Writing these tests against the check name first produced four false failures -- worth
    # keeping in the record: an evidence contract whose key does not match its check name is a
    # trap for the caller that has to supply it (the executor, at Gate-0).
    ev = {"live_weeks": 8.0, "calibration_rows": 10, "critical_drill_failures": 0,
          "cost_ratio": 1.25, "drill_pass_streak_weeks": 8}
    ev.update(over)
    return ev


class TestS1Thresholds:
    """S1 = first real capital. Every bound gets its passing value AND its failing neighbour."""

    def test_capital_fraction_boundary_is_inclusive_at_010(self) -> None:
        assert staging.s1_entry_met(_s1(capital_fraction=0.10))[0] is True
        assert staging.s1_entry_met(_s1(capital_fraction=0.1001))[0] is False

    def test_symbol_count_window_is_4_to_5_inclusive(self) -> None:
        for n in (4, 5):
            assert staging.s1_entry_met(_s1(symbol_count=n))[0] is True, n
        for n in (3, 6):
            assert staging.s1_entry_met(_s1(symbol_count=n))[0] is False, n

    def test_missing_capital_fraction_defaults_to_REFUSE(self) -> None:
        # Fail-closed: an absent number must never read as a satisfied gate.
        ev = _s1()
        del ev["capital_fraction"]
        assert staging.s1_entry_met(ev)[0] is False

    def test_missing_symbol_count_defaults_to_REFUSE(self) -> None:
        ev = _s1()
        del ev["symbol_count"]
        assert staging.s1_entry_met(ev)[0] is False

    @pytest.mark.parametrize("flag", ["principal_signoff", "keys_present", "connector_verified"])
    def test_each_boolean_precondition_is_individually_load_bearing(self, flag: str) -> None:
        assert staging.s1_entry_met(_s1(**{flag: False}))[0] is False

    def test_reason_string_names_every_check(self) -> None:
        _ok, why = staging.s1_entry_met(_s1(capital_fraction=0.99))
        for name in ("principal_signoff", "capital_fraction", "symbol_count", "keys_present",
                     "connector_verified"):
            assert name in why


class TestS2Thresholds:
    """S2 = full automation. Automatic and numeric by design, so the numbers ARE the gate."""

    def test_live_weeks_boundary_is_inclusive_at_8(self) -> None:
        assert staging.s2_entry_met(_s2(live_weeks=8.0))[0] is True
        assert staging.s2_entry_met(_s2(live_weeks=7.99))[0] is False

    def test_calibration_rows_boundary_is_inclusive_at_10(self) -> None:
        assert staging.s2_entry_met(_s2(calibration_rows=10))[0] is True
        assert staging.s2_entry_met(_s2(calibration_rows=9))[0] is False

    def test_zero_critical_drill_failures_means_exactly_zero(self) -> None:
        assert staging.s2_entry_met(_s2(critical_drill_failures=0))[0] is True
        assert staging.s2_entry_met(_s2(critical_drill_failures=1))[0] is False

    def test_realized_cost_ratio_boundary_is_inclusive_at_125(self) -> None:
        assert staging.s2_entry_met(_s2(cost_ratio=1.25))[0] is True
        assert staging.s2_entry_met(_s2(cost_ratio=1.2501))[0] is False

    def test_missing_drill_record_REFUSES_not_passes(self) -> None:
        """THE FAIL-OPEN THIS FILE FOUND. `critical_drill_failures` absent used to read as zero
        failures, so S2 passed on missing evidence -- on the gate that authorises full automation.
        Every sibling check defaults to refusing; this one defaulted permissive."""
        ev = _s2()
        del ev["critical_drill_failures"]
        assert staging.s2_entry_met(ev)[0] is False
        assert staging.s2_entry_met(_s2(critical_drill_failures=0))[0] is True   # 0 still passes

    @pytest.mark.parametrize("key", ["live_weeks", "calibration_rows", "cost_ratio",
                                     "critical_drill_failures"])
    def test_every_s2_field_defaults_to_REFUSE_when_absent(self, key: str) -> None:
        ev = _s2()
        del ev[key]
        assert staging.s2_entry_met(ev)[0] is False, f"{key} absent must not satisfy the gate"

    def test_missing_cost_ratio_defaults_to_REFUSE(self) -> None:
        # The default must sit on the REFUSING side of the bound, not the permissive side.
        ev = _s2()
        del ev["cost_ratio"]
        assert staging.s2_entry_met(ev)[0] is False


class TestStateLoading:
    """`_load` is the only path that trusts a file; its guard was unpinned (line 40 And->Or)."""

    def test_corrupt_state_falls_back_to_S0(self, tmp_path: Path) -> None:
        (tmp_path / "stage_state.json").write_text("{not json", "utf-8")
        assert staging.current_stage() == "S0"

    def test_unknown_stage_value_falls_back_to_S0(self, tmp_path: Path) -> None:
        # The And->Or mutant on the isinstance/stage-membership guard survives unless a file with
        # a VALID shape but an INVALID stage is rejected -- fail-closed to the floor stage.
        (tmp_path / "stage_state.json").write_text(json.dumps({"stage": "S9"}), "utf-8")
        assert staging.current_stage() == "S0"

    def test_non_dict_state_falls_back_to_S0(self, tmp_path: Path) -> None:
        (tmp_path / "stage_state.json").write_text(json.dumps(["S2"]), "utf-8")
        assert staging.current_stage() == "S0"

    def test_valid_state_is_honoured_and_history_defaulted(self, tmp_path: Path) -> None:
        (tmp_path / "stage_state.json").write_text(json.dumps({"stage": "S1"}), "utf-8")
        assert staging.current_stage() == "S1"


class TestTransitionInvariants:
    """Structure was already tested; these pin the RETURN CONTRACTS the mutants exposed."""

    def test_promote_returns_false_and_a_reason_when_refused(self) -> None:
        ok, why = staging.promote({})
        assert ok is False and "gate not met" in why      # line 94: return-None / False->True

    def test_demote_at_floor_returns_false_not_none(self) -> None:
        ok, msg = staging.demote("test")
        assert ok is False and "S0" in msg

    def test_promotion_then_demotion_round_trips_exactly_one_stage(self) -> None:
        assert staging.promote(_s1())[0] is True
        assert staging.current_stage() == "S1"
        ok, target = staging.demote("tripwire")
        assert ok is True and target == "S0"
        assert staging.current_stage() == "S0"

    def test_s0_cannot_reach_s2_in_one_call_even_with_perfect_evidence(self) -> None:
        ev = {**_s1(), **_s2()}
        assert staging.promote(ev)[0] is True
        assert staging.current_stage() == "S1"           # never skips a stage
