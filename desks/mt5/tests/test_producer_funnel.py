"""The producer funnel (BACKLOG row 58): stage yields, the named bottleneck, the RED fence.

Pins the rules that make it honest: an absent input is UNMEASURED and never GREEN; breadth
(distinct grid cells) is never read as a loss; the verdict stage is never named a bottleneck;
STUCK needs 24h of unmoved history; THROUGHPUT_FELL compares disjoint 24h windows; a RED producer
reaches the issue board with its bottleneck; the leg is wired.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import issue_board as ib  # noqa: E402
import producer_funnel as pf  # noqa: E402

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _yield_doc(at: datetime, rows: dict[str, tuple[float, float, float]]) -> dict:
    return {"generated_utc": _iso(at), "cells_owed": {"producers": [
        {"producer": k, "key": k, "cells_emitted_per_hour": e, "unique_cells_per_hour": u,
         "cells_to_judge_per_hour": j} for k, (e, u, j) in rows.items()]}}


def _census_doc(at: datetime, rows: dict[str, dict]) -> dict:
    return {"at": _iso(at), "producers": [
        {"producer": k, "key": k, "kind": "generator", "funnel": f} for k, f in rows.items()]}


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "CENSUS", tmp_path / "PRODUCTIVITY_CENSUS.json")
    monkeypatch.setattr(pf, "YIELD", tmp_path / "PRODUCER_YIELD.json")
    monkeypatch.setattr(pf, "STATE", tmp_path / "PRODUCER_FUNNEL_STATE.json")
    monkeypatch.setattr(pf, "OUT", tmp_path / "PRODUCER_FUNNEL.json")
    return tmp_path


def _put(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_absent_inputs_are_unmeasured_never_green(tree):
    doc, _ = pf.build(now=NOW, state={})
    assert doc["status"] == "UNMEASURED"
    assert set(doc["unmeasured"]) == {"stuck_lifetime", "stuck_window", "throughput_fell"}
    assert all("absent" in why for why in doc["unmeasured"].values())


def test_stale_census_is_named_and_no_movement_is_read_from_it(tree):
    _put(pf.CENSUS, _census_doc(NOW - timedelta(days=14), {"a": {"raw_cells": 5}}))
    doc, _ = pf.build(now=NOW, state={})
    assert doc["inputs"]["census"]["status"] == "STALE"
    assert "old" in doc["checks"]["stuck_lifetime"]["why"]
    # the stale counts are still published, stamped with the census's own time
    row = next(r for r in doc["producers"] if r["key"] == "a")
    assert row["lifetime"]["census_status"] == "STALE"


def test_verdict_stage_is_never_the_bottleneck_and_breadth_is_not_a_loss():
    life, basis = pf.lifetime_stages({
        "raw_mechanism_claims": 0, "raw_cells": 1000, "unique_cells": 3,
        "cells_reached_judge": 1000, "cells_judged": 900, "certificates": 1,
        "forward_enrolled": 1, "live_contribution": 0})
    assert basis.startswith("raw_cells")       # a generator has no claims stage
    stages = [s for s, _ in life]
    assert "unique_cells" not in stages and "minted_cells" not in stages
    tr = pf.stage_yields(life)
    b = pf.bottleneck(tr, life[0])
    # judged->certificates (0.0011) is the lowest yield, but it is the sealed judge's verdict
    assert b["stage"] == "reached_judge" and b["kind"] == "judge_queue"
    verdict = next(t for t in tr if t["from"] == "judged")
    assert "excluded_from_bottleneck" in verdict


def test_zero_input_is_no_output_not_a_zero_yield():
    life, _ = pf.lifetime_stages({"raw_cells": 0, "cells_reached_judge": 0})
    b = pf.bottleneck(pf.stage_yields(life), life[0])
    assert b["verdict"] == "NO_OUTPUT"
    tr = pf.stage_yields(life)
    assert all(t["yield"] == pf.UNMEASURED for t in tr)


def test_throughput_fell_is_red_and_reaches_the_issue_board(tree, monkeypatch):
    state: dict = {}
    _put(pf.YIELD, _yield_doc(NOW - timedelta(hours=24), {"moat": (90.0, 80.0, 90.0),
                                                          "steady": (5.0, 5.0, 5.0)}))
    _, state = pf.build(now=NOW - timedelta(hours=24), state=state)
    _put(pf.YIELD, _yield_doc(NOW, {"moat": (13.0, 13.0, 13.0), "steady": (5.0, 5.0, 5.0)}))
    doc, state = pf.build(now=NOW, state=state)
    assert doc["checks"]["throughput_fell"]["status"] == "MEASURED"
    red = {r["key"]: r for r in doc["red"]}
    assert set(red) == {"moat"}
    assert red["moat"]["red"][0]["check"] == "THROUGHPUT_FELL"
    assert doc["biggest_bottleneck"]["producer"] == "moat"
    assert doc["status"] == "RED"
    # onto the board, with its bottleneck named
    pf._write(pf.OUT, doc)
    rel = Path(ib.PRODUCER_FUNNEL)
    target = tree / "root" / rel
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(doc), encoding="utf-8")
    issues = ib.producer_funnel_issues(tree / "root")
    assert [i.key for i in issues] == ["producer_funnel:moat"]
    assert issues[0].severity == "STALLED" and "bottleneck" in issues[0].what
    assert not issues[0].auto


def test_window_stuck_needs_24h_of_readings(tree):
    state: dict = {}
    for h in (30, 20, 10, 0):
        at = NOW - timedelta(hours=h)
        _put(pf.YIELD, _yield_doc(at, {"lost": (4.0, 4.0, 0.0), "ok": (4.0, 4.0, 4.0)}))
        doc, state = pf.build(now=at, state=state)
    red = {r["key"]: r for r in doc["red"]}
    assert "lost" in red and "ok" not in red
    assert red["lost"]["red"][0]["check"] == "STUCK"
    assert red["lost"]["bottleneck"]["stage"] == "emitted"


def test_lifetime_stuck_reads_unmoved_counts_only_from_fresh_census(tree):
    state: dict = {}
    funnel = {"raw_cells": 500, "cells_reached_judge": 500, "cells_judged": 100,
              "certificates": 0, "forward_enrolled": 0, "live_contribution": 0}
    for h in (30, 12, 0):
        at = NOW - timedelta(hours=h)
        _put(pf.CENSUS, _census_doc(at, {"p": dict(funnel)}))
        doc, state = pf.build(now=at, state=state)
    assert doc["checks"]["stuck_lifetime"]["status"] == "MEASURED"
    red = {r["key"]: r for r in doc["red"]}
    assert red["p"]["red"][0]["stage"] == "reached_judge"
    assert red["p"]["red"][0]["waiting"] == 400


def test_unmeasured_fence_is_one_blind_issue(tree):
    doc, _ = pf.build(now=NOW, state={})
    target = tree / "root" / ib.PRODUCER_FUNNEL
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(doc), encoding="utf-8")
    issues = ib.producer_funnel_issues(tree / "root")
    assert [(i.key, i.severity) for i in issues] == [("producer_funnel:unmeasured", "BLIND")]


def test_main_writes_the_stamped_artifact_and_state(tree):
    assert pf.main(["--once"]) == 0
    doc = json.loads(pf.OUT.read_text(encoding="utf-8"))
    assert doc["at"] and doc["status"] in {"RED", "UNMEASURED", "GREEN"}
    assert pf.STATE.exists()


def test_the_leg_is_wired():
    import hourly_cycle as hc

    from libs.research.layers import LEG_LAYER

    assert "producer_funnel" in hc.CORE_LEGS
    assert hc.department_of("producer_funnel") == "meta"
    assert LEG_LAYER["producer_funnel"] == "meta"
    assert hc.LEG_BUDGET_SEC["producer_funnel"] >= 60
    assert any(name == "producer_funnel" for name, *_ in ib.CADENCE)
    sync = (BASE / "scripts" / "sync_shadow_to_git.ps1").read_text(encoding="utf-8")
    assert "desks/mt5/reports/PRODUCER_FUNNEL.json" in sync
