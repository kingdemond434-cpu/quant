"""AN ABSENT GATE AND A PASSED GATE WERE BYTE-IDENTICAL TO EVERY READER (R0419).

`admit()` blocks on `[g for g in STRUCTURAL_GATES if g in gates and not gates[g]]`. The `g in
gates` is CORRECT and stays: a screen with zero promotion authority must not kill a candidate for
an input its caller never supplied -- that is the `beats_baselines` defect pointed the other way.
What was wrong is that the omission left no trace, so a structural gate that had never once
evaluated was indistinguishable from one that always passed, in every artifact the desk produced.

Measured against every site that can write a gate in `libs.autodiscovery.validation`: of the six
declared structural gates, `break_even_win_rate` is written by NOTHING anywhere in the repo.

These tests pin the DISTINCTION and the NON-BLOCKING, because the two together are the fix. A
version that made absence visible by making it fail would be a loosened screen wearing a fix's
clothes, and would kill real alphas on their caller's missing input.
"""

from __future__ import annotations

import pytest

from libs.validation.screen_admission import (
    MIN_ADMISSION_BARS,
    MIN_ADMISSION_OOS_SHARPE,
    STATISTICAL_GATES,
    STRUCTURAL_GATES,
    admit,
)


def _cand(name="c", **gates):
    # Comfortably clear of BOTH relevance floors, so a failure here is about the gate under test
    # and never about the fixture: `insufficient_bars` is itself a structural block, and a fixture
    # tripping it would make every one of these tests pass for the wrong reason.
    return {"name": name, "gates": gates, "oos_sharpe": MIN_ADMISSION_OOS_SHARPE + 1.0,
            "dsr": 0.1, "reality_p": 0.2, "n_bars": MIN_ADMISSION_BARS + 100,
            "cost_basis": "net"}


def _all_pass():
    return dict.fromkeys((*STRUCTURAL_GATES, *STATISTICAL_GATES), True)


class TestAbsenceIsRecordedAndStillDoesNotBlock:
    def test_an_absent_structural_gate_does_not_block(self):
        """The behaviour that must NOT change: absent is not failed."""
        supplied = _all_pass()
        del supplied["capacity"]
        plan = admit([_cand(**supplied)], idle_slots=1)
        assert len(plan.admitted) == 1
        assert plan.admitted[0].blocked_by == ()

    def test_but_the_absence_is_now_named_on_the_row(self):
        supplied = _all_pass()
        del supplied["capacity"]
        plan = admit([_cand(**supplied)], idle_slots=1)
        assert "capacity" in plan.admitted[0].unmeasured_gates

    def test_a_supplied_failing_gate_still_blocks(self):
        """The screen is unchanged where it was working."""
        plan = admit([_cand(**{**_all_pass(), "capacity": False})], idle_slots=1)
        assert plan.blocked and "capacity" in plan.blocked[0].blocked_by

    def test_a_supplied_passing_gate_is_not_reported_unmeasured(self):
        plan = admit([_cand(**_all_pass())], idle_slots=1)
        assert plan.admitted[0].unmeasured_gates == ()


class TestTheHistogramSeparatesNeverRanFromAlwaysPassed:
    """L1.49: absence from a rejection tally is ambiguous, and the two readings differ.

    "never evaluated" is a WIRING defect whose repair is upward -- supply the input, or record
    that it cannot be supplied. "evaluated and always passed" is a THRESHOLD question. Collapsing
    them sends the reader to fix the wrong thing.
    """

    def test_a_never_supplied_gate_reads_never_evaluated(self):
        supplied = _all_pass()
        del supplied["break_even_win_rate"]
        plan = admit([_cand(f"c{i}", **supplied) for i in range(4)], idle_slots=4)
        assert "NEVER-EVALUATED" in plan.welded_gates()["break_even_win_rate"]

    def test_a_gate_that_always_passes_reads_constant_pass_not_never_evaluated(self):
        plan = admit([_cand(f"c{i}", **_all_pass()) for i in range(4)], idle_slots=4)
        assert "CONSTANT-PASS" in plan.welded_gates()["capacity"]

    def test_a_gate_that_always_rejects_reads_constant_reject(self):
        rows = [_cand(f"c{i}", **{**_all_pass(), "fragility": False}) for i in range(4)]
        assert "CONSTANT-REJECT" in admit(rows, idle_slots=4).welded_gates()["fragility"]

    def test_a_discriminating_gate_is_not_flagged_at_all(self):
        """A gate doing its job must not appear -- noise on a healthy gate trains it away."""
        rows = [_cand(f"c{i}", **{**_all_pass(), "capacity": i % 2 == 0}) for i in range(4)]
        assert "capacity" not in admit(rows, idle_slots=4).welded_gates()

    def test_unmeasured_is_a_first_class_column_not_folded_into_either_side(self):
        supplied = _all_pass()
        del supplied["break_even_win_rate"]
        plan = admit([_cand(f"c{i}", **supplied) for i in range(3)], idle_slots=3)
        cell = plan.gate_histogram["break_even_win_rate"]
        assert cell == {"pass": 0, "fail": 0, "unmeasured": 3}

    def test_every_declared_gate_appears_in_the_histogram(self):
        """L1.57: a gate missing from the tally is exactly the invisibility this fixes."""
        plan = admit([_cand(**_all_pass())], idle_slots=1)
        for g in (*STRUCTURAL_GATES, *STATISTICAL_GATES):
            assert g in plan.gate_histogram, f"{g} is declared but absent from the tally"

    def test_the_finding_reaches_the_plan_notes(self):
        """A histogram nobody reads is the same defect one layer down."""
        supplied = _all_pass()
        del supplied["break_even_win_rate"]
        plan = admit([_cand(f"c{i}", **supplied) for i in range(3)], idle_slots=3)
        assert any("GATE-OPTIMALITY" in n and "break_even_win_rate" in n for n in plan.notes)

    def test_an_empty_cohort_reports_no_welded_gates(self):
        """Zero candidates means zero evidence, not "every gate is dead" (L1.28a)."""
        plan = admit([], idle_slots=3)
        assert not any("GATE-OPTIMALITY" in n for n in plan.notes)


class TestBreakEvenWinRateIsTheGateWithNoWriter:
    def test_it_is_declared_structural(self):
        assert "break_even_win_rate" in STRUCTURAL_GATES

    @pytest.mark.parametrize("gate", ["break_even_win_rate"])
    def test_nothing_in_the_repo_supplies_it(self, gate):
        """The row's core claim, pinned so a future writer flips this test rather than nothing.

        `libs.autodiscovery.validation` is the only producer of a gates dict on the production
        path. If it ever learns to emit this gate, this assertion fails and the reader is told to
        delete it -- which is the outcome R0419 wants and the repair pointing upward.
        """
        from pathlib import Path
        src = Path("libs/autodiscovery/validation.py").read_text("utf-8")
        assert f'"{gate}"' not in src, (
            f"{gate} now has a writer -- delete this test and the NEVER-EVALUATED note with it")
