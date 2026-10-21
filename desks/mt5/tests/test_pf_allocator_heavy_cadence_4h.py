"""The allocator's HEAVY admission scan runs every 4th hour (2026-10-21), and nothing that
reads the scan's stamp expires it before the next heavy pass lands."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "research"))
sys.path.insert(0, str(HERE.parent))

import hourly_cycle  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 5, tzinfo=UTC)
#: The slack a consumer's expiry must clear above the cadence: one missed hourly pass plus margin.
SLACK_S = 1800.0


def _art(tmp_path: Path, age: timedelta) -> Path:
    p = tmp_path / "pf_allocation.json"
    p.write_text(json.dumps({"admission": {"status": "MEASURED",
                                           "measured_utc": (NOW - age).isoformat()}}), "utf-8")
    return p


def test_heavy_runs_once_every_four_hourly_passes(tmp_path: Path) -> None:
    # A scan stamped ~5 min into the 08:00 pass; the cycle then wakes at 09, 10, 11, 12.
    modes = [hourly_cycle._allocator_mode_for_the_hour(
        _art(tmp_path, timedelta(hours=h, minutes=-3)), NOW) for h in (1, 2, 3, 4)]
    assert modes == ["normal", "normal", "normal", "heavy"]


def test_cadence_is_four_hours() -> None:
    assert hourly_cycle.ADMISSION_SCAN_HEAVY_CADENCE_S == 4 * 3600.0
    assert 3 * 3600.0 < hourly_cycle.ADMISSION_SCAN_MAX_AGE_S <= 4 * 3600.0


def test_every_consumer_expiry_exceeds_the_heavy_cadence() -> None:
    import pf_allocator
    import promoter

    floor = hourly_cycle.ADMISSION_SCAN_HEAVY_CADENCE_S + SLACK_S
    assert pf_allocator.ADMISSION_MAX_AGE_S > floor
    assert promoter.ADMISSION_MAX_AGE_H * 3600.0 > floor
