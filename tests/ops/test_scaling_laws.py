"""Survivors per compute hour, fitted in logs; a short ledger is UNMEASURED, never a slope."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.ops import scaling_laws as sl  # noqa: E402

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _days(n: int) -> list[str]:
    return [(NOW - timedelta(days=i)).date().isoformat() for i in range(n, 0, -1)]


def test_hours_and_survivors_are_bucketed_by_day() -> None:
    rows = [{"at": "2026-09-08T01:00:00+00:00", "wall_s": 3600},
            {"at": "2026-09-08T05:00:00+00:00", "wall_s": 1800},
            {"at": "2026-09-07T05:00:00+00:00", "wall_s": 7200},
            {"at": "bad", "wall_s": 999999}]
    assert sl.hours_by_day(rows) == {"2026-09-08": 1.5, "2026-09-07": 2.0}
    graph = [{"at": "2026-09-08T01:00:00+00:00", "fate": "BORN"},
             {"at": "2026-09-08T02:00:00+00:00", "fate": "CERTIFIED"},
             {"at": "2026-09-08T03:00:00+00:00", "fate": "BURIED"},
             {"at": "2026-09-08T04:00:00+00:00"}]
    assert sl.survivors_by_day(graph)["2026-09-08"] == {"born": 2, "certified": 1}


def test_a_short_ledger_is_unmeasured_and_says_why() -> None:
    hours = dict.fromkeys(_days(3), 1.0)
    law = sl.fit(hours, {})
    assert law["status"] == "UNMEASURED" and "below the 7" in law["why"]
    assert law["days_with_compute"] == 3


def test_linear_production_reads_as_an_elasticity_near_one() -> None:
    days = _days(12)
    hours = {d: float(i + 1) for i, d in enumerate(days)}
    # survivors + 1 exactly proportional to hours -> slope 1 in logs
    surv = {d: {"born": int(hours[d]) - 1, "certified": 0} for d in days}
    law = sl.fit(hours, surv)
    assert law["status"] == "MEASURED" and law["days_with_compute"] == 12
    assert law["born"]["elasticity"] == 1.0 and law["born"]["reading"] == "linear"
    assert law["born"]["r2"] == 1.0
    assert law["born"]["per_hour"] == round(law["born"]["total"] / law["total_hours"], 4)


def test_saturation_reads_as_diminishing_and_zero_days_are_kept() -> None:
    days = _days(12)
    hours = {d: float(i + 1) for i, d in enumerate(days)}
    surv = {d: {"born": int(math.sqrt(hours[d])) - 1, "certified": 0} for d in days}
    law = sl.fit(hours, surv)
    assert law["born"]["reading"] == "diminishing" and law["born"]["elasticity"] < 0.95
    zero_days = [d for d in days if surv[d]["born"] == 0]
    assert zero_days, "the fixture must contain a zero-survivor day for this test to bite"
    assert law["born"]["n_days"] == 12, "a zero-survivor day is a point, not a dropped row"


def test_no_variation_in_hours_is_unmeasured() -> None:
    days = _days(10)
    law = sl.fit(dict.fromkeys(days, 2.0), {d: {"born": 1, "certified": 0} for d in days})
    assert law["born"]["status"] == "UNMEASURED" and "no x variation" in law["born"]["why"]


def test_build_windows_the_data_and_names_the_absent_axes() -> None:
    old = (NOW - timedelta(days=90)).isoformat()
    doc = sl.build([{"at": old, "wall_s": 3600}], [{"at": old, "fate": "BORN"}], NOW)
    assert doc["law"]["status"] == "UNMEASURED" and doc["by_day"] == []
    assert doc["axes"]["tokens"].startswith("ABSENT") and doc["axes"]["data_volume"].startswith(
        "ABSENT")
    assert doc["axes"]["cpu_hours"].startswith("MEASURED")


def test_main_writes_the_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sl, "OUT", tmp_path / "scaling.json")
    monkeypatch.setattr(sl, "GRAPH", tmp_path / "graph.jsonl")
    assert sl.main([]) == 0
    doc = json.loads((tmp_path / "scaling.json").read_text("utf-8"))
    assert "law" in doc and "axes" in doc
