"""Clockless certificates come from a per-certificate join, never from subtracting aggregates.

MEASURED ON THE BOX 2026-09-07, which is what settled it:

    authorized runnable certificates : 52
    passed enrolment                 : 52
    refused at enrolment             : 0
    forward rows across 4 lanes      : 101

The board was reporting 23 clockless certificates and telling the reader to search the
shadow_forward log for refusals -- refusals that were never issued, for certificates that were
all enrolled. The arithmetic was `certified - unrunnable - forward_clocks`, which is a correct
subtraction over the WRONG POPULATIONS: `certified` counts certificates, `forward_clocks` counts
rows that are NOT TERMINAL. A certificate whose clock was retired or killed is still certified
and no longer live, so it landed in the difference as work nobody could do.

Three states an enrolled certificate can be in, and only the first is a work item:

    NO ROW    nothing refused it and nothing exists -- the engine never reached it
    TERMINAL  retired or killed: DECIDED, not missing
    BLOCKED   a row exists and accrues nothing; the cure is bars, not enrolment
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import issue_board  # noqa: E402


def test_the_old_aggregate_subtraction_is_gone() -> None:
    """The exact expression that manufactured the phantom work item."""
    src = (DESK / "research" / "issue_board.py").read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "runnable - clocks" not in code
    assert "_clockless_by_join()" in code


def test_unmeasurable_returns_none_rather_than_zero() -> None:
    """A research container has no lane files.

    Reporting "none missing" there would be a pass earned by having no data -- the desk's
    standing rule is that an absent measurement is never a passing one.
    """
    assert issue_board._clockless_by_join() is None


def test_an_unmeasured_join_is_reported_not_silently_skipped() -> None:
    """UNMEASURED is a verdict. Falling back to the old subtraction would re-publish a number
    already known to be wrong, which is worse than publishing none."""
    src = (DESK / "research" / "issue_board.py").read_text("utf-8")
    assert "clockless certificates are UNMEASURED on this host" in src
    assert "check_enrolment_gap.py" in src


def test_the_detector_names_the_certificates_rather_than_counting_them() -> None:
    """'23 clockless, check the log' is not actionable; a list of names is."""
    src = (DESK / "research" / "issue_board.py").read_text("utf-8")
    assert "have no forward row at all" in src
    assert "Named: " in src
