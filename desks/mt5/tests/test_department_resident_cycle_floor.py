"""The gap between department passes is measured, never a constant, and only ever shrinks.

MEASURED ON THE TRADING BOX 2026-09-23/24. `MIN_CYCLE_S = 600` floored the START of one
department pass to ten minutes after the start of the last one. Thirteen forest departments
finish in a median of 130-270 seconds, so `europe` worked 183 s of every 600 and `japan` 22 s --
duty cycles of 30% and 4% imposed by a constant, while the desk's own processes measured 401% of
an 1800% CPU: four cores of eighteen, with fourteen idle. The floor's stated job is that an empty
department does not spin, and `PAUSE_S` already does that.

These tests pin the two properties that make lifting it safe: it is ONE WAY (the floor is only
ever lowered, never raised past `MIN_CYCLE_S`), and an UNMEASURED box keeps exactly the behaviour
this file has always had.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import department_resident as dr  # noqa: E402


def test_a_box_with_spare_cores_starts_the_next_pass_at_the_pause_floor(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 64_000.0)
    monkeypatch.setattr(dr, "spare_cores", lambda: 14.0)
    floor, why = dr.cycle_floor_s()
    assert floor == float(dr.PAUSE_S)
    assert floor < dr.MIN_CYCLE_S
    assert "idle" in why


def test_unmeasured_cores_keep_the_floor_this_file_has_always_had(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """UNMEASURED never licenses a faster loop (L1.28a)."""
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 64_000.0)
    monkeypatch.setattr(dr, "spare_cores", lambda: None)
    floor, why = dr.cycle_floor_s()
    assert floor == float(dr.MIN_CYCLE_S)
    assert "UNMEASURED" in why


def test_a_busy_box_keeps_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE LIVE TERMINAL ALWAYS WINS: under the core reserve, nothing runs sooner."""
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 64_000.0)
    monkeypatch.setattr(dr, "spare_cores", lambda: float(dr.IDLE_RESERVE_CORES) - 0.1)
    assert dr.cycle_floor_s()[0] == float(dr.MIN_CYCLE_S)


def test_thin_memory_keeps_the_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: dr.MIN_FREE_MB - 1.0)
    monkeypatch.setattr(dr, "spare_cores", lambda: pytest.fail("memory is checked first"))
    assert dr.cycle_floor_s()[0] == float(dr.MIN_CYCLE_S)


def test_the_floor_is_never_raised_above_the_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE WAY. No combination of measurements may make a department run LESS often."""
    for free in (None, 0.0, 64_000.0):
        for spare in (None, 0.0, 1.0, 18.0):
            monkeypatch.setattr(dr, "free_phys_mb", lambda free=free: free)
            monkeypatch.setattr(dr, "spare_cores", lambda spare=spare: spare)
            assert dr.cycle_floor_s()[0] <= float(dr.MIN_CYCLE_S)


def test_spare_cores_uses_psutil_never_cim() -> None:
    src = (_DESK / "research" / "department_resident.py").read_text("utf-8")
    assert "import psutil" in src
    for banned in ("Get-CimInstance", "wmic", "Win32_OperatingSystem"):
        assert banned not in src
