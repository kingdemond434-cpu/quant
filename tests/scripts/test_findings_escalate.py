"""A FINDING NOBODY IS PERMITTED TO FIX NEEDS AN EXIT THAT IS NOT A LIE EITHER.

`supersede` exists because a finding proved WRONG had nowhere to go. This is the same hole one
state over: a finding proved RIGHT whose repair is legally reserved to a HUMAN. F0025 asks for a
change to `scripts/run_deadman_switch.py`, the Tier-3 ruin rail, which every worker prompt on this
desk forbids editing. Both available moves were bad in exactly supersede's way -- leave it
accepted-and-unfixed, where `findings-rotting` fires forever demanding work nobody may do, or
`fix` it, a false claim that removes it from view permanently and credits the seat with a hit it
did not earn.

THE TESTS THAT MATTER MOST ARE THE ONES PINNING WHAT ESCALATION IS NOT: not a fix, not a deletion,
not available without naming a person, and -- the one that keeps it honest -- NOT PERMANENT. An
escalation with no clock is an amnesty, and this exit stops a fence firing, so it is precisely the
one an inconvenient finding would hide behind. The lapse tests below are the load-bearing half.
"""
from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime, timedelta

import pytest

from scripts import track_findings as tf


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Redirected to tmp_path -- never the live findings ledger."""
    path = tmp_path / "findings_ledger.json"
    monkeypatch.setattr(tf, "LEDGER", path)
    path.write_text(json.dumps({"next_id": 2, "findings": [
        {"id": "F0001", "model": "seat-a", "summary": "tier-3 rail goes blind on a read error",
         "severity": "high", "ruling": "accepted", "raised": "2026-07-01T00:00:00+00:00",
         "fixed": None, "fix_commit": None, "verified": None},
    ]}), "utf-8")
    return path


def _rows(path):
    return {f["id"]: f for f in json.loads(path.read_text("utf-8"))["findings"]}


REASON = "Tier-3 ruin rail; every worker prompt forbids editing it -- principal sign-off only"


def _escalate(**over):
    kw = {"id": "F0001", "to": "principal", "reason": REASON, "hold_days": None}
    kw.update(over)
    return Namespace(**kw)


class TestEscalationIsNotAFix:
    def test_it_never_sets_fixed_so_the_seat_gets_no_hit(self, ledger) -> None:
        tf.escalate(_escalate())
        row = _rows(ledger)["F0001"]
        assert row["fixed"] is None and row["fix_commit"] is None
        assert row["escalated"] and row["escalated_to"] == "principal"

    def test_the_scorecard_credits_nothing(self, ledger) -> None:
        tf.escalate(_escalate())
        rows = _rows(ledger)
        assert not rows["F0001"]["fixed"], "an escalated finding must never score as a hit"

    def test_it_deletes_no_row(self, ledger) -> None:
        tf.escalate(_escalate())
        assert set(_rows(ledger)) == {"F0001"}


class TestEscalationRequiresNamingSomebody:
    @pytest.mark.parametrize("reason", ["", "not mine", "tier 3", "x" * 24])
    def test_a_thin_reason_is_refused(self, ledger, reason: str) -> None:
        with pytest.raises(SystemExit):
            tf.escalate(_escalate(reason=reason))
        assert _rows(ledger)["F0001"].get("escalated") is None

    def test_an_unknown_id_is_refused(self, ledger) -> None:
        with pytest.raises(SystemExit):
            tf.escalate(_escalate(id="F9999"))


class TestTheHoldIsNotAnAmnesty:
    """The load-bearing half. An exit that stops a fence firing must expire."""

    @pytest.mark.parametrize("hold", [0, -1, 31, 90, 3650])
    def test_a_hold_beyond_the_ceiling_is_refused(self, ledger, hold: float) -> None:
        with pytest.raises(SystemExit):
            tf.escalate(_escalate(hold_days=hold))
        assert _rows(ledger)["F0001"].get("escalated") is None

    def test_a_fresh_escalation_holds(self, ledger) -> None:
        tf.escalate(_escalate())
        assert tf.escalation_lapsed(_rows(ledger)["F0001"]) is False

    def test_it_lapses_once_the_hold_is_spent(self) -> None:
        old = (datetime.now(tz=UTC) - timedelta(days=tf.ESCALATION_HOLD_D + 1)).isoformat()
        assert tf.escalation_lapsed({"escalated": old}) is True

    def test_a_short_hold_lapses_on_its_own_clock_not_the_default(self) -> None:
        four_days_ago = (datetime.now(tz=UTC) - timedelta(days=4)).isoformat()
        assert tf.escalation_lapsed({"escalated": four_days_ago, "escalation_hold_d": 3}) is True
        assert tf.escalation_lapsed({"escalated": four_days_ago, "escalation_hold_d": 10}) is False

    def test_a_row_that_was_never_escalated_is_not_covered(self) -> None:
        """Absence resolves to the counted side, never the clean one (L1.28a)."""
        assert tf.escalation_lapsed({"id": "F0001"}) is False
        assert tf.escalation_lapsed({"escalated": None}) is False

    @pytest.mark.parametrize("bad", ["not-a-date", "", "2026-13-45", 17, [], {}])
    def test_a_corrupt_hold_lapses_rather_than_holding_forever(self, bad: object) -> None:
        """A corrupt stamp must not read as an indefinite exemption -- that is the amnesty
        arriving by way of a typo."""
        stale = (datetime.now(tz=UTC) - timedelta(days=99)).isoformat()
        assert tf.escalation_lapsed({"escalated": stale, "escalation_hold_d": bad}) is True


class TestTheFenceSeesTheDifference:
    """`findings-rotting` must stop firing on a held row and fire a DIFFERENT defect once it
    lapses -- never merge the two, they want different responses from a reader."""

    @pytest.fixture(autouse=True)
    def _tmp_root(self, tmp_path, monkeypatch):
        """Point the real fence at a tmp ledger -- exercises check_findings end to end rather
        than a helper written to be testable, which would prove only that the helper works."""
        (tmp_path / "data").mkdir()
        from scripts import max_audit
        monkeypatch.setattr(max_audit, "ROOT", tmp_path)
        self._ledger = tmp_path / "data/findings_ledger.json"

    def _defects(self, rows):
        from scripts import max_audit
        self._ledger.write_text(json.dumps({"findings": rows}), "utf-8")
        d: list = []
        max_audit.check_findings(d)
        return dict(d)

    def _row(self, **over):
        r = {"id": "F0001", "model": "m", "summary": "s", "severity": "high",
             "ruling": "accepted", "raised": "2026-01-01T00:00:00+00:00",
             "fixed": None, "verified": None}
        r.update(over)
        return r

    def test_an_unescalated_stale_finding_still_rots(self) -> None:
        assert "findings-rotting" in self._defects([self._row()])

    def test_a_held_escalation_silences_rot_without_silencing_the_ledger(self) -> None:
        held = self._row(escalated=datetime.now(tz=UTC).isoformat(), escalated_to="principal")
        got = self._defects([held])
        assert "findings-rotting" not in got
        assert "findings-escalation-lapsed" not in got

    def test_a_lapsed_escalation_fires_its_own_louder_defect(self) -> None:
        old = (datetime.now(tz=UTC) - timedelta(days=tf.ESCALATION_HOLD_D + 2)).isoformat()
        got = self._defects([self._row(escalated=old, escalated_to="principal")])
        assert "findings-escalation-lapsed" in got
        assert "principal" in got["findings-escalation-lapsed"]
        assert "findings-rotting" not in got, "a lapsed row must not double-count as generic rot"
