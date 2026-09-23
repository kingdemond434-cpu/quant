"""THE SANDBOX FEDERATION: rotation, supply line, liveness fence and roster.

What these tests hold, in the order the machine uses them:

  ROTATION   every runnable system reaches an hour inside the rotation window, and the scout lane
             is ordered by AGE with no ROI or breadth test in it. The ratchet this breaks is the
             one measured on 2026-09-23: 7 systems ran of 63 planned, the same 7 every hour.
  BREADTH    marginal independent breadth is the DROP in the federation's effective rank when a
             system's donated cells are removed -- a system that only re-donates a crowded corner
             reads ~0, the sole holder of a direction reads a whole one.
  SUPPLY     pip's own words classify a failure as final or retryable, a settled row is never
             retried, and a retryable one comes back on a doubling backoff.
  FENCE      a runnable system past its window FAILS; an UNMEASURED reason unchanged for a week
             with a stalled install task FAILS; the same reason with a settled
             PERMANENTLY_UNAVAILABLE row that names its error and its cover PASSES.
  ROSTER     the table is GENERATED and total: every roster seed, every adapter and every cell
             has exactly one row, and the columns come from the artifacts that own them.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import adapters as A  # noqa: E402
from libs.research import external_federation as fed  # noqa: E402
from libs.research import sandbox_rotation as ROT  # noqa: E402
from research import sandbox_provision as PROV  # noqa: E402
from research import sandbox_roster as ROSTER  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_sandbox_liveness as FENCE  # noqa: E402


def _stamp(hours_ago: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------- rotation

def test_scout_lane_is_ordered_by_age_alone_and_ignores_roi() -> None:
    """The overdue system goes first even though it has never produced and the rival has."""
    rows = {
        "rich": {"last_at": _stamp(1), "information_gain": 500.0, "compute_spent": 1.0,
                 "candidates": 400},
        "starved": {"last_at": _stamp(72), "information_gain": 0.0, "compute_spent": 0.0},
    }
    plan = ROT.plan(["rich", "starved"], rows, budget_s=600.0, floor_s=30)
    assert plan["order"][0] == "starved", plan["order"]
    assert "starved" in plan["scouts"]
    assert plan["shares"]["starved"] >= 30


def test_a_system_that_never_ran_is_always_a_scout() -> None:
    plan = ROT.plan(["never", "recent"], {"recent": {"last_at": _stamp(0.5)}},
                    budget_s=600.0, floor_s=30)
    assert plan["order"][0] == "never"
    assert ROT.age_s(None) == float("inf")


def test_every_runnable_system_runs_inside_the_window() -> None:
    """Drive a simulated day of hourly passes: nothing may end it past the window."""
    systems = [f"sys{i:02d}" for i in range(40)]
    rows: dict[str, dict[str, Any]] = {}
    start = datetime.now(tz=UTC).timestamp()
    for hour in range(24):
        at = start + hour * 3600.0
        plan = ROT.plan(systems, rows, budget_s=900.0, floor_s=30, at=at)
        ran = plan["order"][:12]                      # what a 900s pass reaches at 30-75s each
        for sid in ran:
            rows.setdefault(sid, {})["last_at"] = datetime.fromtimestamp(at, tz=UTC).isoformat()
    end = start + 24 * 3600.0
    late = ROT.due_violations(systems, rows, at=end, grace=1.0)
    assert late == [], [r["system_id"] for r in late]


def test_scout_slots_never_take_more_than_half_the_pass() -> None:
    n = ROT.scout_slots(600.0, floor_s=30, n_runnable=100)
    assert 1 <= n <= int(600 * ROT.MAX_SCOUT_SHARE // 30)


# --------------------------------------------------------------------------------- breadth

def test_marginal_breadth_is_zero_for_a_duplicate_and_positive_for_a_sole_holder() -> None:
    cells = {
        "a": ["trend|EURUSD|H1", "trend|USDJPY|H1"],
        "duplicate": ["trend|EURUSD|H1", "trend|USDJPY|H1"],
        "orthogonal": ["vol_transition|XAUUSD|H4"],
    }
    b = ROT.breadth(cells)
    assert b["columns"] == 3
    assert b["marginal"]["duplicate"] == pytest.approx(0.0, abs=1e-6)
    # a and duplicate span ONE direction between them; dropping the orthogonal row takes the
    # federation from ~1.47 independent directions to exactly 1.0, so its marginal is that gap
    assert b["marginal"]["orthogonal"] > 0.4
    assert b["marginal"]["orthogonal"] > b["marginal"]["duplicate"] + 0.3
    assert b["total"] > b["marginal"]["orthogonal"]


def test_breadth_with_no_recorded_cells_is_unmeasured_not_a_penalty() -> None:
    b = ROT.breadth({"a": [], "b": []})
    assert b["total"] == 0.0
    assert set(b["marginal"]) == {"a", "b"}
    assert "UNMEASURED" in b["basis"]


def test_breadth_reweighting_gives_the_orthogonal_system_more_of_the_hour() -> None:
    rows = {
        "crowded": {"last_at": _stamp(1), "information_gain": 10.0, "compute_spent": 10.0,
                    "cells": ["trend|EURUSD|H1"]},
        "twin": {"last_at": _stamp(1), "information_gain": 10.0, "compute_spent": 10.0,
                 "cells": ["trend|EURUSD|H1"]},
        "orthogonal": {"last_at": _stamp(1), "information_gain": 10.0, "compute_spent": 10.0,
                       "cells": ["vol_transition|XAUUSD|H4", "range_reversion|US500|H1"]},
    }
    plan = ROT.plan(list(rows), rows, budget_s=3000.0, floor_s=30)
    assert plan["shares"]["orthogonal"] > plan["shares"]["crowded"]


# --------------------------------------------------------------------------------- supply line

@pytest.mark.parametrize(("text", "status"), [
    ("ERROR: No matching distribution found for pysr==2.5.0", PROV.PERMANENT),
    ("ERROR: Could not find a version that satisfies the requirement kats==0.2.0", PROV.PERMANENT),
    ("ERROR: Package 'x' requires a different Python: 3.14.7 not in '<3.13'", PROV.PERMANENT),
    ("error: Microsoft Visual C++ 14.0 or greater is required", PROV.PERMANENT),
    ("ERROR: ResolutionImpossible: conflict is caused by numpy", PROV.PERMANENT),
    ("WARNING: Retrying ... Read timed out.", PROV.RETRYABLE),
    ("something nobody has classified", PROV.RETRYABLE),
])
def test_pip_failures_are_classified_final_or_retryable(text: str, status: str) -> None:
    got, reason = PROV.classify(text)
    assert got == status
    assert reason


def test_a_settled_row_is_never_retried_and_a_retryable_one_backs_off() -> None:
    sid = next(iter(A.SPECS))
    ledger = {sid: {"status": PROV.PERMANENT, "attempts": 1, "last_attempt_at": _stamp(500)}}
    assert sid not in PROV.candidates_for(ledger, only=None, force=False)
    assert sid in PROV.candidates_for(ledger, only=None, force=True)
    assert PROV.retry_due({"attempts": 1, "last_attempt_at": _stamp(0.1)}) is False
    assert PROV.retry_due({"attempts": 1, "last_attempt_at": _stamp(2)}) is True
    assert PROV.retry_due({"attempts": 12, "last_attempt_at": _stamp(48)}) is False


def test_provision_pass_dry_run_writes_nothing_and_plans_in_roi_order(tmp_path: Path) -> None:
    doc = PROV.provision_pass(budget_s=30, dry_run=True, root=tmp_path,
                              ledger_path=tmp_path / "ledger.json",
                              report_path=tmp_path / "report.json",
                              fed_state_path=tmp_path / "fed.json",
                              runner_state_path=tmp_path / "state.json")
    assert not (tmp_path / "ledger.json").exists()
    assert doc["counts"]["specs"] == len(A.SPECS)
    scores = [r["rank_score"] for r in doc["attempted"]]
    assert scores == sorted(scores, reverse=True)


def test_every_unpinned_system_names_what_covers_its_capability(tmp_path: Path) -> None:
    doc = PROV.provision_pass(budget_s=20, root=tmp_path, max_installs=0,
                              ledger_path=tmp_path / "ledger.json",
                              report_path=tmp_path / "report.json",
                              fed_state_path=tmp_path / "fed.json",
                              runner_state_path=tmp_path / "state.json")
    ledger = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    unpinned = [r for r in ledger["systems"].values() if r["status"] == PROV.NO_PIN]
    assert unpinned, "some SPECS rows carry no pinned wheel; they must still be named"
    assert all(r.get("cover") for r in unpinned)
    assert doc["counts"]["no_distribution_pinned"] == len(unpinned)


# --------------------------------------------------------------------------------- fence

def _fence_tree(tmp_path: Path, *, runner: dict[str, Any], state: dict[str, Any],
                ledger: dict[str, Any], prior: dict[str, Any] | None = None) -> None:
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "SANDBOX_RUNNER.json").write_text(json.dumps(runner), "utf-8")
    (tmp_path / "data" / "sandbox_runner_state.json").write_text(json.dumps(state), "utf-8")
    (tmp_path / "data" / "sandbox_install_ledger.json").write_text(json.dumps(ledger), "utf-8")
    (tmp_path / "data" / "sandbox_liveness_state.json").write_text(
        json.dumps(prior or {"reasons": {}}), "utf-8")


@pytest.fixture
def fenced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(FENCE, "RUNNER_REPORT", tmp_path / "reports" / "SANDBOX_RUNNER.json")
    monkeypatch.setattr(FENCE, "RUNNER_STATE", tmp_path / "data" / "sandbox_runner_state.json")
    monkeypatch.setattr(FENCE, "INSTALL_LEDGER",
                        tmp_path / "data" / "sandbox_install_ledger.json")
    monkeypatch.setattr(FENCE, "STATE", tmp_path / "data" / "sandbox_liveness_state.json")
    monkeypatch.setattr(FENCE, "OUT", tmp_path / "reports" / "SANDBOX_LIVENESS.json")
    return tmp_path


def test_fence_fails_on_a_runnable_system_the_rotation_never_reached(fenced: Path) -> None:
    _fence_tree(fenced,
                runner={"systems_tried": [{"system_id": "dark", "status": "RUNNABLE"},
                                          {"system_id": "fine", "status": "RUNNABLE"}],
                        "unmeasured": []},
                state={"systems": {"fine": {"last_at": _stamp(2)},
                                   "dark": {"last_at": _stamp(24 * 5)}}},
                ledger={"systems": {}})
    rep = FENCE.build_report()
    assert rep["status"] == "DARK"
    assert [d["system_id"] for d in rep["dark"]] == ["dark"]


def test_fence_fails_on_an_unmeasured_reason_that_has_not_moved_in_a_week(
        fenced: Path) -> None:
    why = "aeon is not importable here and no sandbox venv exists"
    _fence_tree(fenced,
                runner={"systems_tried": [], "unmeasured": [{"system_id": "aeon", "why": why}]},
                state={"systems": {}},
                ledger={"systems": {"aeon": {"status": "RETRYABLE", "attempts": 3,
                                             "last_attempt_at": _stamp(24 * 30)}}},
                prior={"reasons": {"aeon": {"why": why, "since": _stamp(24 * 9)}}})
    rep = FENCE.build_report()
    assert rep["status"] == "STALLED"
    assert rep["stalled"][0]["system_id"] == "aeon"
    assert rep["stalled"][0]["held_days"] >= 7


def test_a_settled_permanently_unavailable_row_with_its_cover_passes(fenced: Path) -> None:
    why = "pysr is not importable here and no sandbox venv exists"
    _fence_tree(fenced,
                runner={"systems_tried": [], "unmeasured": [{"system_id": "pysr", "why": why}]},
                state={"systems": {}},
                ledger={"systems": {"pysr": {
                    "status": "PERMANENTLY_UNAVAILABLE", "attempts": 1,
                    "last_attempt_at": _stamp(24 * 40),
                    "error": "ERROR: No matching distribution found for pysr==2.5.0",
                    "why": "no distribution for this interpreter/platform",
                    "cover": "REBUILT cell(s): cell:symbolic_regression"}}},
                prior={"reasons": {"pysr": {"why": why, "since": _stamp(24 * 30)}}})
    rep = FENCE.build_report()
    assert rep["status"] == "OK", rep["stalled"]
    assert "pysr" in rep["settled"]


def test_a_terminal_row_without_an_error_and_a_cover_is_still_a_stall(fenced: Path) -> None:
    why = "x is not importable"
    _fence_tree(fenced,
                runner={"systems_tried": [], "unmeasured": [{"system_id": "x", "why": why}]},
                state={"systems": {}},
                ledger={"systems": {"x": {"status": "PERMANENTLY_UNAVAILABLE",
                                          "last_attempt_at": _stamp(24 * 40)}}},
                prior={"reasons": {"x": {"why": why, "since": _stamp(24 * 30)}}})
    assert FENCE.build_report()["status"] == "STALLED"


def test_a_missing_runner_report_is_unmeasured_and_never_a_pass(fenced: Path) -> None:
    rep = FENCE.build_report()
    assert rep["status"] == "UNMEASURED"
    assert rep["status"] not in FENCE._PASSING


def test_a_reason_that_changed_resets_its_clock(fenced: Path) -> None:
    prior = {"aeon": {"why": "old reason", "since": _stamp(24 * 30)}}
    new = FENCE.reason_ages([{"system_id": "aeon", "why": "a different reason"}], prior)
    assert ROT.age_s(new["aeon"]["since"]) < 60
    same = FENCE.reason_ages([{"system_id": "aeon", "why": "old reason"}], prior)
    assert same["aeon"]["since"] == prior["aeon"]["since"]


# --------------------------------------------------------------------------------- roster

def test_the_roster_names_every_seed_every_adapter_and_every_cell(tmp_path: Path) -> None:
    doc = ROSTER.build(state_path=tmp_path / "s.json", report_path=tmp_path / "r.json",
                       ledger_path=tmp_path / "l.json", fed_state_path=tmp_path / "f.json")
    ids = {r["system_id"] for r in doc["systems"]}
    assert set(fed.SEED_BY_ID) <= ids
    assert set(A.SPECS) <= ids
    from research import sandboxes as CELLS
    assert {CELLS.system_id(c) for c in CELLS.CELLS} <= ids
    assert len(ids) == len(doc["systems"]), "one row per system, never a duplicate"
    assert doc["counts"]["seeds"] == 123


def test_every_roster_row_carries_the_columns_the_question_asked_for(tmp_path: Path) -> None:
    doc = ROSTER.build(state_path=tmp_path / "s.json", report_path=tmp_path / "r.json",
                       ledger_path=tmp_path / "l.json", fed_state_path=tmp_path / "f.json")
    needed = {"system_id", "disposition", "licence", "capability_family", "runs_here",
              "last_run_at", "runs", "candidates", "breadth_marginal", "install_status"}
    for row in doc["systems"]:
        assert needed <= set(row), sorted(needed - set(row))


def test_the_roster_reads_the_install_ledger_and_the_runner_state(tmp_path: Path) -> None:
    sid = "ruptures"
    (tmp_path / "l.json").write_text(json.dumps({"systems": {sid: {
        "status": "INSTALLED", "version": "1.0.6"}}}), "utf-8")
    (tmp_path / "s.json").write_text(json.dumps({"systems": {sid: {
        "runs": 4, "candidates": 11, "last_at": _stamp(3), "last_status": "PRODUCED",
        "cells": ["vol_transition|XAUUSD|H1"]}}}), "utf-8")
    doc = ROSTER.build(state_path=tmp_path / "s.json", report_path=tmp_path / "r.json",
                       ledger_path=tmp_path / "l.json", fed_state_path=tmp_path / "f.json")
    row = next(r for r in doc["systems"] if r["system_id"] == sid)
    assert row["install_status"] == "INSTALLED"
    assert row["install_version"] == "1.0.6"
    assert row["runs_here"] is True and row["produced"] is True
    assert row["candidates"] == 11 and row["last_run_age_h"] == pytest.approx(3.0, abs=0.1)


def test_the_markdown_is_rendered_from_the_json_and_names_every_row(tmp_path: Path) -> None:
    doc = ROSTER.build(state_path=tmp_path / "s.json", report_path=tmp_path / "r.json",
                       ledger_path=tmp_path / "l.json", fed_state_path=tmp_path / "f.json")
    text = ROSTER.render(doc)
    assert "DERIVED ARTIFACT" in text
    for row in doc["systems"]:
        assert f"`{row['system_id']}`" in text
