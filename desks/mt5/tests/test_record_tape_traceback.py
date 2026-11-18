"""A failing tape half must say WHERE it failed, not only what.

MEASURED on the box 2026-11-05 14:42Z: MT5-HourlyCore logged
`tick tape tape FAILED: FloatingPointError: overflow encountered in multiply` and nothing else.
`record_tape` caught the exception and printed only its message, so the failing line in
`mt5desk/tape.py` could not be named from the log and the fix could only be guessed. The leg must
print the traceback and record the innermost frame in its result.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _overflowing_tape() -> int:
    raise FloatingPointError("overflow encountered in multiply")


def test_tape_failure_names_its_line(monkeypatch, capsys) -> None:
    import hourly_cycle

    monkeypatch.setattr(hourly_cycle, "_tape_main", _overflowing_tape)
    monkeypatch.setattr(hourly_cycle, "_triangle_main", lambda: 0)
    res = hourly_cycle.record_tape()
    out = capsys.readouterr().out
    assert "tick tape tape FAILED: FloatingPointError" in out
    assert "Traceback (most recent call last)" in out
    assert "_overflowing_tape" in out
    assert res["tape_where"].startswith("test_record_tape_traceback.py:")
    assert res["tape_where"].endswith("in _overflowing_tape")
    # The two halves still keep separate verdicts: ticks failing never hides the triangle result.
    assert res["triangle_exit_code"] == 0
    assert res["exit_code"] == 1
