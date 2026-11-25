"""Per-shard verdict publication (idea 45): a killed sweep keeps every finished shard's verdicts.

    python -m pytest desks/mt5/tests/test_judge_shard_publish.py -q

The sealed judge's `_run_shards` is driven end to end with an in-process dispatcher over a
synthetic docket: real `shard_worker` (build and rule), real `run_gauntlet` merge, real record
writers (hypothesis graph, gate ledger + index, seen cells). Only the per-cell build and the
cell-local stages are stand-ins, so each cell's outcome is chosen by its params. The record files
live under tmp_path.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

eg = pytest.importorskip("external_gauntlet")
from libs.research import hypothesis_graph as hg  # noqa: E402
from libs.research import preregistration as pr  # noqa: E402

N_SHARDS = 3
META: dict = {}


def _stage(ok: bool, **kw) -> dict:
    return {"passed": bool(ok), **kw}


def _local_stages(c, arr, x3, meta):
    """Stand-in cell-local gates: the cell's params say which one fails."""
    fail = str((c.get("params") or {}).get("fail") or "")
    return {g: _stage(g != fail, value=round(float(np.mean(arr)), 6))
            for g in (*eg.CELL_LOCAL_HEAD, *eg.CELL_LOCAL_MID, *eg.CELL_LOCAL_TAIL)}


def _series(i: int, days: int):
    rng = np.random.default_rng(1000 + i)
    idx = pd.bdate_range(end="2026-06-30", periods=days)
    return pd.Series(rng.normal(0.0005, 0.01, days), index=idx)


def _build_specs(specs, meta, t0, s0, s0v, built, blocked, *, cell_objs, deferred,
                 cache_hits, built_fresh, _mem_deferred):
    """Stand-in build: every spec is a cached cell with a synthetic series."""
    for sp in specs:
        days = int(sp["params"].get("days", 400))
        ds = _series(int(sp["params"]["i"]), days)
        cell_objs.append({"sym": sp["sym"], "family": sp["family"], "params": sp["params"],
                          "timeframe": "H1", "df": None, "sigs": None, "costs": None,
                          "_cached_ds": ds, "_cached_ds3": ds - 0.0002, "_ckey": None,
                          "_last_day": ds.index[-1]})
        cache_hits += 1
    return {"cell_objs": cell_objs, "deferred": deferred, "cache_hits": cache_hits,
            "built_fresh": built_fresh, "mem_deferred": _mem_deferred}


def _docket() -> list[dict]:
    """Head failures (FINAL), mid failures (pending), clean cells (provisional), short cells
    (UNMEASURED), across two symbols so every shard holds a mix."""
    out = []
    kinds = [{"fail": "in_sample_screen"}, {"fail": "economic_prior"}, {"fail": "cpcv"},
             {"fail": "swap_cost"}, {}, {"days": 50}]
    for i in range(36):
        out.append({"sym": ("EURUSD", "XAUUSD")[i % 2], "family": "carry",
                    "params": {"i": i, **kinds[i % len(kinds)]}})
    return out


def _make_env(tmp_path: Path, monkeypatch) -> dict:
    rec = tmp_path / "rec"
    rec.mkdir()
    monkeypatch.setattr(eg, "GATE_LEDGER", rec / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(eg, "GATE_INDEX", rec / "gate_verdict_index.json")
    monkeypatch.setattr(eg, "SEEN_CELLS", rec / "gauntlet_seen_cells.json")
    monkeypatch.setattr(pr, "LEDGER", rec / "preregistrations.jsonl")
    graph_path = rec / "hypothesis_graph.jsonl"
    monkeypatch.setattr(eg, "_verdict_graph", lambda: hg.Graph(graph_path))
    monkeypatch.setattr(eg, "_build_specs", _build_specs)
    monkeypatch.setattr(eg, "_cell_local_stages", _local_stages)
    monkeypatch.setattr(eg, "lifetime_trial_report", lambda fams: {
        "status": "MEASURED", "lifetime_trials": 1000, "family_trials": {}})
    return {"root": tmp_path, "rec": rec, "graph": graph_path, "pub": tmp_path / "pub"}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    return _make_env(tmp_path, monkeypatch)


def _dispatch(*, kill_after: int | None = None):
    """In-process launcher: every shard in order; in `rule`, the launcher's hook after each
    clean exit. `kill_after=k` dies (SystemExit) once k rule shards have finished and been
    published -- the drain is disabled by the caller to make it a hard kill."""
    def dispatch(shard_dir, n, phase):
        for k in range(n):
            if phase == "rule" and kill_after is not None and k >= kill_after:
                pub = eg._PUBLISHER
                end = time.monotonic() + 30
                while pub is not None and len(pub.done) < kill_after and time.monotonic() < end:
                    time.sleep(0.02)
                raise SystemExit("killed")
            eg.shard_worker(shard_dir, k, phase)
            if phase == "rule":
                assert eg.publish_finished_shard(shard_dir, k, phase)
    return dispatch


def _sweep(env, monkeypatch, *, publish: bool = True, kill_after: int | None = None,
           seen: dict | None = None, tag: str = "s"):
    """One sweep: shards (with publication), then the merge's record step exactly as `main`
    orders it. Returns (seen, merged verdicts or None when killed)."""
    seen = eg._seen_cells() if seen is None else seen
    specs = _docket()
    monkeypatch.setattr(eg, "_SHARD", {"n": N_SHARDS, "dispatch": _dispatch(kill_after=kill_after),
                                       "dir": env["root"] / f"shards-{tag}", "publish": publish,
                                       "publish_dir": env["pub"]})
    try:
        got = eg._run_shards(specs, META, time.time(), seen=seen)
    except SystemExit:
        return seen, None
    cells = got["cell_objs"]
    result = eg.run_gauntlet(cells, "external_discoveries", META)
    verdicts = result["verdicts"]
    graph = hg.Graph(env["graph"])
    eg.record_gauntlet_verdicts(verdicts, {eg.cell_id(c): c for c in cells},
                                first_judged=seen, graph=graph)
    eg._append_gate_ledger(verdicts, cells)
    eg._save_seen_cells(seen, {str(v.get("cell") or "") for v in verdicts
                               if isinstance(v, dict) and v.get("passed") is not None})
    if publish:
        eg._seal_shard_publication(verdicts)
    return seen, verdicts


def _ledger(env) -> list[dict]:
    p = env["rec"] / "gate_verdict_ledger.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


def _graph_latest(env) -> dict:
    p = env["graph"]
    out: dict = {}
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            r = json.loads(ln)
            out[r["id"]] = (r.get("fate"), r.get("terminal_gate"), r.get("prereg_status"))
    return out


def _shard_of_cell(specs, n):
    return {eg.cell_id({**s, "timeframe": "H1"}): eg.shard_of(s, n) for s in specs}


# ------------------------------------------------------------------ the three properties
def test_a_sweep_killed_after_shard_k_leaves_k_shards_final_verdicts_in_the_ledger(
        env, monkeypatch) -> None:
    k = 2
    monkeypatch.setattr(eg._ShardPublisher, "drain", lambda self: {"shards_published": []})
    seen, merged = _sweep(env, monkeypatch, kill_after=k)
    assert merged is None, "the sweep was killed before its merge"
    eg._PUBLISHER = None
    rows = _ledger(env)
    assert rows, "a killed sweep published nothing"
    owner = _shard_of_cell(_docket(), N_SHARDS)
    assert {owner[r["cell"]] for r in rows} == set(range(k)), "only the finished shards publish"
    # Exactly the FINAL rows, never a pending one: head failures and the unmeasured.
    assert {r["terminal_gate"] for r in rows} <= {"in_sample_screen", "economic_prior", "UNKNOWN"}
    assert not any(r["passed"] for r in rows)
    assert {r["cell"] for r in rows} <= set(seen), "a durable verdict is stamped judged"
    # The next reader sees each finished shard's staged copy, all three statuses.
    plan = next(d for d in env["pub"].iterdir() if d.is_dir())
    staged = sorted(f.name for f in plan.glob("shard_*.json"))
    assert staged == [f"shard_{i}.json" for i in range(k)]
    statuses = Counter(r["verdict_status"] for f in plan.glob("shard_*.json")
                       for r in json.loads(f.read_text("utf-8"))["rows"])
    assert set(statuses) == {eg.VERDICT_FINAL, eg.VERDICT_REJECTED_PENDING,
                             eg.VERDICT_PROVISIONAL}
    assert not (plan / "MERGED.json").exists()


def test_a_rerun_after_the_kill_records_each_verdict_once(env, monkeypatch) -> None:
    real_drain = eg._ShardPublisher.drain
    monkeypatch.setattr(eg._ShardPublisher, "drain", lambda self: {"shards_published": []})
    seen, _ = _sweep(env, monkeypatch, kill_after=2, tag="a")
    eg._PUBLISHER = None
    first = _ledger(env)
    # The killed sweep never saved its index past the first append: the next load must fold the
    # ledger's tail rather than re-append those rows.
    monkeypatch.setattr(eg._ShardPublisher, "drain", real_drain)
    _seen2, merged = _sweep(env, monkeypatch, seen=eg._seen_cells(), tag="b")
    assert merged is not None
    rows = _ledger(env)
    per_cell = Counter(r["cell"] for r in rows)
    assert max(per_cell.values()) == 1, f"a verdict was written twice: {per_cell.most_common(3)}"
    assert rows[:len(first)] == first, "the ledger is append-only"
    # And once more, a whole repeat sweep: nothing changed, nothing is appended.
    n = len(rows)
    _sweep(env, monkeypatch, seen=eg._seen_cells(), tag="c")
    assert len(_ledger(env)) == n


def test_a_complete_sweep_ends_in_the_same_record_with_or_without_publication(
        tmp_path, monkeypatch) -> None:
    ends = []
    for publish in (False, True):
        root = tmp_path / ("pub" if publish else "plain")
        root.mkdir()
        with monkeypatch.context() as m:
            e = _make_env(root, m)
            seen, verdicts = _sweep(e, m, publish=publish)
            led = sorted(json.dumps({k: v for k, v in r.items() if k != "at"}, sort_keys=True)
                          for r in _ledger(e))
            idx = json.loads((e["rec"] / "gate_verdict_index.json").read_text("utf-8"))
            ends.append({"ledger": led, "index": idx, "graph": _graph_latest(e),
                         "seen": sorted(seen), "verdicts": [
                             (v["cell"], v["passed"], v.get("terminal_gate"),
                              v.get("unknown_reason")) for v in verdicts]})
            if publish:
                plan = next(d for d in e["pub"].iterdir() if d.is_dir())
                merged = json.loads((plan / "MERGED.json").read_text("utf-8"))
                assert merged["final_rows_disagree"] == 0 and merged["final_rows_agree"] > 0
                assert merged["absent_from_merge"] == 0
    plain, published = ends
    assert published["verdicts"] == plain["verdicts"], "the merge's verdicts moved"
    assert published["ledger"] == plain["ledger"]
    assert published["index"] == plain["index"]
    assert published["graph"] == plain["graph"]
    assert published["seen"] == plain["seen"]


# ------------------------------------------------------------------ the rules around them
def test_a_failed_wave_still_publishes_the_shards_that_finished(env, monkeypatch) -> None:
    """A wave that RAISES (a shard that never recovers) runs the drain: what finished is kept."""
    def dispatch(shard_dir, n, phase):
        for k in range(n):
            if phase == "rule" and k == 1:
                raise RuntimeError("rule shard 1 failed after 3 attempt(s); refusing partial merge")
            eg.shard_worker(shard_dir, k, phase)
    monkeypatch.setattr(eg, "_SHARD", {"n": N_SHARDS, "dispatch": dispatch,
                                       "dir": env["root"] / "shards", "publish_dir": env["pub"]})
    with pytest.raises(RuntimeError):
        eg._run_shards(_docket(), META, time.time(), seen={})
    owner = _shard_of_cell(_docket(), N_SHARDS)
    assert {owner[r["cell"]] for r in _ledger(env)} == {0}
    assert eg._PUBLISHER is None


def test_no_staged_row_passes_and_no_pending_cell_reaches_the_record(env, monkeypatch) -> None:
    monkeypatch.setattr(eg._ShardPublisher, "drain", lambda self: {"shards_published": []})
    _sweep(env, monkeypatch, kill_after=N_SHARDS)
    eg._PUBLISHER = None
    plan = next(d for d in env["pub"].iterdir() if d.is_dir())
    staged = [r for f in plan.glob("shard_*.json")
              for r in json.loads(f.read_text("utf-8"))["rows"]]
    assert len(staged) == len(_docket())
    assert not any(r["passed"] is True for r in staged)
    final = {r["cell"] for r in staged if r["verdict_status"] == eg.VERDICT_FINAL}
    assert {r["cell"] for r in _ledger(env)} == final
    graph = _graph_latest(env)
    assert all(fate == hg.FAILED for fate, _g, _p in graph.values())


def test_a_shard_with_no_judgeable_cell_leaves_its_unmeasured_rows_to_the_merge() -> None:
    c = {"sym": "EURUSD", "family": "carry", "params": {"i": 1}, "timeframe": "H1",
         "_n_signals": 3}
    full = _series(1, 50)
    alone = eg._shard_verdict(c, full, full, union_judges=False)
    assert alone["verdict_status"] == eg.VERDICT_PROVISIONAL and alone["passed"] is None
    final = eg._shard_verdict(c, full, full, union_judges=True)
    want = eg._unmeasured_verdict(c, full, 50)
    assert final["verdict_status"] == eg.VERDICT_FINAL and final["verdict"] == want


def test_the_gate_index_catches_up_from_the_ledger(env) -> None:
    v = {"cell": "EURUSD.carry.p=1", "sym": "EURUSD", "family": "carry", "passed": False,
         "terminal_gate": "cpcv", "params": {"i": 1}}
    assert eg._append_gate_ledger([dict(v)])["appended"] == 1
    idx = eg._load_gate_index()
    # A kill between the ledger append and the index write: the row is in the ledger only.
    eg._append_gate_ledger([dict(v, terminal_gate="walk_forward")], idx=idx, save_index=False)
    assert eg._append_gate_ledger([dict(v, terminal_gate="walk_forward")])["appended"] == 0
    # A torn last line is skipped on load and the next append starts on a fresh line.
    with eg.GATE_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write('{"at": "x", "cell": "torn')
    assert eg._append_gate_ledger([dict(v, cell="GBPUSD.carry.p=2")])["appended"] == 1
    lines = eg.GATE_LEDGER.read_text("utf-8").splitlines()
    assert json.loads(lines[-1])["cell"] == "GBPUSD.carry.p=2"


def test_the_publisher_charges_no_trial_and_computes_no_program_statistic() -> None:
    import inspect

    banned = ("charged_trial_count", "fail_closed_trial_count", "structural_trial_census",
              "lifetime_trial_report", "calibrated_census_report", "charged_lifetime_trials",
              "probability_backtest_overfitting", "hansen_spa", "deflated_sharpe_ratio",
              "lockbox_stage", "UNIVERSAL_SURVIVORS", "all_ten_pass")
    for fn in (eg._shard_rule, eg._shard_verdict, eg._publish_shard, eg._ShardPublisher,
               eg.publish_finished_shard, eg._seal_shard_publication):
        src = inspect.getsource(fn)
        hit = [b for b in banned if b in src]
        assert not hit, f"{getattr(fn, '__name__', fn)} reaches {hit}"


def test_the_launcher_queues_the_publication_only_for_a_clean_rule_exit(monkeypatch) -> None:
    from scripts import run_sharded_gauntlet as runner

    calls = []
    monkeypatch.setattr(eg, "publish_finished_shard",
                        lambda d, k, phase: calls.append((k, phase)) or True)
    monkeypatch.setitem(sys.modules, "scripts.external_gauntlet", eg)
    monkeypatch.setattr(runner, "run", lambda *a, **k: None)
    runner.dispatch(Path("/nonexistent-shards"), 3, "rule")
    runner.dispatch(Path("/nonexistent-shards"), 2, "build")
    assert sorted(calls) == [(0, "rule"), (1, "rule"), (2, "rule")]

    def boom(argv, **kw):
        raise RuntimeError("child died")
    calls.clear()
    monkeypatch.setattr(runner, "run", boom)
    monkeypatch.setattr(runner, "_retry_attempts", lambda: 0)
    with pytest.raises(RuntimeError):
        runner.dispatch(Path("/nonexistent-shards"), 2, "rule")
    assert calls == [], "a failed shard is never published by the hook"


def test_a_killed_trees_lock_is_released_whichever_pid_stamped_it(tmp_path, monkeypatch) -> None:
    """The venv shim: the resident knows the shim's pid, the lock carries the interpreter's."""
    import socket

    from scripts import run_sharded_gauntlet as runner

    monkeypatch.setattr(runner, "_lock_root", lambda: tmp_path)
    lock = tmp_path / "certification_lane.json"
    host = socket.gethostname()
    lock.write_text(json.dumps({"pid": 2_000_002, "host": host}))
    monkeypatch.setattr(runner, "_gone", lambda pid: pid == 2_000_002)
    assert runner._release_locks_of(2_000_001) == [] and lock.exists(), "unrelated pid kept"
    assert runner._release_locks_of(2_000_001, [2_000_001, 2_000_002]) == ["certification_lane"]
    lock.write_text(json.dumps({"pid": 2_000_003, "host": host}))
    assert runner._release_locks_of(2_000_001, [2_000_001, 2_000_003]) == [], \
        "a tree pid still running keeps its lock"
    assert lock.exists()
