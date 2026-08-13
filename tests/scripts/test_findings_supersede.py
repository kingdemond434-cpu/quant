"""A REFUTED FINDING NEEDS AN EXIT THAT IS NOT A LIE.

The findings lifecycle was raised -> fixed -> verified, and `ruling` is set once at `add` time, so
a finding a later panel proves WRONG had nowhere to go. Both available moves were bad: leave it
accepted-and-unfixed, where it rots and fires `findings-rotting` forever demanding work nobody
should do; or `fix` it, which is a false claim that removes it from view permanently AND credits
the seat that raised it with a hit it did not earn -- and the scorecard is the per-seat
calibration governance uses to decide which models to keep.

Measured 2026-08-13: F0004 (superseded by F0020) and F0007 (superseded by F0008, which says so in
its own first clause) had both been accepted-and-unfixed past the 14d defect bar with no legal way
to close them.

THE TESTS THAT MATTER MOST ARE THE ONES PINNING WHAT SUPERSESSION IS NOT: not a fix, not a
deletion, and not available without naming the successor.
"""
from __future__ import annotations

import json
from argparse import Namespace

import pytest

from scripts import track_findings as tf


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Redirected to tmp_path -- never the live findings ledger."""
    path = tmp_path / "findings_ledger.json"
    monkeypatch.setattr(tf, "LEDGER", path)
    path.write_text(json.dumps({"next_id": 3, "findings": [
        {"id": "F0001", "model": "seat-a", "summary": "the refuted one", "severity": "high",
         "ruling": "accepted", "raised": "2026-07-01T00:00:00+00:00",
         "fixed": None, "fix_commit": None, "verified": None},
        {"id": "F0002", "model": "seat-b", "summary": "the successor", "severity": "high",
         "ruling": "accepted", "raised": "2026-07-20T00:00:00+00:00",
         "fixed": None, "fix_commit": None, "verified": None},
    ]}), "utf-8")
    return path


def _rows(path):
    return {f["id"]: f for f in json.loads(path.read_text("utf-8"))["findings"]}


def _supersede(fid, by, reason="because the evidence said so"):
    tf.supersede(Namespace(id=fid, by=by, reason=reason))


class TestSupersessionIsNotAFix:
    def test_it_never_sets_fixed_so_the_seat_earns_no_hit(self, ledger):
        _supersede("F0001", "F0002")
        row = _rows(ledger)["F0001"]
        assert row["superseded_by"] == "F0002"
        assert row["fixed"] is None, "a refuted finding is not a fixed one"
        assert row["fix_commit"] is None

    def test_the_scorecard_does_not_credit_a_superseded_finding(self, ledger, capsys):
        _supersede("F0001", "F0002")
        tf.scorecard(None)
        out = capsys.readouterr().out
        assert "seat-a" in out                      # still listed -- history stays auditable
        assert "0.0%" in out                        # and its hit rate is unchanged at zero

    def test_the_row_is_never_deleted(self, ledger):
        _supersede("F0001", "F0002")
        assert "F0001" in _rows(ledger)
        assert _rows(ledger)["F0001"]["summary"] == "the refuted one"

    def test_the_reason_is_recorded(self, ledger):
        _supersede("F0001", "F0002", reason="live risk file read at 01:01:23Z says -17.65%")
        assert "01:01:23Z" in _rows(ledger)["F0001"]["supersede_reason"]


class TestSupersessionRequiresSomethingToSupersedeTo:
    def test_an_unknown_successor_is_refused(self, ledger):
        """Otherwise this is a deletion with a reason attached: the concern must live somewhere."""
        with pytest.raises(SystemExit, match="not found"):
            _supersede("F0001", "F9999")
        assert _rows(ledger)["F0001"].get("superseded_by") is None

    def test_a_finding_cannot_supersede_itself(self, ledger):
        with pytest.raises(SystemExit, match="cannot supersede itself"):
            _supersede("F0001", "F0001")

    def test_an_unknown_subject_is_refused(self, ledger):
        with pytest.raises(SystemExit, match="not found"):
            _supersede("F9999", "F0002")


class TestTheClosureIsVisibleNotADisappearance:
    def test_report_drops_it_from_unfixed_but_still_lists_it(self, ledger, capsys):
        _supersede("F0001", "F0002")
        tf.report(None)
        out = capsys.readouterr().out
        assert "SUPERSEDED: 1" in out
        assert "UNFIXED: 1" in out                  # F0002 only
        assert "[ super] F0001 -> F0002" in out

    def test_the_rotting_fence_stops_counting_it(self, ledger, monkeypatch):
        """The whole point: a closed-as-refuted row must not demand work forever."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("ma_sup", tf.Path(
            __file__).resolve().parents[2] / "scripts/max_audit.py")
        ma = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ma)
        monkeypatch.setattr(ma, "ROOT", ledger.parent.parent)

        def _fake_j(path, default):
            return json.loads(ledger.read_text("utf-8"))
        monkeypatch.setattr(ma, "_j", _fake_j)

        before: list = []
        ma.check_findings(before)
        assert before and "F0001" in before[0][1]   # rotting while open

        _supersede("F0001", "F0002")
        after: list = []
        ma.check_findings(after)
        assert not any("F0001" in msg for _k, msg in after)
