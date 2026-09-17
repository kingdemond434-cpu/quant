"""THE DAILY CONTROLLER -- what it decides is the product, so these pin the decisions.

    python -m pytest desks/mt5/tests/test_daily_research_os.py -q -p no:cacheprovider

What is fenced here, and why each one is worth a test:

  * OBSERVE NAMES WHAT IS ABSENT. Four of the twelve artifacts this controller reads do not exist
    on the box today. A controller that reads a missing file as a clean zero diagnoses a desk that
    does not exist, and every rule below it inherits the lie (L1.28a);
  * DIAGNOSE PICKS THE PLANTED BOTTLENECK. The rule set must DISCRIMINATE: the same code, given
    two different desks, must name two different bottlenecks. A ranking that always returns the
    same row is a constant wearing a measurement;
  * AN UNMEASURED RULE STAYS IN THE RANKING. The cheapest bottleneck to miss is the one nobody
    could see, so an unmeasured rule ranks below the measured ones and above nothing at all;
  * THE NORTH STAR IS A DAY-OVER-DAY DIFFERENCE, and a term with no yesterday is UNMEASURED BY
    NAME rather than counted as zero -- a zero says the desk measured no movement;
  * THE ALLOCATION NEVER DISABLES A DEPARTMENT. Every department keeps a floor share and
    `enabled` is True for all of them, because the principal's standing order is that the desk
    never reduces its aggressiveness by fiat;
  * THE RELEASE TRAIN ROW IS APPENDED WITH ITS REASON, and `day_counted_successful` is True only
    when a NAMED check measured an improvement -- never because the pass completed;
  * LEARN REMEMBERS, so tomorrow can ask whether today's bottleneck moved;
  * `--dry-run` RUNS NOTHING AND WRITES NOTHING. The subprocess runner is stubbed throughout:
    a test that shells out measures the box instead of the controller.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import daily_research_os as D  # noqa: E402

TODAY = datetime.now(tz=UTC).date().isoformat()
YESTERDAY = (datetime.now(tz=UTC) - timedelta(days=1)).date().isoformat()
NOW = datetime.now(tz=UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------- the fixtures
def _departments(runs: dict[str, int]) -> dict[str, Any]:
    return {"at": NOW, "departments": {d: {"compute": {"runs": n, "hours": n * 0.5},
                                           "yield": {"born": n, "certified": 0}}
                                       for d, n in runs.items()}}


def _gap_map(valid: int = 1000, ready: int = 100, populated: int = 40) -> dict[str, Any]:
    return {"at": NOW, "n_valid_cells": valid, "n_populated": populated,
            "populated_share": populated / valid,
            "by_state": {"UNSEEN": valid - ready - populated - 10, "DATA_MISSING": 10,
                         "READY": ready, "TESTING": populated, "FAILED": 0, "SURVIVED": 0,
                         "FORWARD": 0, "LIVE": 0},
            "top_holes": [{"cell": "bonds|carry_rollover|negative_carry_holder|carry|d1|all|"
                                   "multi_day|unconditional", "state": "READY", "value": 0.4}],
            "coverage_by_axis": {"asset_class": {"forex": 30, "bonds": 10},
                                 "mechanism": {"carry_rollover": 40}},
            "research_debt_cells": 25}


def _scorecard(silent: float) -> dict[str, Any]:
    return {"generated_utc": NOW, "rows": [
        {"dimension": "effective_breadth_n_eff", "current": 2.1},
        {"dimension": "silent_scheduled_failures", "current": silent}]}


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A desk in a tmp tree, a tmp registry, and a stubbed subprocess runner that records what
    the controller ASKED to run without running anything."""
    reports, data = tmp_path / "reports", tmp_path / "data"
    reports.mkdir(parents=True)
    (data / "hypotheses").mkdir(parents=True)
    (tmp_path / "research").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "ops").mkdir(parents=True)

    arts = {name: (reports if str(path).replace("\\", "/").find("/reports/") >= 0 else data)
            / Path(path).name for name, path in D.ARTIFACTS.items()}
    monkeypatch.setattr(D, "ARTIFACTS", arts)
    monkeypatch.setattr(D, "DESK", tmp_path)
    monkeypatch.setattr(D, "ROOT", tmp_path)
    monkeypatch.setattr(D, "REPORTS", reports)
    monkeypatch.setattr(D, "DATA", data)
    monkeypatch.setattr(D, "OUT", reports / "DAILY_RESEARCH_OS.json")
    monkeypatch.setattr(D, "TRAIN", data / "research_release_train.jsonl")
    monkeypatch.setattr(D, "ALLOCATION", data / "daily_allocation.json")
    monkeypatch.setattr(D, "BREADTH_HIST", data / "effective_breadth.jsonl")
    monkeypatch.setattr(D, "GATE_LEDGER", data / "hypotheses" / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(D, "LOCKS", data / "locks")
    monkeypatch.setattr(D, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(D, "BOX_TASKS", tmp_path / "ops" / "box_tasks.manifest")
    # Deterministic complexity: `git log` on the real repo is neither reproducible nor this
    # organ's subject.
    monkeypatch.setattr(D, "_complexity",
                        lambda since_h=24.0: {"new_modules": 2, "tasks_declared": 30,
                                              "status": "MEASURED"})
    calls: list[list[str]] = []

    def _runner(cmd: list[str], timeout_s: float = 0.0) -> dict[str, Any]:
        calls.append(list(cmd))
        return {"cmd": cmd, "rc": 0, "seconds": 0.0, "tail": ["stubbed"]}

    monkeypatch.setattr(D, "run_command", _runner)
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_such_backup")
    R.set_path(tmp_path / "registry.sqlite")
    yield {"root": tmp_path, "reports": reports, "data": data, "calls": calls, "arts": arts}
    R.set_path(None)


def _populate_registry() -> None:
    """A registry with a research chain in it, so `registry_chain_empty` is not the answer to
    every question this suite asks."""
    R.enqueue_candidate(family="carry", symbol="BUND", params={"rr": 2}, origin="DESK",
                        mechanism="carry_rollover", asset_class="bonds", chart="D1")
    R.enqueue_candidate(family="trend_ma_cross", symbol="EURUSD", params={}, origin="MOAT",
                        mechanism="trend_persistence", asset_class="forex", chart="H1")
    R.record_trial("cell-1", family="carry", method="gauntlet", params=None, passed=False)
    R.record_run("run-1", name="gauntlet", status="ok", organ="gauntlet")
    R.remember("lesson", "a carry cell died at cost", kind="lesson", memory_key="lesson:1")
    R.generator_yield_update("deep_forest", generated=10, independent_survivors=2)


def _full_desk(desk: dict[str, Any], *, silent: float = 0.0, unwired: int = 2,
               dept_runs: dict[str, int] | None = None, ready: int = 100) -> None:
    arts = desk["arts"]
    _write(arts["tier1_scorecard"], _scorecard(silent))
    _write(arts["research_departments"],
           _departments(dept_runs or dict.fromkeys(D.DEPARTMENTS_FALLBACK, 5)))
    _write(arts["wiring_ceo"], {"at": NOW, "n_unwired": unwired, "n_probation": 3,
                                "floor": {"status": "HELD", "previous": unwired}})
    _write(arts["residual_queue"], {"at": NOW, "n_open": 4, "n_candidates": 2})
    _write(arts["unseen_frontier"], {"at": NOW, "grounds": {"a": {"n": 3}, "b": {"n": 0}},
                                     "unmeasured": {"grounds_unmeasured": ["b"]}})
    _write(arts["effective_breadth"], {"generated_utc": NOW, "effective":
                                       {"effective_breadth": 2.4}})
    _write(arts["research_registry"], {"at": NOW})
    _write(arts["gap_map"], _gap_map(ready=ready))
    _write(arts["ceo_docket"], {"at": NOW, "n_proposals": 6})
    _write(arts["probation"], {"at": NOW, "promotable": []})
    _write(arts["auto_legs"], {"at": NOW, "legs": [{"organ": "x", "plan": "core"}]})
    (desk["root"] / "ops" / "box_tasks.manifest").write_text(
        "# a comment\nMT5-Hourly\nMT5-Daily\n", encoding="utf-8")
    hist = desk["data"] / "effective_breadth.jsonl"
    rows = []
    for i in range(8):
        at = (datetime.now(tz=UTC) - timedelta(days=7 - i)).isoformat()
        rows.append({"at": at, "effective_breadth": 2.4 + 0.3 * i})
    hist.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (desk["data"] / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        "\n".join(json.dumps({"at": f"{TODAY}T0{i}:00:00+00:00", "cell": f"c{i}",
                              "passed": i == 0}) for i in range(4)), encoding="utf-8")
    _populate_registry()


# --------------------------------------------------------------------------------- OBSERVE
def test_observe_reads_what_exists_and_names_what_is_absent(desk: dict[str, Any]) -> None:
    _write(desk["arts"]["tier1_scorecard"], _scorecard(0.0))
    _write(desk["arts"]["gap_map"], _gap_map())
    obs = D.observe()

    assert obs["artifacts"]["tier1_scorecard"]["present"] is True
    assert obs["artifacts"]["tier1_scorecard"]["at"] == NOW
    assert obs["artifacts"]["gap_map"]["age_h"] is not None
    for name in ("wiring_ceo", "residual_queue", "unseen_frontier", "mining_objective"):
        assert name in obs["absent"], f"{name} is absent and must be NAMED"
        assert obs["artifacts"][name]["present"] is False
        assert obs["artifacts"][name]["status"] == "ABSENT"
        assert obs["artifacts"][name]["path"], "an absence names the path it looked for"
    assert obs["registry"]["status"] == "MEASURED"
    assert obs["day"] == TODAY


def test_mining_objective_is_tolerated_when_absent_and_read_when_present(
        desk: dict[str, Any]) -> None:
    """Another builder is writing MINING_OBJECTIVE.json. Its absence is a named UNMEASURED, and
    its arrival must need no edit here."""
    assert "mining_objective" in D.observe()["absent"]
    _write(desk["arts"]["mining_objective"], {"at": NOW, "objective": "independent survivors"})
    obs = D.observe()
    assert "mining_objective" not in obs["absent"]
    assert obs["docs"]["mining_objective"]["objective"] == "independent survivors"


# --------------------------------------------------------------------------------- DIAGNOSE
def test_diagnose_runs_every_declared_rule(desk: dict[str, Any]) -> None:
    _full_desk(desk)
    rows = D.diagnose(D.observe())
    assert [r["rule"] for r in rows] == list(D.RULES)
    for r in rows:
        assert r["why"], "a rule with no reason is an opinion"
        assert r["attack"], "a bottleneck nobody is assigned is a bottleneck nobody attacks"


def test_diagnose_picks_the_planted_bottleneck(desk: dict[str, Any]) -> None:
    """The same code on two different desks must name two different bottlenecks."""
    _full_desk(desk, silent=9.0, unwired=90)
    top = D.prioritize(D.diagnose(D.observe()), {})["top"]
    assert top["rule"] == "silent_scheduled_failure"
    assert top["severity"] == 1.0
    assert top["attack"] == "meta"
    assert top["evidence"]["n_unwired"] == 90

    # Now a desk whose organs are all wired and whose READY ground is the whole grid.
    _write(desk["arts"]["wiring_ceo"], {"at": NOW, "n_unwired": 0,
                                        "floor": {"status": "HELD"}})
    _write(desk["arts"]["tier1_scorecard"], _scorecard(0.0))
    _write(desk["arts"]["gap_map"], _gap_map(valid=1000, ready=980, populated=5))
    top = D.prioritize(D.diagnose(D.observe()), {})["top"]
    assert top["rule"] == "frontier_holes_ready_untouched"
    assert top["attack"] == "discovery"
    assert top["evidence"]["ready_cells"] == 980


def test_a_silent_department_is_named_and_attacked_by_name(desk: dict[str, Any]) -> None:
    runs = dict.fromkeys(D.DEPARTMENTS_FALLBACK, 5)
    runs["execution"] = 0
    _full_desk(desk, dept_runs=runs)
    row = next(r for r in D.diagnose(D.observe()) if r["rule"] == "department_silent_24h")
    assert row["evidence"]["silent"] == ["execution"]
    assert row["attack"] == "execution", "the department that stopped is the one that is attacked"


def test_an_unmeasured_rule_is_ranked_never_dropped(desk: dict[str, Any]) -> None:
    """Nothing is written at all: every rule whose input is absent must still appear."""
    rows = D.diagnose(D.observe())
    plan = D.prioritize(rows, {})
    assert len(plan["ranked"]) == len(D.RULES)
    unmeasured = [r for r in plan["ranked"] if r["status"] == "UNMEASURED"]
    assert {r["rule"] for r in unmeasured} >= {"department_silent_24h", "source_cold_3d",
                                               "residuals_unattacked",
                                               "frontier_holes_ready_untouched"}
    assert plan["n_unmeasured_rules"] == len(unmeasured)
    measured_ranks = [r["rank"] for r in plan["ranked"] if r["status"] == "MEASURED"]
    assert max(measured_ranks) < min(r["rank"] for r in unmeasured), (
        "measured rules rank above unmeasured ones, and unmeasured ones above nothing")


# --------------------------------------------------------------------------------- north star
def test_north_star_terms_are_day_over_day_and_name_what_is_absent(desk: dict[str, Any]) -> None:
    _full_desk(desk)
    for name, value in (("frontier_coverage", 0.02), ("orthogonal_candidates", 1.0),
                        ("independent_survivor_yield", 1.0)):
        R.kpi(YESTERDAY, name, value)
    obs = D.observe()
    star = D.north_star(obs)
    terms = {t["name"]: t for t in star["terms"]}

    assert terms["d_frontier_coverage"]["status"] == "MEASURED"
    assert terms["d_frontier_coverage"]["delta"] == pytest.approx(0.04 - 0.02)
    assert terms["d_frontier_coverage"]["weighted"] == pytest.approx(
        (0.04 - 0.02) * D.SCALES["d_frontier_coverage"])
    assert terms["d_independent_survivor_yield"]["delta"] == pytest.approx(1.0)
    assert terms["d_orthogonal_candidates"]["today"] == 2.0, "two distinct registry grid cells"

    # n_eff has no yesterday, so the term is UNMEASURED BY NAME and is excluded from the sum.
    assert terms["d_n_eff"]["status"].startswith("UNMEASURED")
    assert terms["d_n_eff"]["weighted"] is None
    assert "d_n_eff" in star["unmeasured_terms"]
    assert star["research_value"] == pytest.approx(
        sum(t["weighted"] for t in star["terms"] if t["weighted"] is not None))
    assert terms["complexity_cost"]["weighted"] < 0, "new machinery is a cost, never a credit"
    for t in star["terms"]:
        assert t["source"], "every term names the artifact it was read from"


def test_the_north_star_is_None_when_every_term_is_unmeasured(desk: dict[str, Any]) -> None:
    obs = D.observe()
    obs["complexity"] = {"status": "UNMEASURED"}
    star = D.north_star(obs, D.today_absolutes(obs))
    assert star["research_value"] is None
    assert len(star["unmeasured_terms"]) == len(star["terms"])


# --------------------------------------------------------------------------------- ALLOCATE
def test_allocation_never_disables_a_department(desk: dict[str, Any]) -> None:
    _full_desk(desk, silent=9.0, unwired=90)
    plan = D.prioritize(D.diagnose(D.observe()), {})
    alloc = D.allocate(plan["ranked"])
    shares = {d: v["share"] for d, v in alloc["departments"].items()}

    assert set(shares) == set(D.departments())
    assert all(s >= D.MIN_SHARE * 0.9 for s in shares.values()), shares
    assert all(v["enabled"] is True for v in alloc["departments"].values())
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-5)
    assert shares["meta"] == max(shares.values()), "the department attacking the top bottleneck"
    assert alloc["departments"]["meta"]["attack"] == "silent_scheduled_failure"
    assert "never disabled" in alloc["rule"] or "is ever disabled" in alloc["rule"]


# --------------------------------------------------------------------------------- RUN
def test_the_chain_calls_frontier_ceo_first_and_by_subprocess(desk: dict[str, Any]) -> None:
    """It SUPERSEDES the CEO docket by calling it. A controller that reimplemented the ranking
    would give the desk two rankings that disagree on alternate days."""
    steps = D.run_steps()
    names = [s["step"] for s in steps]
    assert names[0] == "frontier_ceo"
    assert names[1] == "research_gap_map"
    assert names[-1] == "mining_objective" and steps[-1]["outcome"] == "ABSENT"
    assert "registry_sync" in names
    cmds = desk["calls"]
    assert cmds[0][-1] == "--apply" and cmds[0][-2].endswith("frontier_ceo.py")
    assert cmds[1][-1].endswith("research_gap_map.py")

    (desk["root"] / "research" / "mining_objective.py").write_text("", encoding="utf-8")
    assert [s["step"] for s in D.run_steps()] == ["frontier_ceo", "research_gap_map",
                                                  "mining_objective", "registry_sync"]


# --------------------------------------------------------------------------------- the pass
def test_a_full_pass_writes_the_artifact_the_allocation_and_the_train_row(
        desk: dict[str, Any]) -> None:
    _full_desk(desk, silent=9.0, unwired=90)
    for name, value in (("frontier_coverage", 0.01), ("orthogonal_candidates", 0.0),
                        ("research_memory_rows", 0.0), ("conversion_debt_unexplained", 5.0),
                        ("auto_legs", 0.0), ("n_eff", 2.0), ("sources_rows", 0.0),
                        ("research_candidates_rows", 0.0), ("axis_values_covered", 0.0),
                        ("mechanisms_rows", 0.0), ("unwired_organs", 95.0),
                        ("silent_failures", 12.0), ("data_missing_cells", 20.0)):
        R.kpi(YESTERDAY, name, value)

    doc = D.run_once()
    assert doc["mode"] == "apply"
    assert Path(D.OUT).exists() and Path(D.ALLOCATION).exists()
    assert [s["outcome"] for s in doc["ran"]].count("ok") == 3
    assert doc["north_star_after"]["research_value"] is not None

    rows = [json.loads(ln) for ln in
            Path(D.TRAIN).read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 1
    row = rows[0]
    for field in ("sources_added", "axes_opened", "candidates_created",
                  "conversion_debt_reduced", "mechanisms_discovered", "gauntlet",
                  "failures_learned", "machinery_tested", "machinery_promoted",
                  "machinery_retired", "n_eff", "frontier_gaps", "next_bottleneck",
                  "day_counted_successful", "day_counted_reason"):
        assert field in row, field
    assert row["gauntlet"] == {"judged": 4, "passed": 1, "status": "MEASURED"}
    assert row["candidates_created"] == 2.0
    assert row["failures_learned"] == 1.0
    assert row["machinery_promoted"] == 1.0
    assert row["machinery_retired"] == 5.0, "unwired fell from 95 to 90"
    assert row["next_bottleneck"] == "silent_scheduled_failure"
    assert row["day_counted_successful"] is True
    assert "measured improvement in" in row["day_counted_reason"]
    assert "reliability_improved" in row["day_counted_reason"], "silent failures 12 -> 9"

    # A second pass appends rather than replaces: the train is a ledger.
    D.run_once()
    assert len(Path(D.TRAIN).read_text(encoding="utf-8").strip().splitlines()) == 2


def test_a_day_that_moved_nothing_says_so(desk: dict[str, Any]) -> None:
    """`day_counted_successful` is False when no named check measured an improvement -- never
    True because the pass completed."""
    _full_desk(desk)
    obs = D.observe()
    absolutes = D.today_absolutes(obs)
    obs["kpis_yesterday"] = dict(absolutes)                     # nothing moved at all
    row = D.release_train_row(obs, absolutes, {"research_value": 0.0}, None,
                              {"moved": None, "why": "no diagnosis stored"})
    assert row["day_counted_successful"] is False
    assert row["day_counted_reason"].startswith("NOTHING MEASURABLE MOVED")
    assert "UNMEASURED" in row["day_counted_reason"]


def test_learn_remembers_the_diagnosis_and_tomorrow_can_read_it(desk: dict[str, Any]) -> None:
    _full_desk(desk, silent=9.0, unwired=90)
    doc = D.run_once()
    assert doc["learned"], "LEARN wrote no memory row"
    mem = R.memories(category="research_os", kind="daily_diagnosis")
    assert len(mem) == 1
    payload = json.loads(mem[0]["payload_json"])
    assert payload["day"] == TODAY
    assert payload["bottleneck"] == "silent_scheduled_failure"
    assert payload["severity"] == 1.0
    assert mem[0]["memory_key"] == f"daily_diagnosis:{TODAY}"
    # The key makes the write an upsert: a re-run refreshes the day, never duplicates it.
    D.run_once()
    assert len(R.memories(category="research_os", kind="daily_diagnosis")) == 1


def test_yesterdays_bottleneck_moved_is_measured_on_the_same_rule(desk: dict[str, Any]) -> None:
    _full_desk(desk, silent=0.0, unwired=2)
    R.remember("research_os", "yesterday", kind="daily_diagnosis",
               memory_key=f"daily_diagnosis:{YESTERDAY}",
               payload={"day": YESTERDAY, "bottleneck": "silent_scheduled_failure",
                        "severity": 1.0})
    rows = D.diagnose(D.observe())
    moved = D.yesterdays_bottleneck(rows)
    assert moved["rule"] == "silent_scheduled_failure"
    assert moved["moved"] is True
    assert moved["severity_today"] < moved["severity_yesterday"]

    # With no stored diagnosis the answer is None and NAMED -- never a cheerful False.
    R.set_path(desk["root"] / "registry2.sqlite")
    assert D.yesterdays_bottleneck(rows)["moved"] is None
    assert YESTERDAY in D.yesterdays_bottleneck(rows)["why"]
    R.set_path(desk["root"] / "registry.sqlite")


# --------------------------------------------------------------------------------- the boundary
def test_dry_run_runs_nothing_and_writes_nothing(desk: dict[str, Any]) -> None:
    _full_desk(desk)
    assert D.main(["--dry-run"]) == 0
    assert desk["calls"] == [], "--dry-run may not start a single child process"
    assert not Path(D.OUT).exists()
    assert not Path(D.TRAIN).exists()
    assert not Path(D.ALLOCATION).exists()
    assert R.kpis(days=3) == [], "--dry-run may not write a KPI either"

    doc = D.run_once(dry_run=True)
    assert doc["ran"] == []
    assert doc["mode"] == "dry-run"
    assert doc["prioritize"]["top"] is not None, "it still diagnoses and ranks"


def test_the_day_stamp_stops_a_second_apply_pass_and_once_forces_it(
        desk: dict[str, Any]) -> None:
    _full_desk(desk)
    assert D.already_ran_today() is False
    D.run_once()
    assert D.already_ran_today() is True
    ran = len(desk["calls"])
    assert D.main([]) == 0
    assert len(desk["calls"]) == ran, "the stamped day runs nothing again"
    assert D.main(["--once"]) == 0
    assert len(desk["calls"]) > ran, "--once forces a pass whatever the stamp says"


def test_todays_absolutes_are_written_as_kpis_so_tomorrow_can_diff(
        desk: dict[str, Any]) -> None:
    """A controller that cannot diff itself is a dashboard."""
    _full_desk(desk)
    D.run_once()
    written = {r["name"] for r in R.kpis(days=2) if r["day"] == TODAY}
    assert {"frontier_coverage", "orthogonal_candidates", "n_eff", "complexity_cost",
            "conversion_debt_unexplained", "research_memory_rows"} <= written
