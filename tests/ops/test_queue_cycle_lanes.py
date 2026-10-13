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


# ---------------------------------------------------------------- the strategy-lane consumers
# Auditor HOLD on #289: `invalidate` and `screen_class` had no consumer, so READY rows piled up.

def _genome_and_repr(root: Path) -> None:
    data = root / "desks" / "mt5" / "data"
    (data / "feature_genome" / "genomes.json").write_text(json.dumps({
        "n": 2, "genomes": {"f_s1": {"feature_id": "f_s1"}, "f_s2": {"feature_id": "f_s2"}}}),
        "utf-8")
    rs = data / "representations"
    rs.mkdir(parents=True)
    (rs / "f_s1.json").write_text("{}", "utf-8")
    (rs / "manifest.json").write_text(json.dumps({"n": 1, "representations": [
        {"id": "f_s1", "file": "f_s1.json"}]}), "utf-8")


def test_invalidate_tasks_are_consumed_and_drop_only_the_stale_artifacts(tmp_path):
    _tree(tmp_path)
    _genome_and_repr(tmp_path)
    data = tmp_path / "desks" / "mt5" / "data"
    # the real control-plane schema carries `valid_until`; give the fixture store it
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    conn.execute("ALTER TABLE lineage_artifacts ADD COLUMN valid_until TEXT")
    conn.execute("UPDATE lineage_artifacts SET valid_until = '2099-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    q = TaskQueue(tmp_path / "q.jsonl")
    queue_cycle._lanes(tmp_path, q)
    ready = [t for t in q.tasks().values() if t.kind == "invalidate" and t.state == "READY"]
    assert len(ready) == 3
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["completed"]["invalidate"] == 3 and res["ready_left"] == 0 and not res["failed"]
    assert all(t.state == "DONE" for t in q.tasks().values() if t.kind == "invalidate")
    genomes = json.loads((data / "feature_genome" / "genomes.json").read_text("utf-8"))
    assert set(genomes["genomes"]) == set()                 # both features' versions moved
    manifest = json.loads((data / "representations" / "manifest.json").read_text("utf-8"))
    assert manifest["representations"] == [] and not (data / "representations" / "f_s1.json"
                                                      ).exists()
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    (until,) = conn.execute("SELECT valid_until FROM lineage_artifacts "
                            "WHERE artifact_id = 'cell:c_s1'").fetchone()
    conn.close()
    assert until < "2099"                                   # the cell's lease ended now
    log = [json.loads(x) for x in (data / "feature_genome" / "invalidations.jsonl")
           .read_text("utf-8").splitlines()]
    assert {r["artifact_id"] for r in log} == {"feature:f_s1", "feature:f_s2", "cell:c_s1"}


def test_an_invalidation_of_an_artifact_no_store_holds_is_not_held_and_still_completes(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.submit("invalidate", lane=STRATEGY, payload={"artifact_id": "feature:ghost",
                                                   "because": "dataset:x", "version": "v"})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"invalidate:NOT_HELD": 1} and res["ready_left"] == 0


def _class_registry(root: Path, rows: int, authority: bool = True) -> None:
    acq = root / "desks" / "mt5" / "data" / "acquired"
    acq.mkdir(parents=True, exist_ok=True)
    (acq / "registry.json").write_text(json.dumps({"series": {
        "bank_rate_jp": {"host": "www.boj.example.jp", "rows": rows, "pit_authority": authority},
        "unrelated": {"host": "other.example.org", "rows": 900, "pit_authority": True}}}),
        "utf-8")


def test_a_met_mission_spawns_a_class_screen_that_is_consumed(tmp_path):
    _class_registry(tmp_path, rows=500)
    q = TaskQueue(tmp_path / "q.jsonl")
    q.link("acquire_class", "screen_class")
    t = q.submit("acquire_class", lane=INFORMATION,
                 payload={"key": "information:policy_rates", "terms": "policy rate"},
                 dedupe_key="acquire_class|information:policy_rates")
    assert q.complete(t.id, produced={"source": "boj.example.jp"})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"screen_class:SCREENED": 1} and res["ready_left"] == 0
    screen = json.loads((tmp_path / "desks" / "mt5" / "reports" / "CLASS_SCREEN.json")
                        .read_text("utf-8"))["classes"]["information:policy_rates"]
    assert screen["vocabulary"] == ["ext_bank_rate_jp"]      # by host; `unrelated` not taken
    assert screen["screens"] == ["anomaly_miner", "family_discovered"]


def test_a_class_not_yet_eligible_is_rescreened_later_not_left_ready(tmp_path):
    _class_registry(tmp_path, rows=50)
    q = TaskQueue(tmp_path / "q.jsonl")
    q.submit("screen_class", lane=STRATEGY,
             payload={"key": "information:policy_rates", "produced": {"source": "boj.example.jp"}})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"screen_class:NOT_YET_ELIGIBLE": 1} and res["rearmed"] == 1
    assert res["ready_left"] == 0                           # the re-screen waits for its release
    again = [t for t in q.tasks().values() if t.kind == "screen_class" and t.state == "READY"]
    assert len(again) == 1 and again[0].not_before and again[0].payload["rearm"] == 1


def test_the_consumers_are_wired_into_the_hourly_cycle():
    src = (_ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert 'qcons = _costed("queue_consumers", lambda: _producer(' in src
    assert '"queue_consumers", "research/queue_consumers.py"))' in src
    assert '"queue_consumers": qcons' in src and '"queue_consumers": 300' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["queue_consumers"] == "meta"
    assert set(queue_cycle.CONSUMED_KINDS) == {"invalidate", "screen_class"}
