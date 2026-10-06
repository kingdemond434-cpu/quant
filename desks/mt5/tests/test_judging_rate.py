"""JUDGING RATE + measured free cores: verdicts/hour vs backlog, and workers only ever rise."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judging_throughput as jt  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_coverage_dependency(tmp_path, monkeypatch):
    """A live coverage file must never replace a fixture's backlog during a rate test."""
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", tmp_path / "absent_coverage.json")
    monkeypatch.setattr(jt, "task_time_limit_s", lambda *a, **k: None)


UNMEASURED = jt.UNMEASURED
COSTS = {"per_worker_mb": 768.0, "declared_need_mb": 1200.0}
BOX = {"cores": 18, "market_closed": False, "source": "GlobalMemoryStatusEx",
       "total_phys_mb": 98_298, "free_phys_mb": 59_364, "commit_limit_mb": 257_024,
       "commit_free_mb": 104_000, "terminal_running": True, "is_judging_box": True}
QUEUE = {"status": "MEASURED", "depth": 19_996, "gates_per_hour": 100.0,
         "workers_last_sweep": 1}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------ free cores, measured
def test_an_idle_box_gives_the_judge_the_cores_the_fixed_reservation_held_back() -> None:
    fixed = jt.plan(BOX, QUEUE, COSTS)
    measured = jt.plan({**BOX, "busy_other_cores": 0.4}, QUEUE, COSTS)
    assert fixed["workers"] == 15 and fixed["cores_basis"] == "fixed_reservation"
    # 0.4 busy x 1.5 -> reserve 1 core: 17 workers instead of 15.
    assert measured["workers"] == 17
    assert measured["cores_basis"] == "measured_free_cores"
    assert measured["reserved_cores"] == 1


def test_a_busy_box_never_costs_the_judge_a_worker() -> None:
    fixed = jt.plan(BOX, QUEUE, COSTS)
    for busy in (2.5, 6.0, 17.9, 40.0):
        got = jt.plan({**BOX, "busy_other_cores": busy}, QUEUE, COSTS)
        assert got["workers"] >= fixed["workers"], busy
        assert got["workers"] >= got["baseline"]["workers"]


def test_unmeasured_cpu_and_the_weekend_leave_the_plan_unchanged() -> None:
    assert (jt.plan({**BOX, "busy_other_cores": UNMEASURED}, QUEUE, COSTS)["workers"]
            == jt.plan(BOX, QUEUE, COSTS)["workers"])
    closed = {**BOX, "market_closed": True}
    assert (jt.plan({**closed, "busy_other_cores": 0.0}, QUEUE, COSTS)["workers"]
            == jt.plan(closed, QUEUE, COSTS)["workers"] == 18)


def test_a_starved_terminal_still_stands_down_to_the_baseline() -> None:
    got = jt.plan({**BOX, "free_phys_mb": 1_000, "busy_other_cores": 0.0}, QUEUE, COSTS)
    assert got["stood_down"] and got["workers"] == got["baseline"]["workers"]


def test_measure_cpu_is_psutil_or_unmeasured() -> None:
    got = jt.measure_cpu(sample_s=0.1)
    if got["cpu_source"] == "psutil":
        assert isinstance(got["busy_other_cores"], float) and got["busy_other_cores"] >= 0
    else:
        assert got["busy_other_cores"] == UNMEASURED


# ------------------------------------------------------------------ the rate artifact
def _ledger(path: Path, stamps: list[datetime]) -> Path:
    path.write_text("".join(json.dumps({"cell": i, "terminal_gate": "PASSED",
                                       "at": t.isoformat(timespec="seconds")})
                            + "\n" for i, t in enumerate(stamps)) + '{"cell": "x"}\n', "utf-8")
    return path


def test_retests_and_unknowns_do_not_count_as_backlog_cleared(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"cell": "old", "at": (NOW - timedelta(days=10)).isoformat(),
         "terminal_gate": "in_sample_screen"},
        {"cell": "old", "at": NOW.isoformat(), "terminal_gate": "stress_costs"},
        {"cell": "blocked", "at": NOW.isoformat(), "terminal_gate": "UNKNOWN"},
        {"cell": "new", "at": NOW.isoformat(), "terminal_gate": "PASSED"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    got = jt.measure_rate({"depth": 100}, {}, NOW, ledger=path,
                          registry=_registry(tmp_path / "registry.sqlite", []))
    assert got["verdicts"]["counts"]["24h"] == 3
    assert got["verdicts"]["first_terminal_counts"]["24h"] == 1
    assert got["verdicts"]["first_terminal_cells"] == 2
    assert got["eta_to_drain"]["net_per_hour"] < got["verdicts_per_hour"]


def test_stale_coverage_cannot_replace_current_queue_depth(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps({"at": (NOW - timedelta(days=3)).isoformat(),
                                "totals": {"unjudged_total": 999999}}), "utf-8")
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", path)
    got = jt.measure_rate({"depth": 8}, {}, NOW, ledger=tmp_path / "absent",
                          registry=tmp_path / "absent.sqlite")
    assert got["backlog"] == 8
    assert got["coverage_backlog_fresh"] is False


def test_verdict_windows_normalise_offsets_and_refuse_future_stamps(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"cell": "recent", "at": "2026-09-30T13:30:00+02:00", "terminal_gate": "PASSED"},
        {"cell": "old", "at": "2026-09-30T11:30:00+02:00", "terminal_gate": "PASSED"},
        {"cell": "future", "at": "2026-09-30T12:30:00Z", "terminal_gate": "PASSED"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    got = jt._verdict_counts(NOW, path)
    assert got["counts"] == {"1h": 1, "24h": 2, "7d": 2}
    assert got["rows_unstamped"] == 1


def _registry(path: Path, stamps: list[datetime]) -> Path:
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE research_candidates (id INTEGER, created_at TEXT)")
    c.executemany("INSERT INTO research_candidates VALUES (?, ?)",
                  [(i, t.isoformat(timespec="seconds")) for i, t in enumerate(stamps)])
    c.commit()
    c.close()
    return path


def test_rate_counts_windows_and_drains(tmp_path: Path) -> None:
    ver = [NOW - timedelta(minutes=10)] * 5 + [NOW - timedelta(hours=5)] * 43 \
        + [NOW - timedelta(days=3)] * 100
    cre = [NOW - timedelta(hours=2)] * 24
    got = jt.measure_rate({"depth": 1_000, "source": "bp"}, {"workers": 15}, NOW,
                          ledger=_ledger(tmp_path / "l.jsonl", ver),
                          registry=_registry(tmp_path / "r.sqlite", cre))
    assert got["verdicts"]["counts"] == {"1h": 5, "24h": 48, "7d": 148}
    assert got["verdicts"]["rows_unstamped"] == 1
    assert got["verdicts_per_hour"] == 2.0 and got["verdicts_per_day"] == 48.0
    assert got["created_per_day"] == 24.0
    eta = got["eta_to_drain"]
    assert eta["status"] == "DRAINING" and eta["net_per_hour"] == 1.0 and eta["hours"] == 1000.0


def test_a_judge_slower_than_creation_is_growing_not_a_big_number(tmp_path: Path) -> None:
    got = jt.measure_rate({"depth": 55_811}, {"workers": 15}, NOW,
                          ledger=_ledger(tmp_path / "l.jsonl", []),
                          registry=_registry(tmp_path / "r.sqlite",
                                             [NOW - timedelta(hours=1)] * 1_032))
    assert got["verdicts_per_day"] == 0.0 and got["created_per_day"] == 1_032.0
    assert got["eta_to_drain"]["status"] == "GROWING"
    assert got["eta_to_drain"]["hours"] is None
    assert got["eta_to_drain"]["net_per_day"] == -1_032.0


def test_absent_inputs_are_unmeasured_never_zero(tmp_path: Path) -> None:
    got = jt.measure_rate({"depth": UNMEASURED}, {}, NOW, ledger=tmp_path / "none.jsonl",
                          registry=tmp_path / "none.sqlite")
    assert got["verdicts"]["status"] == UNMEASURED
    assert got["created"]["status"] == UNMEASURED
    assert got["verdicts_per_hour"] == UNMEASURED
    assert got["eta_to_drain"]["status"] == UNMEASURED


def test_run_publishes_the_rate_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jt, "OUT", tmp_path / "JUDGING_THROUGHPUT.json")
    monkeypatch.setattr(jt, "RATE_OUT", tmp_path / "JUDGING_RATE.json")
    monkeypatch.setattr(jt, "ENV_FILE", tmp_path / "env.json")
    monkeypatch.setattr(jt, "BACKPRESSURE", tmp_path / "bp.json")
    monkeypatch.setattr(jt, "GATE_LEDGER", _ledger(tmp_path / "l.jsonl", [NOW]))
    monkeypatch.setattr(jt, "REGISTRY", tmp_path / "none.sqlite")
    monkeypatch.setattr(jt, "measure_cpu", lambda *a, **k: {"cpu_source": UNMEASURED,
                                                             "busy_other_cores": UNMEASURED})
    monkeypatch.setattr(jt, "apply_env", lambda *a, **k: {})
    payload = jt.run(write=True, now=NOW, apply=False)
    rate = json.loads((tmp_path / "JUDGING_RATE.json").read_text("utf-8"))
    assert rate["verdicts"]["counts"]["1h"] == 1
    assert rate["backlog"] == UNMEASURED
    assert payload["rate"]["eta_to_drain"]["status"] == UNMEASURED


# ------------------------------------------------ publish first, then a bounded best-effort apply
def _isolate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jt, "OUT", tmp_path / "JUDGING_THROUGHPUT.json")
    monkeypatch.setattr(jt, "RATE_OUT", tmp_path / "JUDGING_RATE.json")
    monkeypatch.setattr(jt, "ENV_FILE", tmp_path / "env.json")
    monkeypatch.setattr(jt, "BACKPRESSURE", tmp_path / "bp.json")
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "bd.json")
    monkeypatch.setattr(jt, "GATE_LEDGER", _ledger(tmp_path / "l.jsonl", [NOW]))
    monkeypatch.setattr(jt, "REGISTRY", tmp_path / "none.sqlite")
    monkeypatch.setattr(jt, "measure_cpu", lambda *a, **k: {"cpu_source": UNMEASURED,
                                                             "busy_other_cores": UNMEASURED})
    monkeypatch.setattr(jt, "apply_env", lambda *a, **k: {})
    monkeypatch.setattr(jt, "task_time_limit_s", lambda *a, **k: None)


def test_every_artifact_is_on_disk_before_the_apply_runs(tmp_path: Path, monkeypatch) -> None:
    """CRO 2026-09-30: `schtasks /Change` sat ahead of the writes and timed out at 60 s, so the
    leg died past its budget and JUDGING_RATE.json went 4.4 h stale. Writes come first now."""
    _isolate(tmp_path, monkeypatch)
    seen: dict[str, bool] = {}

    def _machine(decision, box):
        seen["rate"] = (tmp_path / "JUDGING_RATE.json").exists()
        seen["out"] = (tmp_path / "JUDGING_THROUGHPUT.json").exists()
        seen["env"] = (tmp_path / "env.json").exists()
        raise TimeoutError("setx hung")

    monkeypatch.setattr(jt, "apply_machine_env", _machine)
    monkeypatch.setattr(jt, "apply_cadence", lambda m, box: {"status": "APPLIED", "minutes": m})
    payload = jt.run(write=True, now=NOW, apply=True)
    assert seen == {"rate": True, "out": True, "env": True}
    doc = json.loads((tmp_path / "JUDGING_THROUGHPUT.json").read_text("utf-8"))
    assert doc["applied"]["machine_env"]["status"] == "FAILED"
    assert "setx hung" in doc["applied"]["machine_env"]["why"]
    assert doc["applied"]["cadence"]["status"] == "APPLIED", "one failed step skips no other"
    assert payload["seconds"] >= payload["measure_seconds"] >= 0


def test_the_apply_budget_bounds_every_subprocess() -> None:
    import time
    assert jt._sub_timeout() == jt.SUBPROCESS_TIMEOUT_S
    jt._APPLY_DEADLINE[:] = [time.monotonic() + 5.0]
    try:
        assert 1.0 < jt._sub_timeout() <= 5.0
        jt._APPLY_DEADLINE[:] = [time.monotonic()]
        try:
            jt._sub_timeout()
            raise AssertionError("a spent budget must refuse the next call")
        except TimeoutError:
            pass
    finally:
        jt._APPLY_DEADLINE[:] = []
    assert jt.SUBPROCESS_TIMEOUT_S * 2 + jt.APPLY_BUDGET_S < 300, "inside the 300 s leg budget"


def test_a_growing_backlog_is_demand_on_the_judge(tmp_path: Path, monkeypatch) -> None:
    """JUDGING_BURNDOWN.json is consumed here: GROWING raises cadence exactly as a deep queue."""
    monkeypatch.setattr(jt, "BURNDOWN", tmp_path / "bd.json")
    (tmp_path / "bd.json").write_text(json.dumps(
        {"burn_down": {"status": "GROWING", "net_per_day": -3000.0}}), encoding="utf-8")
    bd = jt._burndown()
    assert bd["burndown_status"] == "GROWING"
    shallow = {**QUEUE, "depth": 1, **bd}
    d = jt.plan(BOX, shallow, COSTS)
    assert d["limiting_resource"] == "backlog_growing"
    assert d["cadence_minutes"] == jt.CADENCE_FAST_MIN
    (tmp_path / "bd.json").unlink()
    assert jt._burndown()["burndown_status"] == UNMEASURED


def test_the_warmer_is_no_longer_pinned_through_the_env(tmp_path: Path) -> None:
    d = jt.plan(BOX, QUEUE, COSTS)
    assert "WARM_WORKERS" not in jt.env_for(d)
    assert "WARM_WORKERS" not in jt.ENV_KEYS
    assert "WARM_WORKERS" in jt.RETIRED_MACHINE_KEYS


@pytest.mark.parametrize("age_hours,expected", [(48, 100), (0.25, 999), (-0.25, 100)])
def test_stale_or_future_coverage_cannot_replace_backlog(
        tmp_path, monkeypatch, age_hours, expected):
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps({"at": (NOW-timedelta(hours=age_hours)).isoformat(),
                                   "totals": {"unjudged_total": 999}}))
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", coverage)
    got = jt.measure_rate({"depth":100}, {}, NOW,
                          ledger=_ledger(tmp_path/"ledger.jsonl", [NOW]),
                          registry=_registry(tmp_path/"registry.sqlite", []))
    assert got["backlog"] == expected


def test_recent_births_use_an_indexed_range_not_a_registry_table_scan(tmp_path: Path) -> None:
    """A multi-GB unindexed created_at count timed out judging-rate production."""
    from libs.moat import registry

    path = tmp_path / "registry.sqlite"
    conn = sqlite3.connect(path)
    registry._evolve(conn)
    conn.executemany(
        "INSERT INTO research_candidates(id, created_at) VALUES (?, ?)",
        [("old", "2026-09-20T00:00:00+00:00"),
         ("week", "2026-09-28T00:00:00+00:00"),
         ("day", "2026-09-30T11:00:00+00:00")],
    )
    conn.commit()
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM research_candidates WHERE created_at >= ?",
        ("2026-09-23T00:00:00+00:00",),
    ).fetchall()
    assert any("ix_candidates_created_at" in str(row) for row in plan), plan
    conn.close()
    assert jt._creation_counts(NOW, path)["counts"] == {"24h": 1, "7d": 2}


def test_sweep_remainder_cannot_masquerade_as_full_backlog(tmp_path):
    got = jt.measure_rate({"depth": 59_834, "depth_scope": "sweep"}, {}, NOW,
                          ledger=tmp_path / "absent.jsonl",
                          registry=tmp_path / "absent.sqlite")
    assert got["backlog"] == UNMEASURED
    assert got["eta_to_drain"]["status"] == UNMEASURED


def test_fresh_full_coverage_replaces_sweep_remainder(tmp_path, monkeypatch):
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps({"at": NOW.isoformat(),
                                   "totals": {"unjudged_total": 1_601_468}}), "utf-8")
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", coverage)
    got = jt.measure_rate({"depth": 59_834, "depth_scope": "sweep"}, {}, NOW,
                          ledger=tmp_path / "absent.jsonl",
                          registry=tmp_path / "absent.sqlite")
    assert got["backlog"] == 1_601_468


def _reference_verdict_counts(now: datetime, path: Path) -> dict:
    """The pre-streaming implementation's first-terminal rule, kept as the oracle."""
    from research.judging_burndown import classify
    cuts = {w: (now - timedelta(hours=h)).isoformat(timespec="seconds")
            for w, h in (("1h", 1), ("24h", 24), ("7d", 168))}
    first = dict.fromkeys(cuts, 0)
    seen: set[str] = set()
    for line in path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        try:
            stamp = datetime.fromisoformat(str(row.get("at")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp.tzinfo is None or stamp > now:
            continue
        at = stamp.astimezone(UTC).isoformat(timespec="seconds")
        cell = str(row.get("cell", ""))
        if not cell or classify(row) != "ruled" or cell in seen:
            continue
        seen.add(cell)
        for w, cut in cuts.items():
            if at >= cut:
                first[w] += 1
    return {"first": first, "cells": len(seen)}


def _synthetic_ledger(path: Path, n_old: int, n_new: int, seed: int = 7) -> None:
    import random
    rnd = random.Random(seed)  # noqa: S311 -- synthetic fixture data
    gates = ["PASSED", "deflated_sharpe", "cpcv", "UNKNOWN"]
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n_old):
            at = NOW - timedelta(days=8 + rnd.random() * 30)
            fh.write(json.dumps({"cell": f"OLD{i}.fam.{{\"p\": {i}}}", "at": at.isoformat(),
                                 "terminal_gate": rnd.choice(gates)}) + "\n")
        for i in range(n_new):
            # half re-judge an old cell (not a first terminal), half are new cells
            cell = (f"OLD{rnd.randrange(max(n_old, 1))}.fam.{{\"p\": 0}}" if i % 2
                    else f"NEW{i % 97}")
            at = NOW - timedelta(hours=rnd.random() * 200)
            fh.write(json.dumps({"cell": cell, "at": at.isoformat(),
                                 "terminal_gate": rnd.choice(gates)}) + "\n")


def test_streamed_first_terminal_counts_equal_the_in_memory_rule(tmp_path, monkeypatch) -> None:
    path = tmp_path / "ledger.jsonl"
    _synthetic_ledger(path, 3000, 2000)
    monkeypatch.setattr(jt, "VERDICT_HASH_CHUNK", 257)       # force many spilled chunks
    got = jt._verdict_counts(NOW, path)
    ref = _reference_verdict_counts(NOW, path)
    assert got["first_terminal_counts"] == ref["first"]
    assert got["first_terminal_cells"] == ref["cells"]


def test_verdict_count_memory_is_bounded_by_the_window_not_the_history(tmp_path,
                                                                      monkeypatch) -> None:
    """Ten times the history must not cost ten times the memory: the peak is the window plus one
    hash chunk. The old implementation held every cell id string, ~linear in history."""
    import tracemalloc
    monkeypatch.setattr(jt, "VERDICT_HASH_CHUNK", 4096)

    def peak(n_old: int) -> int:
        path = tmp_path / f"ledger_{n_old}.jsonl"
        _synthetic_ledger(path, n_old, 500)
        tracemalloc.start()
        jt._verdict_counts(NOW, path)
        _cur, top = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return top

    small, large = peak(20_000), peak(200_000)
    # 200k distinct ids as a str set alone is > 20 MB; the streamed count stays near-flat.
    assert large < 4 * 1024 * 1024
    assert large < small * 2
