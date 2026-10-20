"""Per-shard publication: visible at once, counted once, and never a pass.

    python -m pytest desks/mt5/tests/test_shard_publication.py -q

`patches/judge_funnel_shards/B_shard_publication.patch` makes each shard of the sealed judge
publish its rows when its `rule` phase ends (IDEA_QUEUE 159); `research/shard_verdicts.py` reads
them. The reader tests run everywhere. The sealed-side tests SKIP until the patch is applied.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import shard_verdicts as sv  # noqa: E402


def _write(d: Path, name: str, rows: list[dict], token: str | None = None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(json.dumps({"schema": sv.SCHEMA, "token": token or d.name, "rows": rows}),
                 "utf-8")
    return f


def _row(cell: str, status: str = "FINAL", **kw) -> dict:
    base = {"cell": cell, "verdict_status": status,
            "passed": None if status == "PROVISIONAL" else False,
            "terminal_kind": "RULED", "terminal_gate_id": "in_sample_screen",
            "terminal_reason": "in_sample_screen: sharpe=-0.1"}
    base.update(kw)
    return base


def _age(path: Path, seconds_ago: float) -> None:
    t = time.time() - seconds_ago
    for p in [path, *path.rglob("*")]:
        os.utime(p, (t, t))


# ------------------------------------------------------------------ the reader (unsealed)
def test_nothing_published_is_unmeasured(tmp_path: Path) -> None:
    assert sv.in_flight(tmp_path / "absent")["status"] == "UNMEASURED"


def test_the_newest_unmerged_plan_is_in_flight_and_counted_once(tmp_path: Path) -> None:
    old = tmp_path / "aaaa"
    _write(old, "shard_0.json", [_row("c0")])
    (old / "MERGED.json").write_text(json.dumps({"merged_at": "x", "published_rows": 1,
                                                 "final_rows_agree": 1,
                                                 "final_rows_disagree": 0,
                                                 "absent_from_merge": 0}), "utf-8")
    _age(old, 3600)
    live = tmp_path / "bbbb"
    _write(live, "shard_0.json", [_row("c1"), _row("c2", "PROVISIONAL"),
                                  _row("c1")])                      # the same cell twice
    _write(live, "shard_1.json", [_row("c3", "REJECTED_TERMINAL_PENDING"),
                                  _row("c4", terminal_kind="UNMEASURED",
                                       terminal_gate_id="observations",
                                       terminal_reason="no_signals")])
    _write(live, "shard_plan.json", [_row("c5", terminal_gate_id="economic_prior")])
    got = sv.in_flight(tmp_path)
    assert got["status"] == "IN_FLIGHT" and got["token"] == "bbbb"
    assert got["rows"] == 5, "a cell met twice was counted twice"
    assert got["by_status"] == {"FINAL": 3, "PROVISIONAL": 1, "REJECTED_TERMINAL_PENDING": 1}
    assert got["final_by_terminal_gate_id"] == {"in_sample_screen": 1, "economic_prior": 1}
    assert got["final_unmeasured_by_reason"] == {"no_signals": 1}
    assert got["shards_published"] == ["0", "1", "plan"]
    assert got["last_merged"]["token"] == "aaaa"


def test_a_republished_shard_replaces_its_file_and_changes_no_count(tmp_path: Path) -> None:
    live = tmp_path / "cccc"
    rows = [_row(f"c{i}") for i in range(7)]
    _write(live, "shard_0.json", rows)
    first = sv.in_flight(tmp_path)
    _write(live, "shard_0.json", rows)                              # the retry
    assert sv.in_flight(tmp_path)["rows"] == first["rows"] == 7


def test_a_merged_plan_is_never_read_as_live_and_a_killed_one_is_abandoned(
        tmp_path: Path) -> None:
    killed = tmp_path / "dddd"
    _write(killed, "shard_0.json", [_row("k0")])
    _age(killed, 7200)
    done = tmp_path / "eeee"
    _write(done, "shard_0.json", [_row("d0")])
    (done / "MERGED.json").write_text("{}", "utf-8")
    got = sv.in_flight(tmp_path)
    assert got["status"] == "MERGED" and got["abandoned_plans"] == ["dddd"]


def test_a_row_that_claims_a_pass_is_refused(tmp_path: Path) -> None:
    live = tmp_path / "ffff"
    _write(live, "shard_0.json", [_row("ok"), _row("bad", "PROVISIONAL", passed=True),
                                  _row("odd", "SOMETHING")])
    got = sv.in_flight(tmp_path)
    assert got["rows"] == 1
    assert got["refused_rows"]["n"] == 2 and set(got["refused_rows"]["sample"]) == {"bad", "odd"}


def test_the_digest_carries_the_in_flight_block(tmp_path: Path) -> None:
    import gate_verdict_digest as gvd
    live = tmp_path / "pub" / "gggg"
    _write(live, "shard_0.json", [_row("c1")])
    doc = gvd.build(tmp_path / "none.jsonl", tmp_path / "none.json", shard_root=tmp_path / "pub")
    assert doc["in_flight"]["status"] == "IN_FLIGHT" and doc["in_flight"]["rows"] == 1


def test_no_promotion_path_reads_a_provisional_copy() -> None:
    """Certificates come from the merge's record only: nothing that promotes or admits names the
    publication directory or its reader."""
    names = ("shard_verdicts",)
    paths = [DESK / "research" / f for f in ("promoter.py", "shadow_admission.py",
                                             "survivor_publication.py", "canon_publication.py")]
    paths += [DESK / "mt5desk" / f for f in ("gateway.py",)]
    for path in paths:
        if path.exists():
            src = path.read_text("utf-8", errors="ignore")
            assert not any(n in src for n in names), f"{path.name} reads the provisional copy"


# ------------------------------------------------------------------ the sealed side
@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    if not hasattr(external_gauntlet, "_shard_verdict"):
        pytest.skip("B_shard_publication.patch is not applied to the sealed judge")
    return external_gauntlet


def _series(n: int, mu: float = 0.0):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(n)
    return pd.Series(rng.normal(mu, 1.0, n), index=pd.bdate_range("2020-01-01", periods=n))


def _stage(passed: bool) -> dict:
    return {"passed": passed, "x": 1.0}


def _cell(**local) -> dict:
    stages = {g: _stage(True) for g in ("economic_prior", "in_sample_screen", "cpcv",
                                        "walk_forward", "stress_costs", "expected_value",
                                        "swap_cost")}
    stages.update({g: _stage(v) for g, v in local.items() if g in stages})
    return {"sym": "EURUSD", "family": "carry", "params": {"i": 1}, "timeframe": "H1",
            "_local_stages": stages,
            "_local_program": {"dsr": (local.get("deflated_sharpe", True), 0.97, 0.1),
                               "lockbox": {"passed": local.get("lockbox", True)}}}


def test_a_shard_decides_only_what_precedes_the_program_level_gates(eg) -> None:
    full = _series(300)
    dev = full.iloc[:240]
    head = eg._shard_verdict(_cell(in_sample_screen=False, cpcv=False), full, dev, None)
    assert head["verdict_status"] == eg.VERDICT_FINAL and head["terminal_gate"] == \
        "in_sample_screen" and head["passed"] is False
    dsr = eg._shard_verdict(_cell(deflated_sharpe=False), full, dev, None)
    assert dsr["verdict_status"] == eg.VERDICT_FINAL and dsr["terminal_gate"] == \
        "deflated_sharpe"
    late = eg._shard_verdict(_cell(lockbox=False), full, dev, None)
    assert late["verdict_status"] == eg.VERDICT_REJECTED_PENDING and late["passed"] is False
    assert late["terminal_gate"] is None and late["local_failed_gates"] == ["lockbox"]
    clean = eg._shard_verdict(_cell(), full, dev, None)
    assert clean["verdict_status"] == eg.VERDICT_PROVISIONAL and clean["passed"] is None
    assert clean["pending_gates"] == list(eg.PROGRAM_LEVEL_GATES)


def test_without_the_shards_dsr_read_only_the_head_decides(eg) -> None:
    full = _series(300)
    c = _cell(cpcv=False)
    c.pop("_local_program")
    got = eg._shard_verdict(c, full, full.iloc[:240], None)
    assert got["verdict_status"] == eg.VERDICT_REJECTED_PENDING
    c2 = _cell(economic_prior=False)
    c2.pop("_local_program")
    assert eg._shard_verdict(c2, full, full.iloc[:240], None)["verdict_status"] == \
        eg.VERDICT_FINAL


def test_an_unjudgeable_cell_is_final_and_the_merges_row(eg) -> None:
    full = _series(80)
    c = {"sym": "EURUSD", "family": "carry", "params": {"i": 2}, "timeframe": "H1",
         "_n_signals": 4}
    got = eg._shard_verdict(c, full, full.iloc[:30], None)
    want = eg._unmeasured_verdict(c, full.iloc[:30], 80, screened=False)
    want.update(eg.terminal_stamp(want))
    assert got["verdict_status"] == eg.VERDICT_FINAL
    assert all(got[k] == want.get(k) for k in eg.PUBLISHED_FINAL_FIELDS)
    screened = dict(c, screen_read_until="2099-01-01")
    s = eg._shard_verdict(screened, full, full.iloc[:70], full.index[70])
    assert s["unknown_reason"] == "screened_past_cut" and s["days"] == 0


def test_a_publication_is_idempotent_and_never_passes(eg, tmp_path: Path) -> None:
    plan = {"token": "t0", "n": 2, "publication": {"dir": str(tmp_path)}}
    rows = [{"cell": "a", "verdict_status": "FINAL", "passed": False}]
    f1 = eg._publish_shard(plan, 0, [dict(r) for r in rows])
    body1 = json.loads(f1.read_text("utf-8"))
    f2 = eg._publish_shard(plan, 0, [dict(r) for r in rows])
    body2 = json.loads(f2.read_text("utf-8"))
    assert f1 == f2 and body1["rows"] == body2["rows"]
    assert sorted(p.name for p in (tmp_path / "t0").iterdir()) == ["shard_0.json"]
    with pytest.raises(eg.ShardMergeError):
        eg._publish_shard(plan, 1, [{"cell": "b", "verdict_status": "PROVISIONAL",
                                     "passed": True}])
    assert not (tmp_path / "t0" / "shard_1.json").exists()


def test_the_merge_checks_the_copy_and_counts_each_cell_once(eg, tmp_path: Path,
                                                             monkeypatch) -> None:
    plan = {"token": "t1", "n": 2, "publication": {"dir": str(tmp_path)}}
    final = [{"cell": "a", "passed": False, "terminal_gate": "cpcv", "stages": {}},
             {"cell": "b", "passed": False, "terminal_gate": "pbo", "stages": {}},
             {"cell": "c", "passed": True, "terminal_gate": "PASSED", "stages": {}}]
    eg.stamp_terminal(final)
    a = {k: final[0].get(k) for k in ("cell", *eg.PUBLISHED_FINAL_FIELDS)}
    eg._publish_shard(plan, 0, [{**a, "verdict_status": "FINAL"},
                                {"cell": "b", "verdict_status": "REJECTED_TERMINAL_PENDING",
                                 "passed": False}])
    eg._publish_shard(plan, 1, [{"cell": "c", "verdict_status": "PROVISIONAL", "passed": None},
                                {**a, "verdict_status": "FINAL"},          # a again: once
                                {"cell": "z", "verdict_status": "FINAL", "passed": False}])
    monkeypatch.setattr(eg, "_SHARD", {"publication": {"dir": str(tmp_path), "token": "t1"}})
    doc = eg._seal_shard_publication(final)
    assert doc["published_rows"] == 4
    assert (doc["final_rows_agree"], doc["final_rows_disagree"]) == (2, 0)
    assert doc["provisional_rows"] == 1 and doc["absent_from_merge"] == 1
    assert json.loads((tmp_path / "t1" / "MERGED.json").read_text("utf-8"))["token"] == "t1"
    final[0]["terminal_gate"] = "walk_forward"                     # the record moved
    assert eg._seal_shard_publication(final)["final_rows_disagree"] == 1


def test_the_merge_keeps_a_bounded_number_of_plans(eg, tmp_path: Path, monkeypatch) -> None:
    for i in range(eg.SHARD_PUBLISH_KEEP + 3):
        d = tmp_path / f"p{i}"
        _write(d, "shard_0.json", [])
        _age(d, 1000 - i)
    monkeypatch.setattr(eg, "_SHARD", {"publication": {"dir": str(tmp_path),
                                                       "token": f"p{eg.SHARD_PUBLISH_KEEP + 2}"}})
    eg._seal_shard_publication([])
    assert len([d for d in tmp_path.iterdir() if d.is_dir()]) == eg.SHARD_PUBLISH_KEEP


def test_publication_charges_no_trial_and_computes_no_program_statistic(eg) -> None:
    """The DSR bar a shard applies is the fixed per-cell bar; every census, PBO, SPA and
    multiplicity count stays in the merge, over the whole sweep."""
    banned = ("trial_ledger", "charged_trial_count", "fail_closed_trial_count",
              "structural_trial_census", "lifetime_trial_report", "calibrated_census_report",
              "probability_backtest_overfitting", "hansen_spa", "EXPERIMENT_LEDGER")
    for fn in (eg._shard_rule, eg._shard_verdict, eg._publish_shard, eg._final_published,
               eg._seal_shard_publication, eg._dsr_stage):
        src = inspect.getsource(fn)
        hit = [b for b in banned if b in src]
        assert not hit, f"{fn.__name__} reaches {hit}"
