"""The hourly roster measures the admission scan when the supervisor has not.

MEASURED 2026-09-08 (trace of the promoted-scalp money path): only `pf_allocator --mode heavy`
runs `marginal_admission`; `fast` and `normal` carry the last heavy scan forward. The scan is
what lets a PROMOTION_CANDIDATE leave STANDBY (`promoter.reconcile_capital` reads it), and heavy
had exactly one scheduler -- the persistent MT5-ResearchSupervisor worker (cadence 3600s). If
that worker is dead or stalled, no scalp sleeve can ever go LIVE, and every artifact reads
healthy because `normal` keeps re-stamping the old scan as carried.

The hourly roster is on a clock the box owns (MT5-Hourly). It now asks for `heavy` whenever the
last MEASURED scan is missing or older than twice the supervisor's cadence. A scheduling
redundancy: no admission rule, threshold or budget changes.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402

NOW = datetime(2026, 9, 8, 18, 0, tzinfo=UTC)


def _art(tmp_path: Path, admission: dict | None) -> Path:
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"admission": admission} if admission is not None else {}), "utf-8")
    return p


def test_no_artifact_means_heavy(tmp_path: Path) -> None:
    assert hourly_cycle._allocator_mode_for_the_hour(tmp_path / "missing.json", NOW) == "heavy"


def test_an_unmeasured_scan_means_heavy(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "not measured on this clock", "candidates": {}})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_a_fresh_measured_scan_keeps_the_hourly_normal(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(minutes=50)).isoformat()})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "normal"


def test_a_scan_older_than_two_supervisor_passes_means_heavy(tmp_path: Path) -> None:
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(hours=2, minutes=1)).isoformat()})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_a_carried_scan_ages_from_its_real_measurement(tmp_path: Path) -> None:
    """`normal` re-stamps measured_utc? No -- it copies the old doc and adds carried_from, so
    the honest age is carried_from's. A carried scan must not read as fresh forever."""
    art = _art(tmp_path, {"status": "MEASURED",
                          "measured_utc": (NOW - timedelta(hours=5)).isoformat(),
                          "carried_from": (NOW - timedelta(hours=5)).isoformat(),
                          "carried_by": "normal"})
    assert hourly_cycle._allocator_mode_for_the_hour(art, NOW) == "heavy"


def test_the_window_is_twice_the_supervisor_cadence() -> None:
    assert hourly_cycle.ADMISSION_SCAN_MAX_AGE_S == 2 * 3600.0


def test_the_roster_leg_uses_the_chooser() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/pf_allocator.py", "--mode", _allocator_mode_for_the_hour()' in src
    # the executable call that pinned the mode is gone; the docstring that quotes it may stay
    assert '"research/pf_allocator.py", "--mode", "normal"))' not in src
