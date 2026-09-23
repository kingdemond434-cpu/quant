"""The forward gate has two halves and the desk must be told which one binds.

THE DEFECT (measured 2026-08-29). `check_live_readiness` requires n >= MIN_FORWARD_TRADES AND
days >= MIN_FORWARD_DAYS, and published progress against DAYS alone: "best clock is day 2/14".
Every session and the principal read that as twelve days to first capital. The observation count
was the half that actually bound. Measured on the live box the day this shipped: all 17 active
clocks accrue almost exactly 1.00 observation per clock-day, because a session-scoped sleeve gets
one session a day -- so a clock holds n=14 on the day it reaches day 14, and true earliest
eligibility was day ~20, not day 14. A two-part gate reported by its non-binding part is a
progress bar pointing at the wrong wall, and the error is always in the optimistic direction.

NOTHING HERE MOVES A THRESHOLD. The bars are untouched (LAWS s4); only the distance-to-them
that the desk publishes about itself changes.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 8, 29, 5, 0, tzinfo=UTC)


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "check_live_readiness", _ROOT / "scripts" / "check_live_readiness.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod() -> ModuleType:
    return _load()


def _clock(days: float, n: int) -> dict[str, object]:
    """A shadow row whose forward_start is `days` before _NOW."""
    return {"n": n, "forward_start": (_NOW - timedelta(days=days)).isoformat()}


def test_the_live_rate_projects_past_the_day_bar(mod: ModuleType) -> None:
    """The measured case: 1 obs/day cannot reach n=20 by day 14, and must not claim to."""
    rows = mod.project_eligibility({"XAUUSD.asia": _clock(2, 2)}, _NOW)
    assert rows[0]["rate_per_day"] == 1.0
    assert rows[0]["eligible_day"] == 20.0, (
        "at one observation a day the OBSERVATION half binds six days past the time half")


def test_a_fast_clock_is_held_to_the_day_bar(mod: ModuleType) -> None:
    """Satisfying one half early never satisfies the other."""
    rows = mod.project_eligibility({"fast": _clock(2, 18)}, _NOW)
    assert rows[0]["eligible_day"] == float(mod.MIN_FORWARD_DAYS), (
        "n arrives on day ~2.2 but the window still has to be served")


def test_an_already_sufficient_clock_still_reports_the_day_floor(mod: ModuleType) -> None:
    rows = mod.project_eligibility({"done": _clock(3, mod.MIN_FORWARD_TRADES + 5)}, _NOW)
    assert rows[0]["eligible_day"] == float(mod.MIN_FORWARD_DAYS)


def test_a_silent_clock_projects_nothing_rather_than_something_optimistic(
        mod: ModuleType) -> None:
    """No observations means no evidenced arrival date. UNMEASURED, never a number."""
    rows = mod.project_eligibility({"silent": _clock(5, 0)}, _NOW)
    assert rows[0]["rate_per_day"] is None
    assert rows[0]["eligible_day"] is None


def test_a_brand_new_clock_projects_nothing(mod: ModuleType) -> None:
    rows = mod.project_eligibility({"newborn": _clock(0, 0)}, _NOW)
    assert rows[0]["eligible_day"] is None


def test_an_unstamped_clock_does_not_crash_and_earns_no_projection(mod: ModuleType) -> None:
    """`forward_days` fails closed on a missing stamp; the projection must inherit that."""
    rows = mod.project_eligibility({"unstamped": {"n": 9}}, _NOW)
    assert rows[0]["days"] == 0
    assert rows[0]["eligible_day"] is None


def test_slower_clocks_project_later(mod: ModuleType) -> None:
    """Monotonicity: half the rate is roughly twice the wait, and never a shorter one."""
    rows = {r["clock"]: r for r in mod.project_eligibility(
        {"quick": _clock(4, 4), "slow": _clock(4, 2)}, _NOW)}
    assert float(rows["slow"]["eligible_day"]) > float(rows["quick"]["eligible_day"])
    assert float(rows["quick"]["eligible_day"]) >= float(mod.MIN_FORWARD_DAYS)
