"""§42 half of the carry-over brief: stale ledger rows must reach the brain (R0075).

The brief is the FIRST thing in every brain prompt and it carried only max_audit defects, while
the recommendation ledger -- the organ that actually drives conversion -- sat at 145 open rows no
prompt ever surfaced. Rows nobody is shown are rows nobody works, which is exactly what L1.28b
measured: no row older than 3.67 days had EVER been implemented.

The refusal path is tested FIRST and deliberately. An organ with no vocabulary for "I could not
measure" reports OK on absent input (L1.41 condition 1), and for THIS organ that failure is
maximally expensive: a brief that prints an empty queue when the ledger is unreadable tells the
brain there is no work owed, which is the one thing it must never say by accident.
"""

from __future__ import annotations

from typing import Any

import pytest
import scripts.carryover_brief as cb


class TestTheLedgerBlockRefusesHonestly:
    def test_an_unreadable_ledger_reports_UNMEASURED_not_empty(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The dangerous direction. 'Nothing owed' and 'I could not look' are different claims."""
        import scripts.recommendations as rec

        def _boom() -> dict[str, Any]:
            raise OSError("ledger gone")

        monkeypatch.setattr(rec, "_load", _boom)
        out = cb.ledger_block()
        assert "UNMEASURED" in out
        assert "NOT 'nothing owed'" in out
        assert "OSError" in out           # the cause is named, not swallowed

    def test_a_genuinely_clean_ledger_says_so(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The OTHER direction must still be reachable, or the fence would cry wolf forever."""
        import scripts.recommendations as rec
        monkeypatch.setattr(rec, "_load", lambda: {"recommendations": []})
        monkeypatch.setattr(rec, "owed", lambda _d: ([], []))
        out = cb.ledger_block()
        assert "no recommendation row owes a disposition" in out
        assert "UNMEASURED" not in out


class TestTheLedgerBlockRanksWhatMatters:
    @staticmethod
    def _row(rid: str, status: str, age_h: float, due: str | None = None) -> dict[str, Any]:
        from datetime import UTC, datetime, timedelta
        raised = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
        return {"id": rid, "status": status, "raised": raised, "due": due,
                "summary": f"summary for {rid}"}

    def test_past_due_outranks_merely_open_even_when_younger(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A blown schedule broke an explicit commitment; an open row was only ever ignored."""
        import scripts.recommendations as rec
        young_overdue = self._row("R9001", "scheduled", 30.0, due="2020-01-01")
        ancient_open = self._row("R9002", "open", 900.0)
        monkeypatch.setattr(rec, "_load",
                            lambda: {"recommendations": [ancient_open, young_overdue]})
        monkeypatch.setattr(rec, "owed", lambda _d: ([ancient_open], [young_overdue]))
        out = cb.ledger_block()
        assert out.index("R9001") < out.index("R9002"), "past-due must be listed first"
        assert "PAST-DUE" in out and "undisposed" in out

    def test_truncation_states_the_true_total_and_refuses_to_excuse_the_rest(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Silent truncation reads as 'covered everything'. The count and the disclaimer are the
        difference between a workable batch and a shrunken denominator (L1.35)."""
        import scripts.recommendations as rec
        rows = [self._row(f"R9{i:03d}", "open", 100.0 + i) for i in range(25)]
        monkeypatch.setattr(rec, "_load", lambda: {"recommendations": rows})
        monkeypatch.setattr(rec, "owed", lambda _d: (rows, []))
        out = cb.ledger_block()
        assert f"shown {cb._LEDGER_ROWS} of 25" in out
        assert "NOT excused" in out
        assert out.count("[undisposed ]") == cb._LEDGER_ROWS

    def test_the_staleness_rule_is_imported_not_restated(self) -> None:
        """The rule has exactly ONE definition. The sibling defect fixed on this same file hours
        earlier was a second copy of a rule drifting from its source (the brief kept its own idea
        of which defects were acked and ran 57% false); re-deriving grace/due here rebuilds that
        bug one drawer down."""
        import inspect

        import scripts.recommendations as rec
        src = inspect.getsource(cb.ledger_block)
        assert "rec.owed(" in src, "must call the canonical owed()"
        assert "GRACE_H" not in src, "must not restate the grace window"
        assert callable(rec.owed)
