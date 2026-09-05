"""The forward window is DERIVED from the pre-registration stamp, never read back.

REPRODUCES THE DEFECT MEASURED ON DISK 2026-08-27. `desks/mt5/reports/shadow/shadow_state.json`
held 31 of 47 rows whose stored `days_active` outran their own `forward_start` by up to eight
days, because that field used to be computed from `first_entry` -- the first trade the sleeve
EVER took, including trades taken while the cell was still being selected. `shadow_forward` was
corrected to derive it, but only for rows it still enrols; every other consumer of the 14-day
forward gate read the stored field verbatim, so `check_live_readiness` published "best clock is
day 9/14" for a clock that had served ONE day, and a promote lane gating on `days_active >= 14`
would have cleared a window the sleeve never served (LAWS L1.6/L1.58, RESEARCH 6a).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops.forward_clock import (
    forward_days,
    overstated_rows,
    overstatement,
    served_window,
)

ROOT = Path(__file__).resolve().parent.parent

#: The row exactly as it sat in shadow_state.json: stamped 2026-08-25T23:26, first trade
#: 2026-08-17 08:00, and a stored day count of 9 counted from that first trade.
XAGUSD_LEVEL_BREAKOUT = {
    "status": "ACTIVE",
    "forward_start": "2026-08-25T23:26:08.836965+00:00",
    "days_active": 9,
    "n": 6,
    "exp_r": 0.05522716762995586,
    "first_entry": "2026-08-17 08:00:00+00:00",
}
NOW = datetime(2026, 8, 27, 1, 51, tzinfo=UTC)


def test_derives_one_day_not_the_stored_nine() -> None:
    assert forward_days(XAGUSD_LEVEL_BREAKOUT, NOW) == 1
    assert overstatement(XAGUSD_LEVEL_BREAKOUT, NOW) == 7


def test_unstamped_row_is_unmeasured_never_zero_days_served() -> None:
    row = {"status": "ACTIVE", "days_active": 20, "n": 60}
    assert forward_days(row, NOW) is None
    # UNMEASURED must fail the window CLOSED, never pass on the stored count (L1.28a).
    assert served_window(row, 14, NOW) is False


def test_a_stored_count_cannot_buy_a_window_the_stamp_denies() -> None:
    row = {"forward_start": (NOW - timedelta(days=1)).isoformat(), "days_active": 14}
    assert served_window(row, 14, NOW) is False
    row_served = {"forward_start": (NOW - timedelta(days=14)).isoformat(), "days_active": 0}
    assert served_window(row_served, 14, NOW) is True


def test_tolerance_absorbs_a_writer_reader_clock_skew_of_one_day() -> None:
    row = {"forward_start": (NOW - timedelta(days=5)).isoformat(), "days_active": 6}
    assert overstatement(row, NOW) is None
    row["days_active"] = 7
    assert overstatement(row, NOW) == 1


def test_overstated_rows_names_every_offender() -> None:
    rows = {
        "clean": {"forward_start": (NOW - timedelta(days=3)).isoformat(), "days_active": 3},
        "XAGUSD.level_breakout": XAGUSD_LEVEL_BREAKOUT,
        "unstamped": {"days_active": 40},
    }
    found = overstated_rows(rows, NOW)
    assert set(found) == {"XAGUSD.level_breakout"}
    assert found["XAGUSD.level_breakout"]["overstated_by"] == 7


def _load(script: str):
    """Import a scripts/ file by path WITHOUT changing cwd -- these modules resolve their data
    paths from __file__, so running them from a tmp dir would read and rewrite LIVE desk state."""
    spec = importlib.util.spec_from_file_location(f"_t_{script}", ROOT / "scripts" / script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_desk(tmp_path: Path, shadow_rows: dict) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports" / "shadow").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    (desk / "reports" / "shadow" / "shadow_state.json").write_text(
        json.dumps(shadow_rows), encoding="utf-8")
    (desk / "data" / "sleeve_registry.json").write_text(
        json.dumps({"sleeves": {"a": {"status": "OK"}}}), encoding="utf-8")
    (desk / "data" / "decay_live.json").write_text(
        json.dumps({"checked_at": datetime.now(tz=UTC).isoformat()}), encoding="utf-8")
    return desk


@pytest.mark.parametrize("stored_days", [14, 99])
def test_readiness_refuses_a_sleeve_whose_stamp_denies_the_window(tmp_path, stored_days) -> None:
    """The gate that says whether the desk may arm capital must not clear on a stored number."""
    mod = _load("check_live_readiness.py")
    row = {
        "status": "ACTIVE",
        "forward_start": (datetime.now(tz=UTC) - timedelta(days=1)).isoformat(),
        "days_active": stored_days,
        "n": 60,
        "exp_r": 0.4,
    }
    desk = _fake_desk(tmp_path, {"SLEEVE.window": row})
    mod.DESK = desk
    mod.OUT = tmp_path / "live_readiness.json"
    mod.main()
    report = json.loads(mod.OUT.read_text("utf-8"))

    assert report["checks"]["forward_evidence"]["pass"] is False, (
        "a sleeve one day into its pre-registered window cleared the 14-day forward gate on a "
        "stored day count -- this is the promotion the two-stage law exists to refuse")
    assert report["checks"]["chronology"]["overstated_day_counts"] == 1
    assert any("outruns their own pre-registration stamp" in r for r in report["blocking"])


def test_readiness_still_clears_a_sleeve_that_really_served_the_window(tmp_path) -> None:
    """The fix tightens; it must not accidentally block honest forward evidence."""
    mod = _load("check_live_readiness.py")
    row = {
        "status": "ACTIVE",
        "forward_start": (datetime.now(tz=UTC) - timedelta(days=20)).isoformat(),
        "days_active": 0,          # stored count deliberately useless
        "n": 60,
        "exp_r": 0.4,
    }
    desk = _fake_desk(tmp_path, {"SLEEVE.window": row})
    mod.DESK = desk
    mod.OUT = tmp_path / "live_readiness.json"
    mod.main()
    report = json.loads(mod.OUT.read_text("utf-8"))
    assert report["checks"]["forward_evidence"]["pass"] is True
    assert report["checks"]["forward_evidence"]["eligible_sleeves"] == ["SLEEVE.window"]


def test_positive_control_the_old_predicate_would_have_passed_this_row() -> None:
    """The control this fence was missing: show the PREVIOUS rule saying yes to the same row.

    A regression test that only exercises the corrected code proves the new code agrees with
    itself. This pins the disagreement -- if someone reverts to reading the stored field, the
    two predicates converge and this test fails.
    """
    row = {
        "status": "ACTIVE",
        "forward_start": (NOW - timedelta(days=1)).isoformat(),
        "days_active": 14,
    }
    old_predicate = int(row.get("days_active") or 0) >= 14      # what every consumer used to do
    new_predicate = served_window(row, 14, NOW)
    assert old_predicate is True, "control is not exercising the defect"
    assert new_predicate is False
