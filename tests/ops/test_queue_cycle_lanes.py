"""The `lanes` producer: a new data version becomes information work, which invalidates only its
lineage dependents in the strategy lane -- read from BOTH lineage stores -- and drains with no
idle gap. Fixture tree only; no network."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import queue_cycle  # noqa: E402
from libs.ops.task_queue import INFORMATION, STRATEGY, TaskQueue  # noqa: E402


def _tree(root: Path, *, rows_s1: int = 300) -> None:
    data = root / "desks" / "mt5" / "data"
    (data / "acquired").mkdir(parents=True)
    (data / "acquired" / "registry.json").write_text(json.dumps({
        "by_url": {},
        "series": {
            "s1": {"host": "stats.example.org", "rows": rows_s1, "last": "2026-10-01",
                   "acquired_at": "2026-10-06T08:30:00+00:00"},
            "s2": {"host": "stats.example.org", "rows": 500, "last": "2026-10-01",
                   "acquired_at": "2026-10-06T08:30:00+00:00"}}}), "utf-8")
    (data / "feature_genome").mkdir(parents=True)
    (data / "feature_genome" / "lineage.jsonl").write_text(
        json.dumps({"feature_id": "f_s1", "dataset_id": "s1"}) + "\n"
        + json.dumps({"feature_id": "f_s2", "dataset_id": "s2"}) + "\n", "utf-8")
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    conn.execute("CREATE TABLE lineage_artifacts (artifact_id TEXT, producer_component_id TEXT, "
                 "producer_run_id TEXT, created_at TEXT, input_artifact_ids TEXT)")
    conn.execute("INSERT INTO lineage_artifacts VALUES ('cell:c_s1', 'leg:x', 'r1', 't', "
                 "'feature:f_s1')")
    conn.commit()
    conn.close()
    (data / "catalog_routes").mkdir(parents=True)
    (data / "catalog_routes" / "roster.json").write_text(json.dumps({
        "defaults": {"min_gap_s": 2.0},
        "portals": [{"id": "p", "base": "https://stats.example.org", "route": "ckan"}]}), "utf-8")


def test_a_new_version_reaches_only_its_dependents(tmp_path):
    _tree(tmp_path)
    q = TaskQueue(tmp_path / "q.jsonl")
    first = queue_cycle._lanes(tmp_path, q)
    assert sorted(first["queued"]) == ["dataset:s1", "dataset:s2"]
    assert first["drained_information"] == 2              # drained, not left waiting
    assert first["lineage_rows"] == 3
    strat = [t for t in q.tasks().values() if t.lane == STRATEGY]
    by_cause: dict[str, set[str]] = {}
    for t in strat:
        by_cause.setdefault(t.payload["because"], set()).add(t.payload["artifact_id"])
    assert by_cause == {"dataset:s1": {"feature:f_s1", "cell:c_s1"},
                        "dataset:s2": {"feature:f_s2"}}
    assert q.rate_limits()["stats.example.org"]["per_s"] == 0.5

    # an unchanged pass queues nothing; a NEW version of s1 touches only s1's lineage
    assert queue_cycle._lanes(tmp_path, q)["queued"] == []
    _tree_dir = tmp_path / "desks" / "mt5" / "data" / "acquired" / "registry.json"
    reg = json.loads(_tree_dir.read_text("utf-8"))
    reg["series"]["s1"]["rows"] = 301
    _tree_dir.write_text(json.dumps(reg), "utf-8")
    before = {t.id for t in q.tasks().values()}
    third = queue_cycle._lanes(tmp_path, q)
    assert third["queued"] == ["dataset:s1"]
    new = [t for t in q.tasks().values() if t.id not in before and t.lane == STRATEGY]
    assert {t.payload["artifact_id"] for t in new} == {"feature:f_s1", "cell:c_s1"}
    assert third["untouched_total"] >= 1                   # f_s2 left alone and counted


def test_information_tasks_carry_the_release_time(tmp_path):
    _tree(tmp_path)
    q = TaskQueue(tmp_path / "q.jsonl")
    queue_cycle._lanes(tmp_path, q)
    info = [t for t in q.tasks().values() if t.lane == INFORMATION]
    assert info and all(t.not_before.startswith("2026-10-06T08:30") for t in info)


def test_the_lanes_producer_is_on_the_hourly_pass():
    assert "lanes" in queue_cycle.PRODUCERS and "lanes" in queue_cycle._IMPL


def test_the_lanes_sidecars_never_leave_the_box():
    ignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    for suffix in ("links.json", "limits.json", "buckets.json"):
        assert f"desks/mt5/data/task_queue.{suffix}" in ignore
