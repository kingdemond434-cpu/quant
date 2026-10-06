"""The judge's resumable epochs: finished shards are never rerun, and nothing about a verdict moves.

Sealed patch `judge_streaming_resume.patch` (2026-10-06). Measured on the trading box the same
day: every MT5-Gauntlet attempt pre-warmed for ~7,800 s, launched 15 shards over 584,979 cells,
lost five to ArrayMemoryError, published nothing (fail-closed, correctly) -- and the next attempt
deleted the ten finished shard files and started again. These tests run the patched judge in a
miniature desk (a temp copy of the sealed file, synthetic bars and series) and prove:

* a sharded sweep, an unsharded sweep and a sharded sweep that died half-way and was RESUMED
  write identical verdicts, trial census and program-level numbers;
* the resumed invocation dispatches ONLY the shards that had not finished;
* a merge that dies with every shard present keeps the epoch, and the next run re-dispatches
  nothing; the epoch is cleared once published and discarded after repeated merge failures;
* the series-only cell-local stages are served from their content-addressed checkpoint on a
  second sweep of the same data-day, with identical verdicts;
* the optional streaming bound (GAUNTLET_SWEEP_CELLS) rules a prefix of the judge's own order and
  records every other eligible cell DEFERRED, never dropped;
* each shard reads only its own slice of the plan;
* an older three-argument dispatcher still works.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import shutil
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEALED = _DESK / "scripts" / "external_gauntlet.py"
REL = Path("desks") / "mt5" / "scripts" / "external_gauntlet.py"

pytestmark = pytest.mark.skipif("SHARD_RESUME = 1" not in SEALED.read_text("utf-8"),
                                reason="judge_streaming_resume.patch not applied to the judge")

#: Wall-clock stamps, process facts and the run-shape reports: not verdicts.
VOLATILE = frozenset({"swept_at", "gated_at", "listed_at", "at", "updated_at", "revoked_at",
                      "retired_at", "restored_at", "ts", "prewarm", "peak_rss_mb", "workers",
                      "sharding", "memory_budget_mb", "first_seen", "last_seen", "seen_at",
                      "judged_at", "recorded_at", "epoch", "stage_cache",
                      "n_cells_deferred_epoch", "preregistration"})

LAST_DAY = pd.Timestamp("2026-09-29")


def _docket() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fams = ("carry", "session_range_breakout", "overnight_gap_decay", "trend_ma_cross")
    rng = np.random.default_rng(20261006)
    seed = 0
    for s in range(24):
        sym = f"SYN{s:03d}"
        for f in fams[: 2 + s % 3]:
            for _v in range(2):
                seed += 1
                days = int(rng.choice([45, 320, 480, 600]))
                drift = float(rng.choice([0.0, -0.05, 0.02, 0.5], p=[0.45, 0.25, 0.2, 0.1]))
                rows.append({"symbol": sym, "family": f,
                             "params": {"seed": seed, "drift": drift, "days": days}})
    rows.append({"symbol": "NOTLISTED", "family": "carry",
                 "params": {"seed": 9001, "drift": 0.3, "days": 400}})
    rows.append({"symbol": "NOBARS", "family": "carry",
                 "params": {"seed": 9004, "drift": 0.3, "days": 400}})
    rows.append({"symbol": "SYN003", "family": "carry",
                 "params": {"seed": -1, "drift": 0.3, "days": 400}})
    return rows


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2023-06-01", LAST_DAY + pd.Timedelta(hours=12), freq="h")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)


def _desk_tree(root: Path) -> Path:
    dst = root / REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SEALED, dst)
    uni = root / "desks" / "mt5" / "data" / "universe"
    uni.mkdir(parents=True, exist_ok=True)
    syms = [f"SYN{s:03d}" for s in range(24)] + ["NOBARS"]
    row = {"tradeable": True, "median_spread_pts": 10, "tick_size": 0.00001, "tick_value": 1.0,
           "contract_size": 100000, "swap_long": -1.0, "swap_short": 0.5}
    (uni / "universe.json").write_text(json.dumps({s: dict(row) for s in syms}), "utf-8")
    for s in syms:
        (uni / f"{s}_H1.parquet").write_bytes(b"")
    hyp = root / "desks" / "mt5" / "data" / "hypotheses"
    hyp.mkdir(parents=True, exist_ok=True)
    (hyp / "external_survivors.json").write_text(json.dumps(_docket()), "utf-8")
    (root / "desks" / "mt5" / "reports").mkdir(parents=True, exist_ok=True)
    return dst


def _series(sigs: dict[str, Any], mult: float) -> pd.Series:
    rng = np.random.default_rng(int(sigs["seed"]))
    n = int(sigs["days"])
    vals = rng.normal(float(sigs["drift"]), 1.0, n) - 0.01 * mult
    idx = pd.bdate_range(end=LAST_DAY - pd.Timedelta(days=1), periods=n)
    return pd.Series(vals, index=idx)


def _load(path: Path, name: str, mp_: pytest.MonkeyPatch) -> types.ModuleType:
    before = list(sys.path)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    sys.path[:] = before
    frame = _frame()

    def bars_for(sym: str, timeframe: str = "H1"):
        return None if sym == "NOBARS" else frame

    def build_cell(sym: str, family: str, params: dict, meta: dict, h1_override=None):
        if int(params.get("seed", 0)) < 0:
            return mod._build_failed("NOT_RUN_BUILD_FAILED: synthetic build failure")
        mod.LAST_BUILD_FAILURE = None
        return {"sym": sym, "family": family, "params": params, "timeframe": "H1",
                "df": frame, "sigs": dict(params), "costs": {"mult": 1.0},
                "_cost_basis": "synthetic", "_fill_hour": 7}

    mp_.setattr(mod, "_bars_for", bars_for)
    mp_.setattr(mod, "_live_frame", lambda *_a, **_k: None)
    mp_.setattr(mod, "build_cell", build_cell)
    mp_.setattr(mod, "costs_for", lambda sym, meta, mult=1.0: {"mult": mult})
    mp_.setattr(mod, "daily_series", lambda df, sigs, costs: _series(sigs, costs["mult"]))
    mp_.setattr(mod, "modifier_preflight", lambda spec: None)
    mp_.setattr(mod, "_ack_docket", lambda path: None)
    mp_.setattr(mod, "_progress_watermark", lambda *a: None)
    mp_.setattr(mod, "release_stamp", lambda: {"release_id": "test", "canon_sha256": None})
    # The hypothesis graph is the repository's own file: never written from a temp desk.
    mp_.setattr(mod, "record_gauntlet_verdicts", lambda *a, **k: {"status": "TEST_STUB"})
    # A MEASURED lifetime union, so the per-cell charge is max(campaign, union) and the docket can
    # hold ten-gate passes; with no ledger in a temp tree DSR fails closed for every cell.
    mp_.setattr(mod, "lifetime_trial_report", lambda families: {
        "status": "MEASURED", "lifetime_trials": 60, "family_trials": {},
        "families_absent_from_ledger": [], "ledger_generated_utc": None, "note": "test"})
    return mod


@contextlib.contextmanager
def _lane(*_a: Any, **_k: Any) -> Iterator[bool]:
    yield True


class Dispatcher:
    """Runs shards in-process, records what it was asked to run, and can be told to fail."""

    def __init__(self, mod: types.ModuleType, fail: dict[str, set[int]] | None = None) -> None:
        self.mod = mod
        self.fail = fail or {}
        self.calls: list[tuple[str, list[int]]] = []

    def __call__(self, shard_dir: Path, n: int, phase: str, ks: list[int] | None = None) -> None:
        ks = list(range(n)) if ks is None else list(ks)
        self.calls.append((phase, ks))
        bad = []
        for k in ks:
            if k in self.fail.get(phase, set()):
                bad.append(k)
                continue
            self.mod.shard_worker(shard_dir, k, phase)
        if bad:
            raise RuntimeError(f"{phase} shard(s) {bad} died (synthetic ArrayMemoryError)")


def _scrub(obj: Any, root: str) -> Any:
    if isinstance(obj, dict):
        return {k: _scrub(v, root) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [_scrub(v, root) for v in obj]
    if isinstance(obj, str):
        return obj.replace(root, "<ROOT>")
    return obj


def _outputs(tree: Path) -> dict[str, Any]:
    root = tree.parents[3]
    rep = root / "desks" / "mt5" / "reports"
    hyp = root / "desks" / "mt5" / "data" / "hypotheses"

    def rd(p: Path) -> Any:
        return json.loads(p.read_text("utf-8")) if p.exists() else None

    return _scrub({
        "report": rd(rep / "universal_gates_external.json"),
        "survivors": rd(rep / "UNIVERSAL_SURVIVORS.json"),
        "gate_index": rd(hyp / "gate_verdict_index.json"),
        "seen_cells": sorted((rd(hyp / "gauntlet_seen_cells.json") or {}).keys()),
    }, str(root))


def _first_diff(a: Any, b: Any, path: str = "") -> str | None:
    """The first path at which two outputs differ (None when equal), for a readable failure."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                return f"{path}.{k}: only in {'b' if k not in a else 'a'}"
            d = _first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            d = _first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def _same(a: Any, b: Any) -> None:
    d = _first_diff(a, b)
    assert d is None, d


def _report(tree: Path) -> dict[str, Any]:
    return json.loads((tree.parents[3] / "desks/mt5/reports/universal_gates_external.json")
                      .read_text("utf-8"))


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("GAUNTLET_WORKERS", "1")
    monkeypatch.setenv("GAUNTLET_MEMORY_BUDGET_MB", "1000000")
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "1000000")
    monkeypatch.delenv("GAUNTLET_SWEEP_CELLS", raising=False)
    monkeypatch.setitem(sys.modules, "novelty_gate", types.SimpleNamespace(
        screen=lambda cands: [types.SimpleNamespace(verdict="NOVEL") for _ in cands]))
    import research.job_lock as jl
    monkeypatch.setattr(jl, "exclusive_job", _lane)
    return monkeypatch


def _desk(tmp: Path, name: str, mp_: pytest.MonkeyPatch) -> tuple[Path, types.ModuleType]:
    tree = _desk_tree(tmp / name)
    return tree, _load(tree, f"eg_stream_{name}", mp_)


# ------------------------------------------------------------------------------------ proofs
def test_a_resumed_epoch_is_verdict_identical_and_reruns_only_unfinished_shards(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    t_base, base_mod = _desk(tmp_path, "unsharded", env)
    base_mod.main()
    base = _outputs(t_base)
    judged = [v for v in base["report"]["verdicts"] if v.get("stages", {}).get("deflated_sharpe")]
    assert any(v["passed"] for v in judged) and any(not v["passed"] for v in judged)

    t_one, one_mod = _desk(tmp_path, "oneshot", env)
    assert one_mod.run_sharded(4, Dispatcher(one_mod), shard_dir=tmp_path / "oneshot/sh") == 0
    _same(_outputs(t_one), base)

    # Shards 1 and 3 die in the build phase: fail closed, nothing published, outputs KEPT.
    t_res, res_mod = _desk(tmp_path, "resumed", env)
    sh = tmp_path / "resumed" / "sh"
    first = Dispatcher(res_mod, fail={"build": {1, 3}})
    with pytest.raises(RuntimeError, match="died"):
        res_mod.run_sharded(4, first, shard_dir=sh)
    assert not (t_res.parents[3] / "desks/mt5/reports/universal_gates_external.json").exists()
    assert (sh / "epoch.pkl").exists()
    assert {k for k in range(4) if (sh / f"shard_{k}.done.json").exists()} == {0, 2}

    second = Dispatcher(res_mod)
    assert res_mod.run_sharded(4, second, shard_dir=sh) == 0
    assert second.calls == [("build", [1, 3]), ("rule", [0, 1, 2, 3])]
    _same(_outputs(t_res), base)
    rep = _report(t_res)
    assert rep["epoch"]["resumed"] is True and rep["epoch"]["shards_finished_before"] == [0, 2]
    assert rep["sharding"]["shards_resumed_built"] == [0, 2]
    # Published: the epoch is done and its files are gone.
    assert not (sh / "epoch.pkl").exists() and not list(sh.glob("shard_*"))


def test_a_rule_phase_death_resumes_at_the_rule_phase(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    t_res, mod = _desk(tmp_path, "rule", env)
    sh = tmp_path / "rule" / "sh"
    with pytest.raises(RuntimeError):
        mod.run_sharded(3, Dispatcher(mod, fail={"rule": {2}}), shard_dir=sh)
    again = Dispatcher(mod)
    assert mod.run_sharded(3, again, shard_dir=sh) == 0
    assert again.calls == [("rule", [2])]
    t_ref, ref = _desk(tmp_path, "ref", env)
    assert ref.run_sharded(3, Dispatcher(ref), shard_dir=tmp_path / "ref/sh") == 0
    _same(_outputs(t_res), _outputs(t_ref))


def test_a_failed_merge_keeps_every_shard_and_is_bounded(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    t, mod = _desk(tmp_path, "merge", env)
    sh = tmp_path / "merge" / "sh"
    real = mod.run_gauntlet

    def boom(*_a: Any, **_k: Any) -> dict:
        raise MemoryError("synthetic ArrayMemoryError in the union merge")

    env.setattr(mod, "run_gauntlet", boom)
    with pytest.raises(MemoryError):
        mod.run_sharded(3, Dispatcher(mod), shard_dir=sh)
    assert mod._unpickle(sh / "epoch.pkl")["merge_failures"] == 1
    env.setattr(mod, "run_gauntlet", real)
    again = Dispatcher(mod)
    assert mod.run_sharded(3, again, shard_dir=sh) == 0
    assert again.calls == []                      # every shard was already ruled
    t_ref, ref = _desk(tmp_path, "mref", env)
    assert ref.run_sharded(3, Dispatcher(ref), shard_dir=tmp_path / "mref/sh") == 0
    _same(_outputs(t), _outputs(t_ref))

    # A merge that keeps failing is not retried forever: the epoch is discarded and re-planned.
    env.setattr(mod, "run_gauntlet", boom)
    for _ in range(mod.EPOCH_MAX_MERGE_FAILURES):
        with pytest.raises(MemoryError):
            mod.run_sharded(3, Dispatcher(mod), shard_dir=sh)
    env.setattr(mod, "run_gauntlet", real)
    fresh = Dispatcher(mod)
    assert mod.run_sharded(3, fresh, shard_dir=sh) == 0
    assert fresh.calls[0] == ("build", [0, 1, 2])
    assert "merges of it failed" in _report(t)["epoch"]["why_new"]


def test_the_series_only_stages_are_served_from_their_checkpoint(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    """Two sweeps of one data-day: every series ruled before is a checkpoint hit on the second,
    and the published outputs equal a desk whose checkpoint is disabled."""
    t, mod = _desk(tmp_path, "stages", env)
    # The yield quota rotates which cells a sweep reaches; with it off, both sweeps rule one set.
    env.setattr(mod, "allocate_by_yield", lambda specs: (specs, {}))
    keys: list[set[str]] = []
    real_key = mod._stage_key

    def recording_key(arr: Any, x3: Any) -> str | None:
        k = real_key(arr, x3)
        keys[-1].add(str(k))
        return k

    env.setattr(mod, "_stage_key", recording_key)
    stats: list[dict[str, int]] = []
    for _ in range(2):
        keys.append(set())
        before = dict(mod.STAGE_CACHE_STATS)
        mod.main()
        stats.append({k: mod.STAGE_CACHE_STATS[k] - before[k] for k in before})
    assert stats[0]["hit"] == 0 and stats[0]["miss"] == len(keys[0]) > 0
    overlap = keys[1] & keys[0]
    assert keys[1] == keys[0], "one data-day, one docket: the second sweep rules the same series"
    assert stats[1]["hit"] == len(overlap) == len(keys[1])
    assert stats[1]["miss"] == 0
    assert stats[1]["error"] == 0

    t_off, off = _desk(tmp_path, "nostages", env)
    env.setattr(off, "allocate_by_yield", lambda specs: (specs, {}))
    off._STAGE_FINGERPRINT[:] = [None]                    # checkpoint disabled
    off.main()
    off.main()
    assert off.STAGE_CACHE_STATS["hit"] == 0
    _same(_outputs(t), _outputs(t_off))

    # The checkpoint is keyed by the VALUES: one changed observation is a different key.
    arr = np.linspace(-1.0, 1.0, 200)
    x3 = pd.Series(arr - 0.1)
    assert real_key(arr, x3) == real_key(arr.copy(), x3.copy())
    arr2 = arr.copy()
    arr2[17] += 1e-9
    assert real_key(arr2, x3) != real_key(arr, x3)
    assert real_key(arr, None) != real_key(arr, x3)
    # and the cached result is exactly the computed one
    assert mod._pure_stages_cached(arr, x3) == mod._pure_local_stages(arr, x3)
    assert mod._pure_stages_cached(arr, x3) == mod._pure_local_stages(arr, x3)


def test_the_streaming_bound_rules_a_prefix_and_defers_the_rest(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    env.setenv("GAUNTLET_SWEEP_CELLS", "30")
    t, mod = _desk(tmp_path, "bound", env)
    assert mod.run_sharded(3, Dispatcher(mod), shard_dir=tmp_path / "bound/sh") == 0
    rep = _report(t)
    assert rep["epoch"]["cells"] == 30 and rep["epoch"]["bound"] == 30
    assert rep["n_cells_deferred_epoch"] == rep["epoch"]["deferred_outside_epoch"] > 0
    ids = [v["cell"] for v in rep["verdicts"]]
    assert len(ids) == len(set(ids))                       # each docket cell exactly once
    deferred = [v for v in rep["verdicts"]
                if v.get("downstream_status") == "NOT_RUN_BUILD_BUDGET_DEFERRED"]
    assert len(deferred) >= rep["n_cells_deferred_epoch"]
    assert all(v["passed"] is None for v in deferred)
    # every cell an unbounded sweep accounts for is accounted for here too: ruled or deferred
    env.delenv("GAUNTLET_SWEEP_CELLS")
    t_ref, ref = _desk(tmp_path, "unbounded", env)
    assert ref.run_sharded(3, Dispatcher(ref), shard_dir=tmp_path / "unbounded/sh") == 0
    assert set(ids) == {v["cell"] for v in _report(t_ref)["verdicts"]}
    ruled = [v for v in rep["verdicts"] if v.get("stages", {}).get("deflated_sharpe")]
    assert 0 < len(ruled) <= 30


def test_each_shard_reads_only_its_slice_and_a_v2_dispatcher_still_works(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    t, mod = _desk(tmp_path, "v2", env)
    sh = tmp_path / "v2" / "sh"
    seen: list[tuple[str, int]] = []

    def v2(shard_dir: Path, n: int, phase: str) -> None:   # the protocol-2 signature
        plan = mod._unpickle(shard_dir / "plan.pkl")
        assert plan["specs"] is None                      # the header carries no specs
        for k in range(n):
            mine = mod._unpickle(shard_dir / f"plan_{k}.pkl")
            assert all(mod.shard_of(sp, n) == k for _i, sp in mine)
            seen.append((phase, k))
            mod.shard_worker(shard_dir, k, phase)

    assert mod.run_sharded(3, v2, shard_dir=sh) == 0
    assert seen == [("build", 0), ("build", 1), ("build", 2),
                    ("rule", 0), ("rule", 1), ("rule", 2)]
    t_ref, ref = _desk(tmp_path, "v2ref", env)
    ref.main()
    _same(_outputs(t), _outputs(t_ref))


def test_a_changed_shard_count_starts_a_new_epoch(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    _t, mod = _desk(tmp_path, "count", env)
    sh = tmp_path / "count" / "sh"
    with pytest.raises(RuntimeError):
        mod.run_sharded(3, Dispatcher(mod, fail={"build": {0}}), shard_dir=sh)
    assert json.loads((sh / "epoch.json").read_text("utf-8"))["n"] == 3
    d = Dispatcher(mod)
    assert mod.run_sharded(5, d, shard_dir=sh) == 0
    assert d.calls[0] == ("build", [0, 1, 2, 3, 4])
