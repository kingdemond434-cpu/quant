"""Judge P0 (2026-11-25): the pre-warm can never hang, the prune is bounded, midnight costs nothing.

Sweep pid 18528 sat in the pre-warm's `wait(...)` loop from 07:27Z with an idle tree: no cell
timeout, a deadline that only refused NEW work, and `shutdown(wait=True)` on the way out. The
11-24 sweep's shards started after 00:00Z, every parquet's data-day had rolled, and the pool's
cells all missed. These pin the fixes by behaviour, with real pools and real files.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time

import pytest

from scripts import external_gauntlet as eg

needs_fork = pytest.mark.skipif(
    sys.platform == "win32" or mp.get_start_method(allow_none=True) not in (None, "fork"),
    reason="the fake worker is installed by fork")


def _fake(spec, meta):                          # module level: the pool pickles it by name
    k = spec["params"]["k"]
    if k.startswith("hang"):
        time.sleep(3600)
    return {"sym": spec["sym"], "family": spec["family"], "tf": "H1", "status": "WARMED",
            "why": "", "data_day": "2026-11-24"}


def _specs(kinds: list[str]) -> list[dict]:
    return [{"sym": f"S{i}", "family": "fam", "params": {"k": f"{k}{i}"}}
            for i, k in enumerate(kinds)]


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(eg, "_warm_one", _fake)
    monkeypatch.setattr(eg, "WORKERS", 2)
    monkeypatch.setattr(eg, "PREWARM_POLL_S", 0.1)
    monkeypatch.setattr(eg, "PREWARM_HUNG_POOL_S", 1.5)
    monkeypatch.setattr(eg, "PREWARM_DEADLINE_GRACE_S", 0.5)
    monkeypatch.setenv("GAUNTLET_PREWARM_CELL_TIMEOUT_S", "1")
    return monkeypatch


@needs_fork
def test_a_cell_that_never_returns_is_abandoned_by_name_and_the_rest_are_warmed(fast) -> None:
    t0 = time.time()
    got = eg._prewarm_cache(_specs(["w", "hang", "w", "w", "w"]), {}, time.time() + 600)
    assert time.time() - t0 < 30
    assert got["failures"].get("CELL_TIMEOUT") == 1 and got["timed_out"] == 1
    assert got["warmed"] == 4
    assert got["warmed"] + got["hit"] + got["failed"] + got["unreached"] == 5
    assert got["built_symbols"] == {"S0", "S2", "S3", "S4"}    # the rotation key, intact
    assert got["data_days"] == {"S0|H1": "2026-11-24", "S2|H1": "2026-11-24",
                                "S3|H1": "2026-11-24", "S4|H1": "2026-11-24"}
    assert got["pool_teardown"]["workers"] >= 1


@needs_fork
def test_a_pool_where_nothing_completes_is_torn_down_and_the_sweep_proceeds(fast) -> None:
    fast.setenv("GAUNTLET_PREWARM_CELL_TIMEOUT_S", "3600")     # only the hung rule can act
    t0 = time.time()
    got = eg._prewarm_cache(_specs(["hang"] * 6), {}, time.time() + 600)
    assert time.time() - t0 < 30
    assert got["pool_hung"] is True and got["ended"] == "pool_hung"
    assert got["failures"].get("POOL_HUNG", 0) >= 1
    assert got["warmed"] == 0
    assert got["failed"] + got["unreached"] == 6               # every cell accounted, none judged
    assert got["pool_teardown"]["terminated"] >= 1


@needs_fork
def test_at_the_deadline_running_cells_get_a_bounded_grace_then_the_pool_is_left(fast) -> None:
    fast.setenv("GAUNTLET_PREWARM_CELL_TIMEOUT_S", "3600")
    fast.setattr(eg, "PREWARM_HUNG_POOL_S", 3600.0)
    t0 = time.time()
    got = eg._prewarm_cache(_specs(["hang"] * 8), {}, time.time() + 0.5)
    assert time.time() - t0 < 30
    assert got["ended"] == "deadline_grace_spent"
    assert got["abandoned_at_deadline"] >= 1
    assert got["unreached"] == 8 and got["failed"] == 0         # the budget's reason, not a fault


def test_the_cell_timeout_is_derived_from_measured_seconds_within_floor_and_ceiling(
        monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_PREWARM_CELL_TIMEOUT_S", raising=False)
    few = [1.0] * (eg.PREWARM_CELL_TIMEOUT_MIN_N - 1)
    assert eg._prewarm_cell_timeout_s(few) == eg.PREWARM_CELL_TIMEOUT_CEIL_S   # unmeasured: ceil
    n = eg.PREWARM_CELL_TIMEOUT_MIN_N
    assert eg._prewarm_cell_timeout_s([3.0] * n) == eg.PREWARM_CELL_TIMEOUT_FLOOR_S
    assert eg._prewarm_cell_timeout_s([60.0] * n) == 60.0 * eg.PREWARM_CELL_TIMEOUT_MULT
    assert eg._prewarm_cell_timeout_s([1e6] * n) == eg.PREWARM_CELL_TIMEOUT_CEIL_S


def test_the_pool_is_never_left_through_a_waiting_shutdown() -> None:
    import inspect
    src = inspect.getsource(eg._prewarm_cache)
    assert "with ProcessPoolExecutor" not in src
    assert "_abandon_pool(pool)" in src and "finally:" in src


# ---------------------------------------------------------------------------- bounded prune
def _cache(tmp_path, monkeypatch, ages_d: list[float]):
    d = tmp_path / "gauntlet_cache"
    d.mkdir()
    now = time.time()
    for i, a in enumerate(ages_d):
        f = d / f"k{i:02d}.npz"
        f.write_bytes(b"x")
        os.utime(f, (now - a * 86400, now - a * 86400))
    monkeypatch.setattr(eg, "CACHE_DIR", d)
    monkeypatch.setattr(eg, "CACHE_PRUNE_CURSOR", d / "_prune_cursor.json")
    return d


def test_the_prune_removes_only_files_older_than_three_days(tmp_path, monkeypatch) -> None:
    d = _cache(tmp_path, monkeypatch, [0.1, 2.9, 3.1, 10.0, 1.0, 4.0])
    got = eg._bounded_cache_prune(budget_s=600)
    assert got["complete"] and got["cursor"] is None
    assert sorted(p.name for p in d.glob("*.npz")) == ["k00.npz", "k01.npz", "k04.npz"]


def test_a_spent_prune_budget_stops_and_the_next_sweep_resumes(tmp_path, monkeypatch) -> None:
    d = _cache(tmp_path, monkeypatch, [10.0] * 6)
    got = eg._bounded_cache_prune(budget_s=0)          # spent before the first file
    assert not got["complete"] and got["removed"] == 0
    assert len(list(d.glob("*.npz"))) == 6
    json.dumps(json.loads((d / "_prune_cursor.json").read_text("utf-8")))
    # resume from a cursor: names at or before it are skipped without a stat or a delete
    (d / "_prune_cursor.json").write_text(json.dumps({"cursor": "k02.npz"}), "utf-8")
    got = eg._bounded_cache_prune(budget_s=600)
    assert got["complete"] and got["removed"] == 3
    assert sorted(p.name for p in d.glob("*.npz")) == ["k00.npz", "k01.npz", "k02.npz"]
    got = eg._bounded_cache_prune(budget_s=600)       # cursor cleared: the walk wraps
    assert got["removed"] == 3 and not list(d.glob("*.npz"))


# -------------------------------------------------------------------------- midnight
def test_a_sweep_spanning_midnight_still_hits_the_cells_its_prewarm_built(
        tmp_path, monkeypatch) -> None:
    """The pool keyed the cell on 11-24; the shard reads a parquet that now ends 11-25. The
    planned key is tried, the exact pre-warmed series is used, and the cell carries 11-24."""
    import pandas as pd
    monkeypatch.setattr(eg, "CACHE_DIR", tmp_path)
    idx = pd.date_range("2026-11-01", periods=20, freq="D")
    s1, s3 = pd.Series(range(20), index=idx, dtype=float), pd.Series(0.5, index=idx)
    params = {"x": 1}
    key24 = eg._cache_key("EURUSD", "fam", params, "2026-11-24", "H1")
    eg.cache_save(key24, s1, s3)
    bars = pd.DataFrame({"close": [1.0, 1.1]},
                        index=pd.DatetimeIndex(["2026-11-24 23:00", "2026-11-25 00:00"]))
    monkeypatch.setattr(eg, "_bars_for", lambda sym, tf="H1": bars)
    monkeypatch.setattr(eg, "timeframe_of", lambda p, f: "H1")
    monkeypatch.setattr(eg, "stage0_record", lambda *a, **k: None)
    spec = {"sym": "EURUSD", "family": "fam", "params": params}
    eg._PLAN_DATA_DAYS.clear()
    try:
        miss = eg._build_specs([spec], {}, time.time() - 10 ** 9, {}, {}, set(), [])
        assert miss["cache_hits"] == 0               # without the plan's day: a miss, deferred
        eg._PLAN_DATA_DAYS.update({"EURUSD|H1": "2026-11-24"})
        got = eg._build_specs([spec], {}, time.time() - 10 ** 9, {}, {}, set(), [])
    finally:
        eg._PLAN_DATA_DAYS.clear()
    assert got["cache_hits"] == 1 and not got["deferred"]
    cell = got["cell_objs"][0]
    assert cell["_ckey"] == key24 and str(cell["_last_day"].date()) == "2026-11-24"
    assert list(cell["_cached_ds"].to_numpy()) == list(s1.to_numpy())


def test_the_plan_carries_the_data_days_and_the_shard_restores_them() -> None:
    import inspect
    assert '"data_days": dict(_PLAN_DATA_DAYS)' in inspect.getsource(eg._run_shards)
    assert 'plan.get("data_days")' in inspect.getsource(eg.shard_worker)
