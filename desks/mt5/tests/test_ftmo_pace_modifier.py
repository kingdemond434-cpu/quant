"""The FTMO pace modifier is two-sided, survival-capped, report-only, and neutral when unmeasured."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import ftmo_pace_modifier as fpm  # noqa: E402


def _pacing(gain: float, *, elapsed: int = 1, dm: float = 20.0, pp: float = 0.9) -> dict:
    eq = 100_000.0 + gain
    return {"status": "OK", "phase": "phase1",
            "progress": {"target_frac": 0.10, "target_usd": 10_000.0, "gained_usd": 0.0,
                         "gained_equity_usd": gain},
            "days": {"traded": elapsed - 1, "min_days": 4,
                     "min_days_left": max(0, 5 - elapsed), "weekdays_elapsed": elapsed},
            "plan": {"days_median": dm, "p_pass": pp},
            "room": {"daily_room_usd": 5_000.0 - max(0.0, -gain), "max_room_usd": eq - 90_000.0},
            "pace": {"verdict": "ON_PLAN"}}


def test_absent_report_is_unmeasured_and_neutral() -> None:
    doc = fpm.build(None)
    assert doc["status"] == fpm.UNMEASURED and doc["multiplier"] == 1.0
    assert doc["report_only"] is True and doc["consumer"] is None
    assert "allocator" in doc["intended_consumer"]


def test_missing_plan_is_unmeasured() -> None:
    p = _pacing(0.0)
    p["plan"] = {"why": "no allocator"}
    doc = fpm.build(p, n_paths=500)
    assert doc["status"] == fpm.UNMEASURED and doc["multiplier"] == 1.0


def test_two_sided_ahead_down_behind_up() -> None:
    ahead = fpm.build(_pacing(8_500.0, elapsed=10), n_paths=2000)
    behind = fpm.build(_pacing(500.0, elapsed=30), n_paths=2000)
    assert ahead["status"] == behind["status"] == "OK"
    assert ahead["multiplier"] <= 1.0
    assert behind["multiplier"] > 1.0
    assert behind["at_m"]["p_pass"] >= behind["at_1"]["p_pass"]


def test_survival_caps_the_pick() -> None:
    doc = fpm.build(_pacing(-372.14), n_paths=1000)
    assert doc["status"] == "OK"
    pick = next(r for r in doc["table"] if r["m"] == doc["multiplier"])
    assert pick["survives"] and pick["worst_day_usd"] <= doc["state"]["daily_room_usd"]
    assert doc["multiplier"] <= doc["survival_cap"]["max_m"]


def test_no_room_reports_grid_floor() -> None:
    doc = fpm.build(_pacing(-4_900.0), n_paths=500)
    assert doc["status"] == "SURVIVAL_BELOW_GRID" and doc["multiplier"] == fpm.GRID[0]


def test_write_is_atomic(tmp_path: Path) -> None:
    out = tmp_path / "FTMO_PACE_MODIFIER.json"
    fpm.write(fpm.build(None), out)
    assert json.loads(out.read_text("utf-8"))["report_only"] is True
    assert not list(tmp_path.glob(".*.tmp"))


def test_registered_two_sided_and_billed() -> None:
    from libs.portfolio.capital_modifiers import REGISTRY
    from libs.portfolio.rails import rail
    from research import missed_growth
    m = next(x for x in REGISTRY if x.name == "ftmo_pace")
    assert m.kind == "two_sided" and m.lo < 1.0 < m.hi
    assert rail("ftmo_pace").measure in missed_growth.MEASURES


def test_wired_as_an_hourly_leg() -> None:
    from libs.research import layers
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/ftmo_pace_modifier.py", "--once"' in src
    assert layers.LEG_LAYER["ftmo_pace_modifier"] == "sizing"
    reg = json.loads((_ROOT / "docs" / "research" / "experiment_contracts.json").read_text("utf-8"))
    assert "ftmo_pace_modifier" in reg["legs"]
