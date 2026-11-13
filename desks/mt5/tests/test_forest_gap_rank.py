"""Never-attempted grounds are worked by breadth gap; the yield ledger carries a 7-day window."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_data_yield as ady  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402


def test_gap_weight_reads_the_grounds_own_words() -> None:
    assert dfm.gap_weight({"name": "黄金 论坛", "region": "cn"}) == 4.0   # gold + 02-09 session
    assert dfm.gap_weight({"name": "x", "queries": ["Nikkei 225 open"], "region": "us"}) == 2.0
    assert dfm.gap_weight({"name": "x", "why": "USDJPY and gold", "region": "br"}) == 5.0
    assert dfm.gap_weight({"name": "金融 forum", "region": "cn"}) == 0.0   # finance, not gold
    assert dfm.gap_weight({"name": "plain", "region": "jp"}) == 0.0


def test_never_attempted_grounds_rank_by_gap_and_none_is_dropped() -> None:
    grounds = [{"name": "aaa exotic", "region": "tr", "weight": 1.0},
               {"name": "bbb plain", "region": "us", "weight": 1.0},
               {"name": "ccc gold blog", "region": "jp", "weight": 1.0},
               {"name": "ddd dax index", "region": "de", "weight": 1.0}]
    order = [g["name"] for g in dfm.schedule(grounds, 0)]
    assert order[:2] == ["ccc gold blog", "ddd dax index"]
    assert sorted(order) == sorted(g["name"] for g in grounds)


def test_vector_stats_keep_bounded_per_day_counts(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "deep_forest_vector_stats.json"
    old = {f"2026-10-{d:02d}": [1, 0, 0] for d in range(1, 21)}
    p.write_text(json.dumps({"vectors": {"g": {"attempts": 20, "daily": old}}}), "utf-8")
    monkeypatch.setattr(dfm, "_vector_stats_path", lambda: p)
    dfm._record_vector_stats([{"ground": "g", "claims": 3, "status": "PRODUCTIVE"}])
    dfm._record_vector_stats([{"ground": "g", "claims": 0, "status": "REACHED_NO_CLAIMS"}])
    daily = json.loads(p.read_text("utf-8"))["vectors"]["g"]["daily"]
    today = datetime.now(UTC).date().isoformat()
    assert daily[today] == [2, 1, 3] and len(daily) == dfm.DAILY_KEEP


def test_yield_rows_carry_the_seven_day_window_and_unmeasured_is_never_zero() -> None:
    now = datetime(2026, 11, 13, 20, tzinfo=UTC)
    frontier = {"vectors": {"new": {}, "old": {"attempts": 4, "outcome": "EMPTY"},
                            "live": {"attempts": 9, "outcome": "YIELDED"}}}
    stats = {"vectors": {
        "old": {"attempts": 4},
        "live": {"attempts": 9, "successes": 2, "rows": 7, "last_success": "2026-11-12T03:00:00",
                 "daily": {"2026-11-12": [3, 1, 5], "2026-11-10": [2, 1, 2],
                           "2026-11-01": [4, 0, 0]}}}}
    rows = ady.vectors(frontier, stats, now)["rows_by_vector"]
    assert rows["new"]["attempts_7d"] == 0 and rows["new"]["last_output_at"] == ""
    assert rows["old"]["attempts_7d"] == ady.UNMEASURED
    assert (rows["live"]["attempts_7d"], rows["live"]["successes_7d"],
            rows["live"]["rows_7d"]) == (5, 2, 7)
    assert rows["live"]["last_output_at"] == "2026-11-12T03:00:00"


def test_the_artifact_names_when_it_was_generated(tmp_path: Path) -> None:
    now = datetime(2026, 11, 13, 20, tzinfo=UTC)
    doc = ady.build(coverage=tmp_path / "c", frontier=tmp_path / "f", vector_stats=tmp_path / "v",
                    runs=tmp_path / "r", compute_ledger=tmp_path / "l", now=now)
    assert doc["generated_at"] == "2026-11-13T20:00:00+00:00"
