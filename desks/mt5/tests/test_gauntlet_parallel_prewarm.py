"""The gauntlet builds cells in parallel, and the ways a pool can quietly make things worse.

THE ARITHMETIC (2026-09-08): ~22s a cell, single-process, 45 minutes an hour -> ~123 cells an
hour, ~3,000 a day. The docket held 23,465 and the cache key rolls with the data day, so a cell
not rebuilt inside one day goes cold again. A single process was not slow; it was structurally
unable to converge that docket at all. Workers are the only exit, and they are the kind of change
that can silently break the one conversion step the desk has -- so every property that keeps the
pool honest is pinned here at source level, the way the desk pins its other money-adjacent
invariants (`test_self_certifying_caps`, `test_stall_watch_disk`).
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
SRC = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
TREE = ast.parse(SRC)


def _fn_source(name: str) -> str:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(SRC, node)
    raise AssertionError(f"{name} is not a module-level function")


# ----------------------------------------------------------------- the pool is sized off the box
def _worker_count_with(cores: int, budget_mb: float, per_worker_mb: float, env: dict) -> int:
    """Run the real `_worker_count` against a stubbed box."""
    class _OS:
        environ = env

        @staticmethod
        def cpu_count():
            return cores

    ns: dict = {"os": _OS, "MEMORY_BUDGET_MB": budget_mb, "PER_WORKER_MB": per_worker_mb}
    exec(textwrap.dedent(_fn_source("_worker_count")), ns)
    return ns["_worker_count"]()


def test_workers_are_bounded_by_cores_minus_one() -> None:
    assert _worker_count_with(cores=16, budget_mb=100_000, per_worker_mb=768, env={}) == 15


def test_workers_are_bounded_by_the_memory_budget() -> None:
    """8192MB at 768MB a worker admits 10, whatever the core count says."""
    assert _worker_count_with(cores=64, budget_mb=8192, per_worker_mb=768, env={}) == 10


def test_a_small_measured_budget_collapses_to_one_worker_and_the_old_behaviour() -> None:
    """The 8GB box's 1200MB budget cannot hold one 768MB worker beside the parent: 1 worker, so
    the pre-warm block is skipped and the sweep is what it was."""
    assert _worker_count_with(cores=8, budget_mb=1200, per_worker_mb=768, env={}) == 1


def test_a_single_core_box_never_goes_to_zero() -> None:
    assert _worker_count_with(cores=1, budget_mb=100_000, per_worker_mb=768, env={}) == 1


def test_the_env_override_wins_and_is_floored_at_one() -> None:
    assert _worker_count_with(cores=2, budget_mb=1, per_worker_mb=768,
                              env={"GAUNTLET_WORKERS": "6"}) == 6
    assert _worker_count_with(cores=64, budget_mb=100_000, per_worker_mb=768,
                              env={"GAUNTLET_WORKERS": "0"}) == 1


# ------------------------------------------------------------ the call site shares ONE budget
def test_the_prewarm_runs_before_the_spec_loop_and_only_with_workers() -> None:
    call = "_prewarm_cache(eligible_specs, meta, _build_t0 + FRESH_BUILD_BUDGET_SEC)"
    assert call in SRC
    assert SRC.index("if WORKERS > 1 and len(eligible_specs) > 1:") < SRC.index(call)
    assert SRC.index(call) < SRC.index("for spec in eligible_specs:")


def test_the_deadline_is_the_loop_s_own_clock_not_a_second_budget() -> None:
    """A pool with its own 45 minutes followed by a loop with another 45 breaks the hourly
    cadence. `_build_t0` is set once, before both, and both count from it."""
    t0_set = SRC.index("_build_t0 = time.time()")
    assert t0_set < SRC.index("_prewarm_cache(eligible_specs, meta, _build_t0")
    assert t0_set < SRC.index("if time.time() - _build_t0 > FRESH_BUILD_BUDGET_SEC:")
    assert SRC.count("_build_t0 = time.time()") == 1


def test_the_pool_s_work_is_in_the_report_beside_the_budgets() -> None:
    assert 'result["workers"] = WORKERS' in SRC
    assert 'result["prewarm"] = _prewarm' in SRC


# --------------------------------------------------------------- the worker is spawn-safe
def test_the_worker_and_the_pool_are_module_level_so_windows_spawn_can_pickle_them() -> None:
    for name in ("_warm_one", "_prewarm_cache", "_worker_count"):
        assert _fn_source(name)                    # raises if not module-level


def test_the_main_guard_exists_so_spawned_workers_do_not_re_run_the_sweep() -> None:
    assert 'if __name__ == "__main__":' in SRC


def test_the_worker_is_the_fresh_path_extracted_and_nothing_else() -> None:
    w = _fn_source("_warm_one")
    for step in ("_bars_for(sym, tf)", "_cache_key(sym, family, params, str(last_day.date()), tf)",
                 "build_cell(sym, family, params, meta)",
                 "daily_series(obj[\"df\"], obj[\"sigs\"], obj[\"costs\"])",
                 "costs_for(sym, meta, mult=COST_SCENARIO)", "cache_save(ckey, ds1, ds3)"):
        assert step in w, step
    assert "run_gauntlet(" not in w               # no verdict logic crosses into the worker


def test_a_cell_whose_3x_arm_fails_is_not_half_cached() -> None:
    w = _fn_source("_warm_one")
    assert '"FAIL_3X"' in w
    assert w.index('"FAIL_3X"') < w.index("cache_save(ckey, ds1, ds3)")


# ------------------------------------------------------------- order, backpressure, deadline
def test_specs_are_submitted_in_the_loop_s_order() -> None:
    """The loop rotates longest-unbuilt symbol first so deferral is self-correcting. A pool that
    reordered would rebuild the head of the docket every hour and never reach the tail."""
    p = _fn_source("_prewarm_cache")
    assert "it = iter(specs)" in p
    assert "sp = next(it, None)" in p


def test_at_most_two_by_workers_are_in_flight_so_the_deadline_can_actually_stop_it() -> None:
    p = _fn_source("_prewarm_cache")
    assert "for _ in range(2 * WORKERS):" in p
    assert "if time.time() <= deadline:" in p     # no new submission past the deadline
    assert "if f.cancel():" in p                  # not-yet-started work is cancelled, counted


def test_unreached_cells_are_counted_never_dropped() -> None:
    p = _fn_source("_prewarm_cache")
    assert 'summary["unreached"] += sum(1 for _ in it)' in p


# ------------------------------------------------------------------ the cache write is atomic
def test_cache_save_writes_a_temp_file_and_replaces() -> None:
    c = _fn_source("cache_save")
    assert 'tmp = CACHE_DIR / f"{key}.{os.getpid()}.tmp"' in c
    assert "os.replace(tmp, final)" in c
    assert 'with open(tmp, "wb") as fh:' in c     # a handle, so savez does not append .npz
    assert re.search(r"savez_compressed\(\s*fh", c)


def test_cache_load_treats_a_torn_file_as_a_miss() -> None:
    """Belt and braces: even if a torn .npz ever appeared, a load failure is a recompute."""
    c = _fn_source("cache_load")
    assert "except Exception:" in c and "return None" in c
