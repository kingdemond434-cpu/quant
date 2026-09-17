"""The three moat swarms: yield-weighted seconds with a floor, costed children, one lock each.

WHAT THESE PIN, and why each one is here rather than trusted. (1) The allocation: a productive
engine gets more seconds, a junk-producing one fewer, NOBODY gets zero, and a generator the
yield table has never seen gets its cold share -- the whole point of M19, and the one number a
future edit can silently invert. (2) That an engine this tree does not carry is REPORTED, never
run and never counted as a clean zero. (3) That every child closes a compute-ledger run, so
`research_runs` sees the swarm's work -- the defect the canonical registry was raised for. (4)
The heartbeat, the report's shape, the singleton lock and that --dry-run writes nothing.

The child process is stubbed at `_spawn`, which is the module's one door to the box: the test
measures what the swarm DECIDED, and the engines have their own suites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import moat_swarms as ms  # noqa: E402

from libs.moat import registry as reg  # noqa: E402
from libs.ops import compute_ledger as cl  # noqa: E402

EXPLOIT = ("card_explosion", "alpha_recombination", "forward_exploitation", "descendants")


def _plant(root: Path, scripts: list[str]) -> None:
    """Put the engine files where `resolve` looks. Their contents never run: `_spawn` is stubbed."""
    for rel in scripts:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# stub engine\n", encoding="utf-8")


def _scripts_of(swarm: str) -> list[str]:
    return [str(e["script"]) for e in ms.SWARMS[swarm]["engines"]]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A tmp registry, a tmp compute ledger, tmp locks/logs/report and a stubbed child runner."""
    reg.set_path(tmp_path / "registry.sqlite")
    monkeypatch.setattr(cl, "LEDGER", tmp_path / "compute_ledger.jsonl")
    monkeypatch.setattr(ms, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(ms, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(ms, "OUT", tmp_path / "MOAT_SWARMS.json")
    monkeypatch.setattr(ms, "DESK", tmp_path / "desk")
    monkeypatch.setattr(ms, "REPO", tmp_path / "repo")
    monkeypatch.setattr(ms, "free_phys_mb", lambda: None)
    calls: list[dict] = []

    def fake_spawn(cmd, cwd, timeout_s):
        calls.append({"cmd": [str(c) for c in cmd], "cwd": Path(cwd),
                      "timeout_s": float(timeout_s)})
        return {"rc": 0, "seconds": 0.5, "status": "ok", "tail": "stub"}

    monkeypatch.setattr(ms, "_spawn", fake_spawn)
    try:
        yield {"tmp": tmp_path, "calls": calls}
    finally:
        reg.set_path(None)


def _budget_of(calls: list[dict], stem: str) -> float:
    for c in calls:
        if stem in c["cmd"][4]:
            return float(c["cmd"][c["cmd"].index("--budget-s") + 1])
    raise AssertionError(f"no child was started for {stem}: {[c['cmd'][4] for c in calls]}")


# --------------------------------------------------------------------------- the allocation
def test_budget_follows_measured_yield_and_never_falls_below_the_floor(desk):
    """Y_g orders the seconds; the floor and the cold share keep every engine alive."""
    reg.generator_yield_update("card_explosion", generated=100, independent_survivors=40)
    reg.generator_yield_update("alpha_recombination", generated=100, independent_survivors=1)
    reg.generator_yield_update("forward_exploitation", generated=50, independent_survivors=10)
    # `descendants` is deliberately absent from the table: it is COLD.
    table, unmeasured = ms.generator_yields()
    assert unmeasured == []
    rows, rule, floor_cost = ms.allocate(list(ms.SWARMS["exploit"]["engines"]), table, 1000.0)
    got = {r["engine"]: r for r in rows}
    assert got["card_explosion"]["yields"]["yield"] == pytest.approx(0.40)
    assert got["descendants"]["yields"]["yield"] is None
    assert got["descendants"]["basis"] == "cold" and got["card_explosion"]["basis"] == "measured"
    # productive > mediocre > junk, and the cold engine is screened rather than starved
    assert (got["card_explosion"]["budget_s"] > got["forward_exploitation"]["budget_s"]
            > got["alpha_recombination"]["budget_s"])
    assert all(r["budget_s"] >= ms.FLOOR_SHARE * 1000.0 for r in rows)
    assert got["descendants"]["share"] == pytest.approx(
        ms.FLOOR_SHARE + ms.COLD_SHARE + (1 - 4 * ms.FLOOR_SHARE - ms.COLD_SHARE)
        * ms.PRIOR / (0.40 + 0.01 + 0.20 + 4 * ms.PRIOR), abs=1e-4)
    assert sum(r["budget_s"] for r in rows) == pytest.approx(1000.0, abs=4.0)
    assert floor_cost > 0.0                       # the rail's cost to the best engine is priced
    assert "floor" in rule and "Y_g" in rule


def test_an_empty_yield_table_splits_evenly_and_says_so(desk):
    """Nothing measured is not a ranking. Every engine is cold, so every engine gets the same."""
    rows, rule, _cost = ms.allocate(list(ms.SWARMS["resurrect"]["engines"]), {}, 600.0)
    assert {r["basis"] for r in rows} == {"cold"}
    assert len({r["budget_s"] for r in rows}) == 1
    assert "Y_g" in rule


# --------------------------------------------------------------------------- one pass
def test_once_runs_the_swarms_engines_with_yield_weighted_budgets(desk):
    """--once: four engines plus the compiler, each a child carrying its own budget."""
    _plant(desk["tmp"] / "desk", [*_scripts_of("exploit"), "research/discovery_compiler.py"])
    reg.generator_yield_update("card_explosion", generated=100, independent_survivors=90)
    reg.generator_yield_update("descendants", generated=100, independent_survivors=0)
    assert ms.main(["--swarm", "exploit", "--once", "--budget-s", "1000"]) == 0
    calls = desk["calls"]
    assert len(calls) == 5                                    # four engines, then the compiler
    assert "discovery_compiler.py" in calls[-1]["cmd"][4]      # the join runs LAST, by design
    assert _budget_of(calls, "moat_card_explosion.py") > _budget_of(calls, "descendants.py")
    # the child is stopped at its own budget plus the grace, never at the budget itself
    assert calls[0]["timeout_s"] == pytest.approx(
        _budget_of(calls, "moat_card_explosion.py") + ms.GRACE_S)


def test_an_absent_engine_is_named_not_crashed(desk):
    """ABSENCE IS NEVER A PASS: a script under neither root is MISSING, with both roots named."""
    _plant(desk["tmp"] / "desk", ["research/moat_card_explosion.py"])
    assert ms.main(["--swarm", "exploit", "--once", "--budget-s", "400"]) == 0
    doc = json.loads((desk["tmp"] / "MOAT_SWARMS.json").read_text(encoding="utf-8"))
    engines = {e["engine"]: e for e in doc["swarms"]["exploit"]["engines"]}
    assert engines["card_explosion"]["status"] == "ok"
    for name in ("alpha_recombination", "forward_exploitation", "descendants"):
        assert engines[name]["status"] == "MISSING"
        assert "exists under neither" in engines[name]["why"]
    assert doc["swarms"]["exploit"]["compiler"]["status"] == "MISSING"
    assert len(desk["calls"]) == 1                            # only the engine that exists ran


def test_every_engine_closes_a_compute_run(desk):
    """`research_runs` sees the swarm's work -- the chain the canonical registry was raised for."""
    _plant(desk["tmp"] / "desk", [*_scripts_of("resurrect"), "research/discovery_compiler.py"])
    assert ms.main(["--swarm", "resurrect", "--once", "--budget-s", "300"]) == 0
    conn = reg.connect()
    try:
        names = [str(r["name"]) for r in conn.execute("SELECT name FROM research_runs")]
        organs = {str(r["organ"]) for r in conn.execute("SELECT organ FROM research_runs")}
    finally:
        conn.close()
    assert "moat_resurrect:graveyard_resurrection" in names
    assert "moat_resurrect:discovery_compiler" in names
    assert organs == {"moat_swarm"}
    ledger = [json.loads(line) for line in
              (desk["tmp"] / "compute_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["outcome"] for r in ledger} == {"ok"}
    assert {r["swarm"] for r in ledger} == {"resurrect"}
    # the seconds each engine spent go back into the yield table's denominator
    paid = {r["generator"]: r["compute_s"] for r in reg.generator_yields()}
    assert paid.get("graveyard_resurrection", 0.0) > 0.0


def test_the_swarm_heartbeats_as_a_registry_worker(desk):
    """One worker row per swarm, so three concurrent swarms are three visible workers.

    The row is RUNNING while the pass runs -- which is when the report reads it -- and STOPPED
    when the resident exits cleanly. Both are the measurement: a swarm that died without saying
    so leaves `running` and a stale `last_seen`, which is what `workers_alive` exists to expose.
    """
    _plant(desk["tmp"] / "desk", _scripts_of("explore"))
    assert ms.main(["--swarm", "explore", "--once", "--budget-s", "300"]) == 0
    doc = json.loads((desk["tmp"] / "MOAT_SWARMS.json").read_text(encoding="utf-8"))
    published = {w["worker_id"]: w for w in doc["workers"]}
    assert "moat:explore" in published and published["moat:explore"]["status"] == "running"
    conn = reg.connect()
    try:
        row = dict(conn.execute("SELECT * FROM workers WHERE worker_id=?",
                                ("moat:explore",)).fetchone())
    finally:
        conn.close()
    assert row["kind"] == "moat_swarm" and row["department"] == "moat_explore"
    assert row["status"] == "stopped" and int(row["campaigns_done"]) >= 1


def test_report_carries_the_swarm_the_rule_and_the_box_task_rows(desk):
    """The artifact the desk reads: engines, yields, rule, workers, and the manifest rows."""
    _plant(desk["tmp"] / "desk", _scripts_of("exploit"))
    assert ms.main(["--swarm", "exploit", "--once", "--budget-s", "500"]) == 0
    doc = json.loads((desk["tmp"] / "MOAT_SWARMS.json").read_text(encoding="utf-8"))
    assert doc["rule"] == ms.RULE
    assert set(doc) >= {"at", "swarms", "workers", "unmeasured", "box_tasks", "rule"}
    swarm = doc["swarms"]["exploit"]
    assert swarm["pass"] == 1 and swarm["pass_budget_s"] == 500.0
    assert [e["engine"] for e in swarm["engines"]] == list(EXPLOIT)
    assert set(swarm["yields"]) == set(EXPLOIT)
    assert all({"engine", "budget_s", "seconds", "rc", "status"} <= set(e) for e in
               swarm["engines"])
    assert swarm["allocation_rule"] and "floor_cost_s" in swarm
    assert doc["swarms_idle"] == ["explore", "resurrect"]
    names = [t["name"] for t in doc["box_tasks"]]
    assert names == ["MT5-Moat-Exploit", "MT5-Moat-Explore", "MT5-Moat-Resurrect"]
    assert all(t["runs"] == "desks/mt5/research/moat_swarms.py" for t in doc["box_tasks"])
    assert all("keep-alive" in t["trigger"] for t in doc["box_tasks"])
    assert [t["arguments"] for t in doc["box_tasks"]] == ["--swarm exploit", "--swarm explore",
                                                          "--swarm resurrect"]


def test_a_second_pass_merges_and_does_not_evict_a_sibling(desk):
    """Three residents share one file; each owns its key and none erases another's."""
    _plant(desk["tmp"] / "desk", _scripts_of("exploit") + _scripts_of("explore"))
    assert ms.main(["--swarm", "exploit", "--once", "--budget-s", "300"]) == 0
    assert ms.main(["--swarm", "explore", "--once", "--budget-s", "300"]) == 0
    doc = json.loads((desk["tmp"] / "MOAT_SWARMS.json").read_text(encoding="utf-8"))
    assert set(doc["swarms"]) == {"exploit", "explore"}
    assert doc["swarms_idle"] == ["resurrect"]


# --------------------------------------------------------------------------- the rails
def test_singleton_lock_is_exclusive_per_swarm(desk):
    """A keep-alive trigger that restarts a live swarm must be a no-op, and only for that swarm."""
    a = ms.claim_singleton("exploit")
    assert a is not None
    assert ms.claim_singleton("exploit") is None
    other = ms.claim_singleton("explore")
    assert other is not None                       # a sibling swarm is free: they run CONCURRENTLY
    other.close()
    assert ms.main(["--swarm", "exploit", "--once"]) == 0
    assert desk["calls"] == []                     # the held slot started no child at all
    a.close()
    b = ms.claim_singleton("exploit")
    assert b is not None                           # released when the holder closes
    b.close()


def test_dry_run_starts_nothing_writes_nothing_and_charges_nothing(desk):
    """The plan only: every engine PLANNED, no child, no report, no compute charged."""
    _plant(desk["tmp"] / "desk", _scripts_of("exploit"))
    assert ms.main(["--swarm", "exploit", "--dry-run", "--budget-s", "800"]) == 0
    assert desk["calls"] == []
    assert not (desk["tmp"] / "MOAT_SWARMS.json").exists()
    assert not (desk["tmp"] / "compute_ledger.jsonl").exists()
    assert not (desk["tmp"] / "locks").exists()
    assert reg.generator_yields() == []
    doc = ms.run_pass("exploit", 1, budget_s=800.0, dry_run=True)
    assert {e["status"] for e in doc["engines"]} == {"PLANNED"}
    assert sum(e["budget_s"] for e in doc["engines"]) == pytest.approx(800.0, abs=4.0)
