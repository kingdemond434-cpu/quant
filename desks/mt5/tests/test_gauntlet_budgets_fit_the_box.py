"""The gauntlet's budgets are sized for the box it runs on, and they cannot silently shrink.

MEASURED 2026-09-08: docket 23,465, reached a backtest 147, judged last pass 42. At 42 cells an
hour the docket needed 558 passes -- 23 days -- to judge work the miners had already delivered.
Both budgets that produced that number were "MEASURED 2026-09-05 on the 8GB research box"; the
principal reports the box at 80GB.

The memory floor was the dangerous one because it was SELF-TIGHTENING: budget = max(declared,
p75 of observed peaks), and a sweep that defers at the declared figure never records a higher
peak, so no run could ever raise it. A cap that measures only what it permitted is not a
measurement. These tests pin the new floors and the properties that make raising them safe.
"""
from __future__ import annotations

import re
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
SRC = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def _const(name: str) -> str:
    m = re.search(rf"^{name}\s*=\s*(.+)$", SRC, re.M)
    assert m, name
    return m.group(1).strip()


# ------------------------------------------------------------------------------ the new floors
def test_the_declared_memory_floor_is_sized_for_the_80gb_box() -> None:
    assert _const("DECLARED_NEED_MB") == "8192"


def test_the_build_budget_is_forty_five_minutes() -> None:
    assert _const("FRESH_BUILD_BUDGET_SEC") == \
        'float(os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700"))'


def test_the_build_budget_still_fits_the_hourly_cadence_with_room_for_the_gates() -> None:
    """The gates measured twelve minutes in the pure-cache regime. 45 + 12 < 60."""
    assert 2700 + 12 * 60 < 3600


# ------------------------------------------------------ the properties that make it safe to raise
def test_both_budgets_stay_env_overridable() -> None:
    """An operator with a measurement can move either without a commit."""
    assert 'os.environ.get("GAUNTLET_FRESH_BUDGET_SEC"' in SRC
    assert 'os.environ.get("GAUNTLET_MEMORY_BUDGET_MB")' in SRC


def test_the_floor_and_the_admission_ask_are_the_same_number() -> None:
    """Raising the throttle without raising what `exclusive_job` is told would let the sweep in
    on a false statement -- the exact thing the docstring beside the constant forbids."""
    assert 'measured_need_mb("external_gauntlet", DECLARED_NEED_MB)' in SRC
    assert "return float(DECLARED_NEED_MB)" in SRC     # the unmeasurable-box fallback


def test_an_unmeasurable_box_falls_back_to_the_declaration_never_to_unlimited() -> None:
    assert "an unmeasurable box must not have its throttle removed" in SRC


def test_the_reason_is_recorded_beside_the_number() -> None:
    """The next person to see 8192 must be able to see why it is not 1200 -- and that it was
    the principal's report of the box, not a measured peak."""
    assert "RAISED 1200 -> 8192 on 2026-09-08" in SRC
    assert "80GB" in SRC
    assert "SELF-TIGHTENING" in SRC
    assert "not a measured peak" in SRC


def test_it_fails_closed_on_a_box_that_does_not_have_the_room() -> None:
    assert "refused at the door rather than let in on a false statement" in SRC
