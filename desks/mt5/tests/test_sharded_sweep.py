"""A sharded sweep rules EXACTLY what the unsharded sweep rules -- verdicts, census, program stats.

`sealed_patches/external_gauntlet_sharded_sweep.patch` lets the sealed judge run as N shards:
each shard builds its stable-hash share of ONE plan (phase `build`), the merge takes the ONE
lockbox cut from the union of every shard's dates, each shard then computes only the cell-local
gates on the development window (phase `rule`), and the merge computes every program-level number
(the trial census, the deflated-Sharpe charge, PBO, SPA, the lockbox at the union's DSR hurdle)
once, on the union, before anything is written. The binding constraint is that
this is VERDICT-IDENTICAL to today's single sweep on the same docket. This file proves it by
applying the patch to a TEMP COPY of the sealed file (never the repo copy), running the ORIGINAL
sealed sweep, the patched sweep with N=1 and the patched sweep with N=3 on one synthetic docket
in three identical miniature desks, and comparing every artifact the sweep writes.

The docket exercises every branch a verdict can take: gate-0 rejections (untradeable symbol, no
economic prior, the banned `discovered` family), data missing, build failed, too few days
(UNMEASURED), ten-gate passes and failures, series of different lengths (so the union matrix's
common window is set by a cell in ANOTHER shard), and a second, warm pass over the cache.

The shards run as forked processes where the platform can fork (the wall clock is then a real
parallel measurement) and in-process otherwise; the verdicts must match either way.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import multiprocessing as mp
import shutil
import subprocess
import sys
import time
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
PATCH = _DESK / "sealed_patches" / "external_gauntlet_sharded_sweep.patch"
REL = Path("desks") / "mt5" / "scripts" / "external_gauntlet.py"

#: Keys whose values are wall-clock stamps, process facts or the sharding report itself. They
#: are not verdicts and legitimately differ between two runs of the SAME sweep.
VOLATILE = frozenset({"swept_at", "gated_at", "listed_at", "at", "updated_at", "revoked_at",
                      "retired_at", "restored_at", "ts", "prewarm", "peak_rss_mb", "workers",
                      "sharding", "memory_budget_mb", "first_seen", "last_seen", "seen_at",
                      "judged_at", "recorded_at"})

LAST_DAY = pd.Timestamp("2026-09-29")


# --------------------------------------------------------------------------- the synthetic desk
def _docket() -> list[dict[str, Any]]:
    """~150 cells over 30 symbols and four families, every verdict branch represented."""
    rows: list[dict[str, Any]] = []
    fams = ("carry", "session_range_breakout", "overnight_gap_decay", "trend_ma_cross")
    rng = np.random.default_rng(20260930)
    seed = 0
    for s in range(30):
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
    rows.append({"symbol": "SYN001", "family": "carry", "mechanism_status": "STATISTICAL_ONLY",
                 "params": {"seed": 9002, "drift": 0.3, "days": 400}})
    rows.append({"symbol": "SYN002", "family": "discovered",
                 "params": {"seed": 9003, "drift": 0.3, "days": 400}})
    rows.append({"symbol": "NOBARS", "family": "carry",
                 "params": {"seed": 9004, "drift": 0.3, "days": 400}})
    rows.append({"symbol": "SYN003", "family": "carry",
                 "params": {"seed": -1, "drift": 0.3, "days": 400}})
    return rows


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2023-06-01", LAST_DAY + pd.Timedelta(hours=12), freq="h")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)


def _desk_tree(root: Path, patched: bool) -> Path:
    """A miniature desk under `root`: the sealed file (patched or not), registry, docket."""
    dst = root / REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SEALED, dst)
    if patched and "SHARD_PROTOCOL" not in SEALED.read_text("utf-8"):
        subprocess.run(["git", "apply", "--whitespace=nowarn", str(PATCH)], cwd=root,
                       check=True, capture_output=True)
        assert "SHARD_PROTOCOL = 2" in dst.read_text("utf-8")
    uni = root / "desks" / "mt5" / "data" / "universe"
    uni.mkdir(parents=True, exist_ok=True)
    syms = [f"SYN{s:03d}" for s in range(30)] + ["NOBARS"]
    # Every registry cost field `swap_cost` needs, so a cell can be priced and pass all ten.
    row = {"tradeable": True, "median_spread_pts": 10, "tick_size": 0.00001, "tick_value": 1.0,
           "contract_size": 100000, "swap_long": -1.0, "swap_short": 0.5}
    (uni / "universe.json").write_text(json.dumps({s: dict(row) for s in syms}), "utf-8")
    for s in syms:
        (uni / f"{s}_H1.parquet").write_bytes(b"")      # exists(): gate 0's parquet limb
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
    """Import one tree's judge with every host side effect pointed at a stub."""
    before = list(sys.path)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    sys.path[:] = before                               # the module pushes its tree's BASE
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
    return mod


@contextlib.contextmanager
def _lane(*_a: Any, **_k: Any) -> Iterator[bool]:
    yield True


def _fork_dispatch(mod: types.ModuleType):
    """Every shard at once, as its own process, when the platform can fork."""
    def dispatch(shard_dir: Path, n: int, phase: str) -> None:
        ctx = mp.get_context("fork")
        procs = [ctx.Process(target=mod.shard_worker, args=(shard_dir, k, phase))
                 for k in range(n)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        bad = [p.exitcode for p in procs if p.exitcode != 0]
        if bad:
            raise RuntimeError(f"shard exit codes {bad}")
    return dispatch


def _inline_dispatch(mod: types.ModuleType):
    def dispatch(shard_dir: Path, n: int, phase: str) -> None:
        for k in range(n):
            mod.shard_worker(shard_dir, k, phase)
    return dispatch


def _can_fork() -> bool:
    return "fork" in mp.get_all_start_methods()


# ------------------------------------------------------------------------ reading the outputs
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

    out = {
        "report": rd(rep / "universal_gates_external.json"),
        "survivors": rd(rep / "UNIVERSAL_SURVIVORS.json"),
        "power_cure": rd(rep / "POWER_CURE_CANDIDATES.json"),
        "claims": rd(rep / "SURVIVORS_LEDGER.json"),
        "gate_index": rd(hyp / "gate_verdict_index.json"),
        "seen_cells": sorted((rd(hyp / "gauntlet_seen_cells.json") or {}).keys()),
    }
    return _scrub(out, str(root))


def _run(tmp: Path, name: str, mp_: pytest.MonkeyPatch, *, patched: bool,
         shards: int | None, fork: bool = True, passes: int = 1) -> tuple[dict, list[float]]:
    tree = _desk_tree(tmp / name, patched)
    mod = _load(tree, f"eg_{name}", mp_)
    import research.job_lock as jl
    mp_.setattr(jl, "exclusive_job", _lane)
    secs: list[float] = []
    for _ in range(passes):
        t0 = time.perf_counter()
        if shards is None:
            mod.main()
        else:
            disp = _fork_dispatch(mod) if (fork and _can_fork()) else _inline_dispatch(mod)
            assert mod.run_sharded(shards, disp, shard_dir=tmp / name / "shards") == 0
        secs.append(time.perf_counter() - t0)
    return _outputs(tree), secs


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("GAUNTLET_WORKERS", "1")
    monkeypatch.setenv("GAUNTLET_MEMORY_BUDGET_MB", "1000000")
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "1000000")
    monkeypatch.setitem(sys.modules, "novelty_gate", types.SimpleNamespace(
        screen=lambda cands: [types.SimpleNamespace(verdict="NOVEL") for _ in cands]))
    return monkeypatch


def _patch_applies() -> bool:
    if "SHARD_PROTOCOL" in SEALED.read_text("utf-8"):
        return True
    return not (not PATCH.exists() or shutil.which("git") is None)


pytestmark = pytest.mark.skipif(not _patch_applies(), reason="patch or git unavailable")


# --------------------------------------------------------------------------------- the proofs
def test_n1_and_n3_are_verdict_identical_to_the_unsharded_sweep(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    base, t_base = _run(tmp_path, "unsharded", env, patched=False, shards=None, passes=2)
    one, t_one = _run(tmp_path, "n1", env, patched=True, shards=1, passes=2)
    three, t_three = _run(tmp_path, "n3", env, patched=True, shards=3, passes=2)

    rep = base["report"]
    assert rep and rep["verdicts"], "the unsharded sweep ruled nothing"
    judged = [v for v in rep["verdicts"] if v.get("stages", {}).get("deflated_sharpe")]
    assert any(v["passed"] for v in judged), "the docket must hold a ten-gate pass"
    assert any(not v["passed"] for v in judged)
    assert any(v.get("unmeasured") for v in rep["verdicts"])
    assert {v.get("downstream_status") for v in rep["verdicts"]} >= {
        "NOT_RUN_DATA_MISSING", "NOT_RUN_BUILD_FAILED", "NOT_RUN_UNTRADEABLE_SYMBOL"}
    assert not [v for v in judged if v["family"] == "discovered"], "discovered stays banned"
    # the lockbox is live: a real cut, and every judged cell carries gate 9 at its DSR hurdle
    assert all("lockbox" in v["stages"] for v in judged)
    assert any(v["stages"]["lockbox"]["passed"] for v in judged)
    assert any(v["stages"]["swap_cost"]["passed"] for v in judged)

    for got in (one, three):
        r = got["report"]
        # the four the constraint names, then everything else the sweep writes
        assert r["verdicts"] == rep["verdicts"]
        assert r["n_trials"] == rep["n_trials"]
        assert r["trial_count_basis"] == rep["trial_count_basis"]
        assert r["trial_census"] == rep["trial_census"]
        assert r["program_level"] == rep["program_level"]
        assert r["effective_trials"] == rep["effective_trials"]
        assert r == rep
        assert got == base

    print(f"\nWALL-CLOCK (cold, warm) s: unsharded {t_base[0]:.2f}, {t_base[1]:.2f} | "
          f"N=1 {t_one[0]:.2f}, {t_one[1]:.2f} | N=3 {t_three[0]:.2f}, {t_three[1]:.2f} "
          f"(fork={_can_fork()})")


def test_every_cell_is_charged_once_and_the_family_is_the_union(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    """The deflated-Sharpe row every cell carries names the UNION's charge, not its shard's."""
    tree = _desk_tree(tmp_path / "u", True)
    mod = _load(tree, "eg_union", env)
    import research.job_lock as jl
    env.setattr(jl, "exclusive_job", _lane)
    assert mod.run_sharded(3, _inline_dispatch(mod), shard_dir=tmp_path / "u" / "shards") == 0
    rep = json.loads((tree.parents[3] / "desks/mt5/reports/universal_gates_external.json")
                     .read_text("utf-8"))
    sh = rep["sharding"]
    assert sh["n_shards"] == 3 and sh["each_cell_ruled_once"] is True
    assert sum(s["planned"] for s in sh["shards"]) == sh["planned_cells"]
    ns = {v["stages"]["deflated_sharpe"]["n_trials"] for v in rep["verdicts"]
          if v.get("stages", {}).get("deflated_sharpe")}
    assert ns == {rep["n_trials"]}
    ids = [v["cell"] for v in rep["verdicts"] if v.get("stages", {}).get("deflated_sharpe")]
    assert len(ids) == len(set(ids))


def test_a_missing_shard_fails_closed_and_publishes_nothing(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    tree = _desk_tree(tmp_path / "m", True)
    mod = _load(tree, "eg_missing", env)
    import research.job_lock as jl
    env.setattr(jl, "exclusive_job", _lane)

    def lossy(shard_dir: Path, n: int, phase: str) -> None:
        for k in range(n - 1):                          # the last shard never reports
            mod.shard_worker(shard_dir, k, phase)

    with pytest.raises(mod.ShardMergeError):
        mod.run_sharded(3, lossy, shard_dir=tmp_path / "m" / "shards")
    rep = tree.parents[3] / "desks" / "mt5" / "reports"
    hyp = tree.parents[3] / "desks" / "mt5" / "data" / "hypotheses"
    for name in ("universal_gates_external.json", "UNIVERSAL_SURVIVORS.json",
                 "SURVIVORS_LEDGER.json", "POWER_CURE_CANDIDATES.json"):
        assert not (rep / name).exists(), name
    assert not (hyp / "gauntlet_seen_cells.json").exists()
    assert mod._SHARD is None


def test_a_shard_returning_a_cell_it_does_not_own_is_refused(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    tree = _desk_tree(tmp_path / "t", True)
    mod = _load(tree, "eg_tamper", env)
    import research.job_lock as jl
    env.setattr(jl, "exclusive_job", _lane)

    def tamper(shard_dir: Path, n: int, phase: str) -> None:
        for k in range(n):
            mod.shard_worker(shard_dir, k, phase)
        if phase != "rule":
            return
        a, b = mod._unpickle(shard_dir / "shard_0.pkl"), mod._unpickle(shard_dir / "shard_1.pkl")
        a["rows"].append(b["rows"][0])                  # shard 0 claims a shard-1 cell
        mod._pickle_atomic(shard_dir / "shard_0.pkl", a)

    with pytest.raises(mod.ShardMergeError):
        mod.run_sharded(3, tamper, shard_dir=tmp_path / "t" / "shards")


def test_a_shard_ruling_at_another_lockbox_cut_is_refused(
        tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    """The cut is program-level: a shard that carved anywhere but the union's cut fails closed."""
    tree = _desk_tree(tmp_path / "c", True)
    mod = _load(tree, "eg_cut", env)
    import research.job_lock as jl
    env.setattr(jl, "exclusive_job", _lane)

    def skew(shard_dir: Path, n: int, phase: str) -> None:
        if phase == "rule":                             # shard 1 is handed an earlier cut
            got = mod._unpickle(shard_dir / "cut.pkl")
            for k in range(n):
                if k == 1:
                    mod._pickle_atomic(shard_dir / "cut.pkl",
                                       {**got, "cut": got["cut"] - pd.Timedelta(days=30)})
                mod.shard_worker(shard_dir, k, phase)
                mod._pickle_atomic(shard_dir / "cut.pkl", got)
            return
        for k in range(n):
            mod.shard_worker(shard_dir, k, phase)

    with pytest.raises(mod.ShardMergeError):
        mod.run_sharded(3, skew, shard_dir=tmp_path / "c" / "shards")
    assert not (tree.parents[3] / "desks/mt5/reports/universal_gates_external.json").exists()


def test_the_partition_is_stable_and_total(tmp_path: Path, env: pytest.MonkeyPatch) -> None:
    """sha256 of the cell id, mod N: the same shard on every call, and one of 0..N-1."""
    mod = _load(_desk_tree(tmp_path / "p", True), "eg_partition", env)
    rows = [{"sym": r["symbol"], "family": r["family"], "params": r["params"]}
            for r in _docket()]
    for n in (1, 2, 3, 7):
        parts = [mod.shard_of(r, n) for r in rows]
        assert parts == [mod.shard_of(dict(r), n) for r in rows]
        assert set(parts) <= set(range(n))
    assert len({mod.shard_of(r, 3) for r in rows}) == 3


def test_the_launcher_falls_back_to_the_unsharded_sweep_without_the_patch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(_DESK / "scripts"))
    try:
        import external_gauntlet_sharded as sg
    finally:
        sys.path.remove(str(_DESK / "scripts"))
    calls: list[str] = []
    fake = types.SimpleNamespace(__file__=str(SEALED), WORKERS=15, MEMORY_BUDGET_MB=8192,
                                 _cli_main=lambda: calls.append("unsharded") or 0)
    monkeypatch.setattr(sg, "_import_judge", lambda: fake)
    monkeypatch.setattr(sg, "REPORT", tmp_path / "SHARDED_SWEEP.json")
    assert sg.supports_sharding(fake) is False
    assert sg.main([]) == 0
    assert calls == ["unsharded"]
    doc = json.loads((tmp_path / "SHARDED_SWEEP.json").read_text("utf-8"))
    assert doc["mode"] == "unsharded" and "SHARD_PROTOCOL" in doc["why"]

    # patched, but a reproduction: never sharded
    # a judge carrying another protocol version is not spoken to
    fake1 = types.SimpleNamespace(**{**vars(fake), "SHARD_PROTOCOL": 1,
                                     "run_sharded": lambda *a, **k: calls.append("sharded"),
                                     "shard_worker": lambda *a: None,
                                     "shard_of": lambda *a: 0})
    assert sg.supports_sharding(fake1) is False

    fake2 = types.SimpleNamespace(**{**vars(fake), "SHARD_PROTOCOL": 2,
                                     "run_sharded": lambda *a, **k: calls.append("sharded"),
                                     "shard_worker": lambda *a: None,
                                     "shard_of": lambda *a: 0})
    monkeypatch.setattr(sg, "_import_judge", lambda: fake2)
    assert sg.supports_sharding(fake2) is True
    assert sg.main(["--only", "EURUSD"]) == 0
    assert calls == ["unsharded", "unsharded"]

    # a sharded run that raises falls back to the unsharded sweep in the same slot
    def boom(*_a: Any, **_k: Any) -> int:
        raise RuntimeError("shard 2 rc=1")
    fake3 = types.SimpleNamespace(**{**vars(fake2), "run_sharded": boom})
    monkeypatch.setattr(sg, "_import_judge", lambda: fake3)
    monkeypatch.setenv("GAUNTLET_SHARDS", "3")
    assert sg.main([]) == 0
    assert calls[-1] == "unsharded"
    doc = json.loads((tmp_path / "SHARDED_SWEEP.json").read_text("utf-8"))
    assert "FAILED CLOSED" in doc["why"] and "shard 2" in doc["sharded_failure"]


def test_the_burndown_reads_how_the_last_sweep_ran(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    import judging_burndown as jb
    monkeypatch.setattr(jb, "SHARDED", tmp_path / "SHARDED_SWEEP.json")
    assert jb.sharding()["status"] == "UNMEASURED"
    (tmp_path / "SHARDED_SWEEP.json").write_text(json.dumps({
        "at": "2026-09-30T12:00:00+00:00", "mode": "sharded", "why": "sharded sweep ran",
        "decision": {"n_shards": 3}, "wall_seconds": 90.0, "sealed_protocol": 2,
        "merge": {"dispatch_seconds": 60.0, "shards": [{"k": 0, "seconds": 40.0},
                                                       {"k": 1, "seconds": 58.5}]}}), "utf-8")
    got = jb.sharding()
    assert got["status"] == "MEASURED" and got["n_shards"] == 3
    assert got["slowest_shard_seconds"] == 58.5 and got["fastest_shard_seconds"] == 40.0
