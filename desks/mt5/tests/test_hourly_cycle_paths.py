"""The hourly cycle must be able to import the desk's own packages BEFORE it uses them.

MEASURED 2026-08-27 on the desk box: 66 consecutive `tick tape FAILED: ModuleNotFoundError: No
module named 'mt5desk'` lines since the log was created on 08-22 -- five days of broker-native
ticks never recorded. `record_tape()` runs BEFORE `daily()`, and `daily_cycle` was the module
that happened to insert BASE into sys.path, so the tape import always arrived too early. A tick
nobody recorded is GONE: unlike a bar, it cannot be re-downloaded.
"""
from __future__ import annotations

from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
SRC = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")


def test_base_is_on_sys_path_before_any_function_runs() -> None:
    setup = SRC.split("def ", 1)[0]
    assert "sys.path.insert(0, _p)" in setup, "BASE is not put on sys.path at module level"
    assert "import sys" in setup


def test_the_tape_import_is_not_reached_before_the_path_is_set() -> None:
    """Order is the whole defect: the fix is worthless if the insert lands after first use.

    Matches the INDENTED statement, not the bare phrase -- the phrase also appears in the comment
    explaining the bug, and a test that matches prose instead of code proves nothing about code.
    """
    assert SRC.index("sys.path.insert(0, _p)") < SRC.index("\n        from mt5desk import")


def test_the_tape_failure_is_still_reported_not_swallowed() -> None:
    """It failed loudly for five days and nothing escalated it -- keep the line, and keep it
    findable, because the next import break will look exactly the same."""
    assert 'print(f"tick tape FAILED:' in SRC
