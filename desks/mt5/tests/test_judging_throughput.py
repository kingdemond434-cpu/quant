"""JUDGING THROUGHPUT -- the organ may only ever RAISE the judge, and the terminal outranks it.

What is fenced here, and why each one is the thing that would actually go wrong:

  * A DEEP QUEUE WITH HEADROOM RAISES WORKERS ABOVE THE SEALED BASELINE. This is the whole
    purpose. The sealed file's `HEADROOM_CAP_MB=8192` caps it at ten workers on any box, however
    large, so on an 18-core / 98 GB machine the baseline is 10 and the measured plan must exceed
    it. If this test ever passes trivially, the organ has stopped doing its job.
  * THE LIVE TERMINAL ALWAYS WINS, and winning means the plan RETURNS TO THE BASELINE -- never
    below it. "Protecting the box" by shrinking the gauntlet is forbidden, so the test asserts
    both halves: it stands down, AND it stands down to exactly the sealed number.
  * THE FLOOR HOLDS UNDER EVERY INPUT. A shallow queue, an unmeasurable counter, a tiny box: none
    of them may produce fewer workers than the sealed file would have chosen unaided.
  * THE ENV IS WHAT THE SEALED FILE READS. The decision is worthless unless it lands in
    GAUNTLET_WORKERS / GAUNTLET_MEMORY_BUDGET_MB / GAUNTLET_HEADROOM_CAP_MB, and an operator's
    own export outranks the organ.
  * UNMEASURED IS A REAL ANSWER (L1.28a): an absent backpressure artifact makes queue depth
    UNMEASURED, never an empty queue.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judging_throughput as jt  # noqa: E402

UNMEASURED = jt.UNMEASURED
COSTS = {"per_worker_mb": 768.0, "declared_need_mb": 1200.0}

#: The TRADING box as it was measured 2026-09-23: 18 cores, 98 GB, plenty of commit, terminal up.
#: Never this build box -- nothing in this suite may be sized from the machine it runs on.
BIG_BOX = {"cores": 18, "market_closed": False, "source": "GlobalMemoryStatusEx",
           "total_phys_mb": 98_298, "free_phys_mb": 59_364,
           "commit_limit_mb": 257_024, "commit_free_mb": 104_000,
           "terminal_running": True, "gateway_running": True, "n_python": 14,
           "terminal_source": "psutil", "is_judging_box": True}

DEEP_QUEUE = {"status": "MEASURED", "depth": 19_996, "gates_per_hour": 101.583,
              "workers_last_sweep": 1, "discovered": 21_391, "judged_last_sweep": 1_395}


def _box(**over):
    return {**BIG_BOX, **over}


# ------------------------------------------------------------- the raise, which is the point
def test_deep_queue_with_headroom_raises_workers_above_the_sealed_baseline() -> None:
    base = jt.sealed_baseline(BIG_BOX, COSTS)
    out = jt.plan(BIG_BOX, DEEP_QUEUE, COSTS)
    # The sealed ceiling is what binds the baseline on a big box: 8192 / 768 = 10 workers.
    assert base["workers"] == 10, "the sealed HEADROOM_CAP_MB is the ceiling this organ lifts"
    assert out["workers"] > base["workers"], "a deep queue on a 98 GB box must raise the judge"
    assert out["workers"] == 15, "18 cores less the 3 the terminal and gateway keep in session"
    assert out["raised_by"] == 5
    assert out["limiting_resource"] == "cores"
    assert out["stood_down"] is False
    # The budget must cover the workers it just authorised, or the sweep throttles itself.
    assert out["memory_budget_mb"] >= out["workers"] * COSTS["per_worker_mb"]
    assert out["cadence_minutes"] == jt.CADENCE_FAST_MIN, "a deep queue earns the faster clock"
    assert out["queue_deep"] is True


def test_the_weekend_gives_every_core_to_the_judge() -> None:
    out = jt.plan(_box(market_closed=True), DEEP_QUEUE, COSTS)
    assert out["workers"] == 18, "nothing trades Friday 21:00 to Sunday 21:00; no core is reserved"


def test_projected_gates_per_hour_and_days_to_drain_are_published() -> None:
    out = jt.plan(BIG_BOX, DEEP_QUEUE, COSTS)
    # 15 workers against the 1 the last sweep ran, and the cadence doubles on top of it.
    assert out["gates_per_hour_before"] == 101.583
    assert out["gates_per_hour_projected"] > out["gates_per_hour_before"]
    assert isinstance(out["days_to_drain_queue"], float)
    assert out["days_to_drain_queue"] > 0


# ---------------------------------------------------------------- the terminal always wins
def test_a_starved_terminal_stands_the_plan_down_to_the_baseline_and_no_lower() -> None:
    starved = _box(free_phys_mb=900)          # under two workers' budget (1536 MB)
    base = jt.sealed_baseline(starved, COSTS)
    out = jt.plan(starved, DEEP_QUEUE, COSTS)
    assert out["stood_down"] is True
    assert out["limiting_resource"] == "live_terminal"
    assert out["workers"] == base["workers"], "standing down returns to the sealed number"
    assert out["cadence_minutes"] == jt.CADENCE_BASE_MIN
    assert "live terminal" in out["why"]


def test_an_unseeable_terminal_in_session_stands_down_rather_than_taking_its_cores() -> None:
    blind = _box(terminal_running=UNMEASURED, terminal_source=UNMEASURED)
    out = jt.plan(blind, DEEP_QUEUE, COSTS)
    assert out["stood_down"] is True
    assert out["workers"] == jt.sealed_baseline(blind, COSTS)["workers"]


def test_an_unseeable_terminal_at_the_weekend_does_not_stand_down() -> None:
    blind = _box(terminal_running=UNMEASURED, market_closed=True)
    assert jt.plan(blind, DEEP_QUEUE, COSTS)["stood_down"] is False


# ------------------------------------------------------- the floor: this organ cannot throttle
def test_the_plan_is_never_below_the_sealed_baseline_on_any_box() -> None:
    for box in (BIG_BOX,
                _box(free_phys_mb=900),
                _box(commit_free_mb=1_000),
                _box(cores=4, total_phys_mb=8_186, free_phys_mb=3_900, is_judging_box=False),
                _box(free_phys_mb=UNMEASURED, commit_free_mb=UNMEASURED, source=UNMEASURED),
                _box(market_closed=True)):
        for queue in (DEEP_QUEUE, {"status": UNMEASURED, "depth": UNMEASURED},
                      {"status": "MEASURED", "depth": 0, "gates_per_hour": 0.0,
                       "workers_last_sweep": 1}):
            out = jt.plan(box, queue, COSTS)
            assert out["workers"] >= jt.sealed_baseline(box, COSTS)["workers"], (
                "no input may make this organ hand the judge fewer workers than the sealed file "
                "would have chosen by itself")


def test_a_shallow_queue_names_the_queue_as_the_limit_and_still_holds_the_floor() -> None:
    shallow = {"status": "MEASURED", "depth": 2, "gates_per_hour": 50.0, "workers_last_sweep": 4}
    out = jt.plan(BIG_BOX, shallow, COSTS)
    assert out["limiting_resource"] == "queue"
    assert out["workers"] >= jt.sealed_baseline(BIG_BOX, COSTS)["workers"]
    assert out["cadence_minutes"] == jt.CADENCE_BASE_MIN


# ----------------------------------------------------------------- measurement and the env
def test_an_absent_backpressure_artifact_is_unmeasured_not_an_empty_queue(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(jt, "BACKPRESSURE", tmp_path / "nope.json")
    q = jt.measure_queue()
    assert q["status"] == UNMEASURED
    assert q["depth"] == UNMEASURED
    assert q["gates_per_hour"] == UNMEASURED


def test_queue_depth_is_read_from_the_gauntlets_own_artifact(tmp_path, monkeypatch) -> None:
    doc = {"capacity": {"declared": {"per_worker_mb": 768.0, "declared_need_mb": 1200.0},
                        "measured": {"n_cells_discovered": 21_391, "n_judged": 1_395,
                                     "workers": 1, "n_cells_deferred_build_budget": 3_490}},
           "windows": {"24h": {"testing": {"per_hour": 101.583}}}}
    path = tmp_path / "GAUNTLET_BACKPRESSURE.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(jt, "BACKPRESSURE", path)
    q = jt.measure_queue()
    assert q["status"] == "MEASURED"
    assert q["depth"] == 21_391 - 1_395
    assert q["gates_per_hour"] == 101.583
    assert q["deferred_build_budget"] == 3_490
    assert jt.declared_costs() == {"per_worker_mb": 768.0, "declared_need_mb": 1200.0}


def test_the_env_carries_exactly_what_the_sealed_file_reads(tmp_path) -> None:
    decision = jt.plan(BIG_BOX, DEEP_QUEUE, COSTS)
    env = jt.env_for(decision)
    assert env["GAUNTLET_WORKERS"] == str(decision["workers"])
    assert int(env["GAUNTLET_MEMORY_BUDGET_MB"]) >= decision["workers"] * 768
    assert int(env["GAUNTLET_HEADROOM_CAP_MB"]) >= decision["workers"] * 768
    assert env["WARM_WORKERS"] == str(decision["warm_workers"])
    path = tmp_path / "judging_throughput.env.json"
    jt.write_env(decision, path)
    target: dict[str, str] = {}
    applied = jt.apply_env(path, target)
    assert applied == env
    assert target["GAUNTLET_WORKERS"] == env["GAUNTLET_WORKERS"]


def test_an_operators_own_export_outranks_the_organ(tmp_path) -> None:
    decision = jt.plan(BIG_BOX, DEEP_QUEUE, COSTS)
    path = tmp_path / "env.json"
    jt.write_env(decision, path)
    target = {"GAUNTLET_WORKERS": "2"}
    jt.apply_env(path, target)
    assert target["GAUNTLET_WORKERS"] == "2", "a hand-set variable is never overwritten"


def test_a_build_box_never_writes_machine_scope_or_touches_the_task() -> None:
    small = _box(cores=4, total_phys_mb=8_186, is_judging_box=False)
    decision = jt.plan(small, DEEP_QUEUE, COSTS)
    assert jt.apply_machine_env(decision, small)["status"] == "NOT_APPLIED"
    assert jt.apply_cadence(5, small)["status"] == "NOT_APPLIED"


def test_market_closed_matches_the_sealed_rule() -> None:
    from datetime import UTC, datetime
    assert jt.market_closed(datetime(2026, 9, 18, 21, 30, tzinfo=UTC)) is True   # Friday 21:30
    assert jt.market_closed(datetime(2026, 9, 19, 12, 0, tzinfo=UTC)) is True    # Saturday
    assert jt.market_closed(datetime(2026, 9, 20, 20, 0, tzinfo=UTC)) is True    # Sunday 20:00
    assert jt.market_closed(datetime(2026, 9, 20, 22, 0, tzinfo=UTC)) is False   # Sunday 22:00
    assert jt.market_closed(datetime(2026, 9, 23, 12, 0, tzinfo=UTC)) is False   # Wednesday
