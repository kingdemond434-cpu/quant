"""R0274: the growth audit must tell TIMIDITY from a LATCHED SURVIVAL RAIL.

`justified_by` was hardcoded to "NONE -- ..." for any under-deployment, and `conservatism_defects`
is derived from exactly that prefix. So a book held flat by a fired ruin rail published as a
conservatism defect, in an artifact whose own `rule` field tells the reader to "close it
same-cycle". An organ obeying that against a latched rail closes it by RE-ARMING A KILLED BOOK.

The direction that must never regress: naming the rail may NOT turn the gap into health. The
verdict stays GAP; only the justification changes, because the justification is what an organ acts
on.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_growth_audit", _ROOT / "scripts" / "run_growth_audit.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_no_kill_file_means_the_gap_is_a_real_conservatism_defect(tmp_path, monkeypatch):
    """The anti-timidity half, and it is the half that must not be weakened.

    With nothing explaining the under-deployment, the audit must still call it a defect. A fix
    that made every gap excusable would be worse than the bug it replaced.
    """
    m = _mod()
    monkeypatch.setattr(m, "_KILL", tmp_path / "nope")
    assert m._clamp_state() is None


def test_latched_kill_file_is_reported_as_a_rail_not_as_timidity(tmp_path, monkeypatch):
    m = _mod()
    k = tmp_path / "CASHCARRY_KILL"
    k.write_text("live_guard freeze: pager ladder at 4h rung (disarmed)", "utf-8")
    monkeypatch.setattr(m, "_KILL", k)
    c = m._clamp_state()
    assert c is not None
    assert c["rail"] == "CASHCARRY_KILL"
    assert "pager ladder" in c["detail"]
    assert c["since"] != "unknown"


def test_every_clamp_carries_a_lifting_condition(tmp_path, monkeypatch):
    """L1.51: a clamp with no lifting condition is UNPRICED, which is its own defect."""
    m = _mod()
    k = tmp_path / "CASHCARRY_KILL"
    k.write_text("frozen", "utf-8")
    monkeypatch.setattr(m, "_KILL", k)
    c = m._clamp_state()
    assert c["lifting_condition"]
    assert "principal" in c["lifting_condition"].lower()
    # The restart-verification lesson must travel with the lifting condition: a committed fix is
    # inert until the process restarts (desk lesson L0004), and the re-arm is when that happens.
    assert "restart" in c["lifting_condition"].lower()


@pytest.mark.parametrize("key", ["holds_usd", "usd_per_day", "cumulative_usd"])
def test_paper_book_publishes_no_dollar_figure(tmp_path, monkeypatch, key):
    """L1.51 refuses a cost computed from a simulated denominator.

    "A cost from a simulated denominator is WORSE than no number because a reader will act on it."
    The desk has never deployed live capital, so there is no honest price for this clamp and the
    refusal is the measurement.
    """
    m = _mod()
    k = tmp_path / "CASHCARRY_KILL"
    k.write_text("frozen", "utf-8")
    monkeypatch.setattr(m, "_KILL", k)
    assert m._clamp_state()[key] == "UNMEASURABLE-PAPER-BOOK"


def test_unreadable_kill_file_is_latched_not_absent(tmp_path, monkeypatch):
    """ABSENT and UNREADABLE demand opposite responses (L1.55); only one licenses "timid"."""
    m = _mod()
    k = tmp_path / "CASHCARRY_KILL"
    k.mkdir()                      # a directory reads as present-but-unreadable
    monkeypatch.setattr(m, "_KILL", k)
    c = m._clamp_state()
    assert c is not None, "an unreadable rail file must never read as 'no rail latched'"
    assert "UNREADABLE" in c["detail"] or "latched" in c["detail"]
