"""The persisted sweep plan: a restart resumes it, and re-plans only what changed (IDEA_QUEUE 159).

The sealed judge (`external_gauntlet`, patch `patches/judge_funnel_shards/B2_plan_resume`)
persists the plan a sharded sweep made and resumes it on restart while code, law and universe are
unchanged. These tests pin the rules of that resume at the unit level; the equality harness
(`fs_resume.py` in the patch directory) shows a killed-and-resumed sweep's records equal an
uninterrupted one's. They skip until the patch is applied to the sealed file.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    if not hasattr(external_gauntlet, "_resume_plan"):
        pytest.skip("B2_plan_resume.patch is not applied to the sealed judge")
    return external_gauntlet


@pytest.fixture
def shard(eg, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(eg, "_SHARD", {"n": 2, "dir": str(tmp_path / "shards"), "resume": True})
    (tmp_path / "shards").mkdir()
    monkeypatch.setattr(eg, "_plan_code_identity", lambda: "code-v1")
    return tmp_path


def _spec(i: int, **params) -> dict:
    return {"sym": "EURUSD", "family": "carry", "params": {"i": i, **params}, "timeframe": "H1"}


def _docket(path: Path, cells: dict) -> Path:
    path.write_text(repr(sorted(cells)) + repr([cells[k] for k in sorted(cells)]), "utf-8")
    return path


def _plan(eg, cells: dict, meta: dict) -> dict:
    """A plan the way `_plan_phase` shapes it, from the stand-in gate 0 and preflight."""
    elig, rej = eg.partition_at_economic_prior(list(cells.values()), meta)
    ready, blocked = eg._preflight_split(elig)
    return {"cells": cells, "meta": meta, "n_cells": len(cells), "eligible_specs": ready,
            "prior_rejections": rej, "blocked_build": blocked, "cell_objs": [], "deferred": [],
            "cache_hits": 0, "built_fresh": 0, "_mem_deferred": 0, "_build_t0": 1.0,
            "_built_syms": set(), "_cursor": 0, "_seen": {}, "_prewarm": {},
            "_remint_stale": []}


@pytest.fixture
def stand_ins(eg, monkeypatch):
    """Gate 0 advances `ok` cells; the preflight blocks `block` cells. Deterministic."""
    def partition(specs, meta):
        adv = [s for s in specs if s["params"].get("ok")]
        rej = [{"cell": eg._cid(s), "passed": False, "terminal_gate": "economic_prior"}
               for s in specs if not s["params"].get("ok")]
        return adv, rej

    def preflight(specs):
        return ([s for s in specs if not s["params"].get("block")],
                [{**s, "downstream_status": "NOT_RUN_MODIFIER"} for s in specs
                 if s["params"].get("block")])
    monkeypatch.setattr(eg, "partition_at_economic_prior", partition)
    monkeypatch.setattr(eg, "_preflight_split", preflight)


META = {"EURUSD": {"tick_size": 1e-5}}


def _cells(**over) -> dict:
    cells = {f"c{i}": _spec(i, ok=i % 3 != 0, block=i == 4) for i in range(8)}
    cells.update(over)
    return cells


def test_an_unchanged_docket_resumes_the_same_plan(eg, shard, stand_ins) -> None:
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    st = _plan(eg, cells, META)
    eg._persist_plan(st, surv)
    assert (shard / "shards" / eg.SWEEP_PLAN_NAME).exists()
    got = eg._resume_plan(cells, META, surv)
    assert got is not None
    assert got["plan_resume"]["resumed"] and got["plan_resume"]["docket_unchanged"]
    assert got["_build_t0"] > 1.0, "a resumed plan gets a fresh build budget"
    for k in ("eligible_specs", "prior_rejections", "blocked_build", "n_cells", "meta"):
        assert got[k] == st[k], k


@pytest.mark.parametrize("change", ["code", "meta", "age", "protocol"])
def test_a_plan_from_other_code_law_universe_or_time_is_re_made(eg, shard, stand_ins,
                                                                monkeypatch, change) -> None:
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    eg._persist_plan(_plan(eg, cells, META), surv)
    path = shard / "shards" / eg.SWEEP_PLAN_NAME
    meta = META
    if change == "code":
        monkeypatch.setattr(eg, "_plan_code_identity", lambda: "code-v2")
    elif change == "meta":
        meta = {**META, "GBPUSD": {"tick_size": 1e-5}}
    else:
        doc = eg._unpickle(path)                            # the judge's own reader
        if change == "age":
            doc["created_at"] = time.time() - eg.PLAN_RESUME_MAX_AGE_S - 60
        else:
            doc["protocol"] = -1
        eg._pickle_atomic(path, doc)
    assert eg._resume_plan(cells, meta, surv) is None
    assert not path.exists(), "a plan that may not resume is removed, never retried"


def test_a_changed_docket_re_plans_only_the_changed_cells(eg, shard, stand_ins) -> None:
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    st = _plan(eg, cells, META)
    eg._persist_plan(st, surv)
    new = dict(cells)
    new["c1"] = _spec(1, ok=True, block=False, w=9)        # changed, still advances
    new["c2"] = _spec(2, ok=False)                          # changed, now rejected at gate 0
    new["c3"] = _spec(3, ok=True)                           # changed, advances for the first time
    del new["c5"]                                           # removed
    new["c9"] = _spec(9, ok=True)                           # new to the docket
    surv = _docket(surv, new)
    got = eg._resume_plan(new, META, surv)
    assert got is not None and got["plan_resume"]["docket_unchanged"] is False
    rep = got["plan_resume"]
    assert (rep["cells_changed_replanned"], rep["cells_removed"],
            rep["cells_not_in_this_plan"]) == (3, 1, 1)
    planned = [eg._cid(s) for s in got["eligible_specs"]]
    old_order = [eg._cid(s) for s in st["eligible_specs"]]
    # c1 keeps its slot with its new spec; c2 and c5 leave; c3 joins the tail; c9 waits.
    want = [c for c in old_order if c not in {eg._cid(cells["c1"]), eg._cid(cells["c2"]),
                                              eg._cid(cells["c5"])}]
    want.insert(old_order.index(eg._cid(cells["c1"])), eg._cid(new["c1"]))
    want.append(eg._cid(new["c3"]))
    assert planned == want
    rejected = {r["cell"] for r in got["prior_rejections"]}
    assert eg._cid(new["c2"]) in rejected and eg._cid(cells["c3"]) not in rejected
    assert eg._cid(new["c9"]) not in planned and eg._cid(new["c9"]) not in rejected
    assert got["n_cells"] == len(new)
    # Every unchanged cell is exactly where the made plan put it: nothing else was re-planned.
    keep = [s for s in st["eligible_specs"] if eg._cid(s) in set(planned)]
    assert keep == [s for s in got["eligible_specs"] if s in st["eligible_specs"]]


def test_no_plan_is_kept_without_resume_or_under_reproduction(eg, shard, stand_ins,
                                                              monkeypatch) -> None:
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    monkeypatch.setattr(eg, "_SHARD", {"n": 2, "dir": str(shard / "shards")})
    eg._persist_plan(_plan(eg, cells, META), surv)
    assert not (shard / "shards" / eg.SWEEP_PLAN_NAME).exists()
    assert eg._resume_plan(cells, META, surv) is None
    monkeypatch.setattr(eg, "_SHARD", None)
    assert eg._sweep_plan_path() is None


def test_a_durable_merge_drops_what_a_resume_would_read(eg, shard) -> None:
    d = shard / "shards"
    for name in ("shard_0.pkl", "shard_1.pkl", "cut.pkl", eg.SWEEP_PLAN_NAME, "plan.pkl"):
        (d / name).write_bytes(b"x")
    assert eg._sweep_cleanup() == {"cleaned": 4}
    assert sorted(p.name for p in d.iterdir()) == ["plan.pkl"]


def test_a_shard_output_is_reused_only_on_an_equal_basis(eg, shard) -> None:
    d = shard / "shards"
    mine = [(0, _spec(0)), (2, _spec(2))]
    plan = {"token": "t", "n": 2, "code": "code-v1", "lockbox_frac": 0.2, "meta_digest": "m"}
    basis = eg._shard_basis(plan, mine)
    rows = [{"kind": "blocked", "idx": 0, "obj": {"downstream_status": "NOT_RUN_MODIFIER"}},
            {"kind": "blocked", "idx": 2, "obj": {"downstream_status": "NOT_RUN_MODIFIER"}}]
    for other in ({**basis, "code": "code-v0"}, {**basis, "specs": "another docket"},
                  {**basis, "lockbox_frac": 0.3}):
        eg._pickle_atomic(d / "shard_0.pkl", {"protocol": eg.SHARD_PROTOCOL, "phase": "build",
                                              "basis": other, "rows": rows})
        assert eg._resume_shard_build(d, plan, 0, mine, basis) is None
    eg._pickle_atomic(d / "shard_0.pkl", {"protocol": eg.SHARD_PROTOCOL, "phase": "build",
                                          "basis": basis, "rows": rows})
    got = eg._resume_shard_build(d, plan, 0, mine, basis)
    assert got is not None and got["resumed"]


@pytest.fixture
def v2(eg):
    if not hasattr(eg, "PLAN_RESUME_NAME"):
        pytest.skip("the funnel v2 sealed patch (15_funnel_B2_v2_fixes) is not applied")
    return eg


def test_a_budget_deferred_shard_is_rebuilt_under_the_fresh_budget(v2, shard) -> None:
    """audit of b94babf39: reusing it kept its deferred cells deferred despite the new budget."""
    eg, d = v2, shard / "shards"
    mine = [(0, _spec(0)), (2, _spec(2))]
    plan = {"token": "t", "n": 2, "code": "code-v1", "lockbox_frac": 0.2, "meta_digest": "m"}
    basis = eg._shard_basis(plan, mine)
    rows = [{"kind": "blocked", "idx": 0, "obj": {"downstream_status": "NOT_RUN_MODIFIER"}},
            {"kind": "deferred", "idx": 2, "obj": {}}]
    assert eg._rows_current(rows, mine) is False
    eg._pickle_atomic(d / "shard_0.pkl", {"protocol": eg.SHARD_PROTOCOL, "phase": "build",
                                          "basis": basis, "rows": rows})
    assert eg._resume_shard_build(d, plan, 0, mine, basis) is None


def test_a_resume_reads_seen_and_cursor_from_disk(v2, shard, stand_ins, monkeypatch) -> None:
    """audit of b94babf39: the pickled maps predate a kill between the ledger and the cleanup."""
    eg = v2
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    st = {**_plan(eg, cells, META), "_seen": {"old": "2026-10-01"}, "_cursor": {"EURUSD": "x"}}
    eg._persist_plan(st, surv)
    on_disk_seen, on_disk_cursor = {"old": "2026-10-01", "c-new": "2026-10-20"}, {"EURUSD": "y"}
    monkeypatch.setattr(eg, "_seen_cells", lambda: dict(on_disk_seen))
    monkeypatch.setattr(eg, "_build_cursor", lambda: dict(on_disk_cursor))
    got = eg._resume_plan(cells, META, surv)
    assert got["_seen"] == on_disk_seen and got["_cursor"] == on_disk_cursor
    assert got["eligible_specs"] == st["eligible_specs"], "the plan's order is unchanged"


def test_a_resume_writes_its_record_for_the_missed_growth_line(v2, shard, stand_ins) -> None:
    import json
    import os

    eg = v2
    cells = _cells()
    surv = _docket(shard / "docket.json", cells)
    eg._persist_plan(_plan(eg, cells, META), surv, plan_s=9729.04)
    new = {**cells, "c9": _spec(9, ok=True)}
    got = eg._resume_plan(new, META, _docket(surv, new))
    assert got is not None
    rec = json.loads((shard / "shards" / eg.PLAN_RESUME_NAME).read_text("utf-8"))
    assert rec["resumed"] is True and rec["pid"] == os.getpid() and rec["at"]
    assert rec["cells_not_in_this_plan"] == 1 and rec["plan_seconds_saved"] == 9729.0
    assert rec["max_age_s"] == eg.PLAN_RESUME_MAX_AGE_S and rec["planned_at"]
    eg._note_plan_resume(shards_reused=[1], build_seconds_saved=12.5)
    rec = json.loads((shard / "shards" / eg.PLAN_RESUME_NAME).read_text("utf-8"))
    assert rec["shards_reused"] == [1] and rec["cells_not_in_this_plan"] == 1
    # A plan that is made, not resumed, leaves no record of its own to bill.
    (shard / "shards" / eg.SWEEP_PLAN_NAME).unlink()
    assert eg._resume_plan(new, META, surv) is None and eg._PLAN_RESUME_DOC == {}
