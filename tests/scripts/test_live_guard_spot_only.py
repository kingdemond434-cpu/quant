"""The guard on a desk that has no futures leg by construction.

WHAT HAPPENED, 2026-08-15. The principal is Irish retail: EEA derivatives are unavailable under
MiCA, so the futures account cannot be read. The futures keyfile still existed, so `_venue()`
returned the futures connector as armed, `positions()` raised, and `_reconcile` did exactly what a
carry desk needs -- FAILED CLOSED, calling the unreadable venue a naked position and freezing the
executor. A minute later it did it again.

Nothing was broken. The rail fired accurately at a book that no longer existed, and the spot book
could not trade. That is the hardest kind of defect to see, so these tests pin both halves of the
fix: the marker makes the absence DELIBERATE, and the report keeps saying what is NOT covered.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_SRC = Path("scripts/run_live_guard.py")


def _guard() -> Any:
    spec = importlib.util.spec_from_file_location("run_live_guard_undertest", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_WITHOUT_THE_MARKER_AN_UNREADABLE_VENUE_STILL_FAILS_CLOSED(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PROPERTY THAT MUST SURVIVE THE FIX. A venue we cannot read is treated as naked. Losing
    this to make a spot desk quiet would disarm the rail for every desk that does have leverage."""
    g = _guard()
    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")

    class _Broken:
        def positions(self) -> dict[str, float]:
            raise OSError("venue unreachable")

        def open_orders(self) -> list[dict[str, Any]]:
            return []

    rep, note = g._reconcile(_Broken(), 0.0)
    assert rep.naked, "an unreadable venue must read as naked, not as clean"
    assert "fail-closed" in note


def test_THE_MARKER_MAKES_THE_ABSENCE_DELIBERATE(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With SPOT_ONLY the futures connector is not consulted at all -- so an account that cannot
    exist cannot be reported as an unreadable one."""
    g = _guard()
    marker = tmp_path / "SPOT_ONLY"
    marker.write_text("", "utf-8")
    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
    assert g._venue() is None
    rep, note = g._reconcile(None, 0.0)
    assert not rep.freeze_entries
    assert "SPOT_ONLY" in note


def test_THE_REPORT_STATES_WHAT_IT_DOES_NOT_COVER(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean §3 line beside a live spot book reads as 'the book is protected'. It is not: spot
    holdings carry no venue-side stop here. Silence is the more dangerous of the two reports."""
    g = _guard()
    marker = tmp_path / "SPOT_ONLY"
    marker.write_text("", "utf-8")
    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
    _, note = g._reconcile(None, 0.0)
    assert "OUTSIDE the" in note and "invariant" in note
    assert "drawdown, not liquidation" in note


def test_ONE_LEGGED_BY_DESIGN_IS_NOT_HALF_ARMED(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HALF-ARMED describes a cash-and-carry book that lost a leg, and it demotes the stage. A desk
    that never had a futures leg would be demoted every tick, forever, for a risk -- an unhedgeable
    perp position -- that cannot arise on it."""
    g = _guard()
    marker = tmp_path / "SPOT_ONLY"
    marker.write_text("", "utf-8")
    monkeypatch.setattr(g, "_SPOT_ONLY", marker)
    _, _, hazard = g._arming()
    assert hazard is None


def test_WITHOUT_THE_MARKER_HALF_ARMED_STILL_FIRES(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The carry desk's hazard must be untouched: futures armed without spot is a directional book
    wearing a hedged book's risk limits."""
    g = _guard()
    monkeypatch.setattr(g, "_SPOT_ONLY", tmp_path / "absent")
    monkeypatch.setattr(g, "_arming", g._arming)  # no-op; exercised through the real function

    src = _SRC.read_text("utf-8")
    assert "HALF-ARMED" in src, "the carry hazard was removed rather than scoped"
    assert "if _spot_only():" in src


def test_THE_MARKER_IS_A_PRINCIPAL_ACT_AND_NO_ORGAN_WRITES_IT() -> None:
    """Same class of file as LIVE_ENABLE and the kill switch: it changes what the rails believe,
    so nothing autonomous may create it."""
    src = _SRC.read_text("utf-8")
    assert "_SPOT_ONLY.write_text" not in src and "_SPOT_ONLY.touch" not in src
    assert "never by an organ" in src
    for other in Path("scripts").glob("*.py"):
        body = other.read_text("utf-8")
        assert 'SPOT_ONLY").write_text' not in body
        assert 'SPOT_ONLY").touch' not in body
