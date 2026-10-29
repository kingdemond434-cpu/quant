"""DATA-14: the ontology is never closed. A candidate class that RECURS -- seen in at least
MIN_RECURRENCE distinct sources or countries -- is promoted automatically into the extension file
with provenance, in the row shape the equivalence ontology's extension loader reads, and routed
to acquisition as an information-lane mission. The `frontier_unknowns` leg, which exited 1 every
hour on a relative import, now runs as a script. No network."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontier_intel import unknowns as U  # noqa: E402

NOW = datetime(2026, 10, 7, tzinfo=UTC)


def _rec(country: str, words: list[str], endpoints: int = 1) -> dict:
    return {"data_type": "UNCLASSIFIED", "endpoints": endpoints, "country": country,
            "candidate_words": words, "sample": ["a dataset"],
            "stages": {"DISCOVERED": "2026-10-01T00:00:00+00:00"}}


def test_a_class_seen_in_enough_sources_is_promoted_with_provenance(tmp_path):
    loop = {"a.example.de": _rec("DE", ["biodiversity"]),
            "b.example.fr": _rec("FR", ["biodiversity"]),
            "c.example.org": _rec("UNMEASURED", ["biodiversity", "lonely"]),
            "d.example.org": _rec("UNMEASURED", ["phenology"], endpoints=0)}   # prose: ignored
    rows = U.candidate_class_rows(loop, [])
    assert {r["name"] for r in rows} == {"biodiversity", "lonely"}
    ext = tmp_path / "ext.json"
    res = U.promote_recurring(rows, path=ext, now=NOW)
    assert res["promoted_now"] == ["information_class:biodiversity"]
    assert {"key": "information_class:lonely", "sources": 1, "countries": 0} in \
        res["below_threshold_top"]
    doc = json.loads(ext.read_text("utf-8"))
    row = doc["classes"][0]
    # the equivalence ontology extension's class-row shape
    assert {"group", "name", "terms", "layer", "cadence", "mandate_id", "part"} <= set(row)
    assert row["status"] == "PROMOTED_AUTO" and row["lifecycle"] == "MISSION_OPEN"
    prov = row["provenance"]
    assert prov["n_sources"] == 3 and prov["countries"] == ["DE", "FR"]
    assert prov["first_seen"] and prov["promoted_at"]
    assert doc["known"] == []


def test_promotion_is_additive_and_widens_provenance(tmp_path):
    ext = tmp_path / "ext.json"
    base = [{"axis": "information_class", "name": "tidal", "source": f"s{k}",
             "country": "UNMEASURED"} for k in range(3)]
    U.promote_recurring(base, path=ext, now=NOW)
    more = [{"axis": "information_class", "name": "tidal", "source": "s9", "country": "NO"}]
    res = U.promote_recurring(more, path=ext, now=NOW)
    assert res["widened"] == ["information_class:tidal"] and res["promoted_now"] == []
    res2 = U.promote_recurring([], path=ext, now=NOW)       # nothing seen: nothing removed
    assert res2["total_promoted"] == 1
    prov = json.loads(ext.read_text("utf-8"))["classes"][0]["provenance"]
    assert prov["n_sources"] == 4 and prov["countries"] == ["NO"]


def test_recurrence_by_countries_alone_promotes():
    rows = [{"axis": "actor", "name": "Some Capital", "source": "one.example", "country": c}
            for c in ("JP", "KR", "TW")]
    res = U.promote_recurring(rows, write=False, now=NOW)
    assert res["promoted_now"] == ["actor:Some Capital"]


def test_unmapped_capabilities_and_unknown_firms_are_candidates():
    rows = U.candidate_class_rows({}, [
        {"capability": "QUANTUM_ANNEALING", "source_url": "https://lab.example.jp/x",
         "claim": "Kumo Quant Research and Kumo Quant Research again", "at": "t"},
        {"capability": "MACRO", "source_url": "https://y.example.com/z", "claim": ""}])
    axes = {(r["axis"], r["name"]) for r in rows}
    assert ("capability", "quantum_annealing") in axes
    assert all(r["name"] != "macro" for r in rows)           # MACRO is in the ontology
    assert any(r["axis"] == "actor" for r in rows)
    assert all(r["country"] in ("JP", "UNMEASURED") for r in rows)


def test_promoted_classes_route_to_acquisition_as_linked_information_missions(tmp_path):
    from libs.ops.task_queue import INFORMATION, TaskQueue
    q = TaskQueue(tmp_path / "q.jsonl")
    classes = [{"group": "information_class", "name": "tidal", "terms": r"\btidal\b",
                "provenance": {"n_sources": 4}},
               {"group": "information_class", "name": "done", "terms": "x",
                "lifecycle": "MISSION_MET"}]
    res = U.route_missions(classes, q)
    assert res["queued"] == ["information_class:tidal"]
    assert U.route_missions(classes, q)["already_open"] == ["information_class:tidal"]
    t = next(iter(q.tasks().values()))
    assert t.lane == INFORMATION and t.kind == "acquire_class" and t.priority == 4
    assert {"info_kind": "acquire_class", "strategy_kind": "screen_class",
            "priority": 0.0} in q.links()


def test_a_met_mission_moves_the_class_lifecycle(tmp_path):
    ext = tmp_path / "ext.json"
    rows = [{"axis": "information_class", "name": "tidal", "source": f"s{k}",
             "country": "UNMEASURED"} for k in range(3)]
    U.promote_recurring(rows, path=ext, now=NOW)
    U.promote_recurring([], path=ext, now=NOW, met=["information_class:tidal"])
    assert json.loads(ext.read_text("utf-8"))["classes"][0]["lifecycle"] == "MISSION_MET"


def test_the_hourly_leg_runs_as_a_script_now():
    """It exited 1 every hour: `from . import` with no parent package."""
    got = subprocess.run([sys.executable, str(DESK / "frontier_intel" / "unknowns.py"),
                          "--dry-run"], capture_output=True, text=True, timeout=120,
                         cwd=str(ROOT), check=False)
    assert got.returncode == 0, got.stderr[-400:]
    assert "frontier unknowns:" in got.stdout
