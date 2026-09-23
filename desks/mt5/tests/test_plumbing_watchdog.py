"""THE PLUMBING MAY NOT STOP SILENTLY, AND THE FIXES MAY NOT BE QUIETLY UNDONE.

Two jobs in one file, because they are one law with two halves.

FIRST HALF -- the watchdog does what it says. Each check is exercised against an injected,
measured state, never against the live box: a task the scheduler does not return, one with no
next run time, a mutex that cannot be taken, orphaned workers holding commit, a producer and a
consumer disagreeing about a path. If any of these stops being a defect, a test here fails.

SECOND HALF -- THE REGRESSION GUARDS. Five fixes were made after five outages, and every one of
them is a line somewhere that a later session could delete without noticing:

    the tree-killing runner is used by the launchers        (147 GB of orphaned commit)
    the reaper is first in the reconciler's apply pass      (every other repair fails behind it)
    the adoption task is daily-repeating-hourly, as SYSTEM  (a -Once trigger folded to nine days)
    the git-writer lock helper is used by all four writers  (four days of unadopted code)
    the live sleeve policy still bans FX and M15            (the forex sleeves came back twice)

These are pinned by reading the SOURCE, not by running the box, so they mean the same thing in
CI, in a fresh clone and on the trading box. A comment saying "do not remove this" is not a
guard; this file is.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from desks.mt5.research import plumbing_watchdog as pw  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------ the scheduler observations
def test_an_absent_task_is_a_critical_defect_naming_its_installer() -> None:
    rows, _f = pw.check_task("MT5-AdoptRelease", max_next_run_s=3600, check="adoption_task",
                             now=NOW, facts={"measured": True, "present": False})
    assert len(rows) == 1
    assert rows[0]["severity"] == "CRITICAL"
    assert "ABSENT" in rows[0]["evidence"]
    assert rows[0]["repair"], "a defect row without a repair is a complaint"


def test_a_task_with_no_next_run_time_is_the_four_day_outage_and_is_caught() -> None:
    """The measured shape: a -Once trigger whose repetition the scheduler folded to nine days,
    leaving `Next Run Time: N/A` while the task itself looked perfectly Ready."""
    rows, _f = pw.check_task("MT5-AdoptRelease", max_next_run_s=3600, check="adoption_task",
                             now=NOW, facts={"measured": True, "present": True, "state": "Ready",
                                             "next": "NONE", "result": "0"})
    assert [r["check"] for r in rows] == ["adoption_task"]
    assert "NO next run time" in rows[0]["evidence"]
    assert rows[0]["severity"] == "CRITICAL"


def test_a_next_run_a_day_away_is_a_stopped_clock_not_a_slow_one() -> None:
    far = (NOW + timedelta(hours=30)).isoformat()
    rows, _f = pw.check_task("MT5-AdoptRelease", max_next_run_s=3600, check="adoption_task",
                             now=NOW, facts={"measured": True, "present": True, "state": "Ready",
                                             "next": far, "result": "0"})
    assert any("outside its" in r["evidence"] for r in rows)


def test_a_ready_task_inside_its_window_with_a_clean_result_is_no_defect() -> None:
    soon = (NOW + timedelta(minutes=20)).isoformat()
    rows, _f = pw.check_task("MT5-AdoptRelease", max_next_run_s=3600, check="adoption_task",
                             now=NOW, facts={"measured": True, "present": True, "state": "Ready",
                                             "next": soon, "result": "0"})
    assert rows == []


def test_unmeasured_is_a_defect_and_never_a_pass() -> None:
    """L1.28a. A scheduler that cannot be queried has not reported a healthy scheduler."""
    rows, _f = pw.check_task("MT5-AdoptRelease", max_next_run_s=3600, check="adoption_task",
                             now=NOW, facts={"measured": False, "why": "no powershell"})
    assert len(rows) == 1 and "UNMEASURED" in rows[0]["repair"]


def test_every_clock_disabled_collapses_to_one_loud_row_not_forty() -> None:
    want = [f"MT5-Task{i}" for i in range(10)]
    have = dict.fromkeys(want, "Disabled")
    rows, facts = pw.check_declared_tasks(present=have, declared=want)
    assert len(rows) == 1, "forty rows is how a watchdog gets muted"
    assert rows[0]["key"] == "scheduled_task:box_administratively_stopped"
    assert rows[0]["severity"] == "CRITICAL"
    assert facts["disabled"] == want


def test_one_disabled_clock_among_many_is_reported_individually() -> None:
    want = [f"MT5-Task{i}" for i in range(10)]
    have = dict.fromkeys(want, "Ready")
    have["MT5-Task3"] = "Disabled"
    rows, _f = pw.check_declared_tasks(present=have, declared=want)
    assert [r["organ"] for r in rows] == ["MT5-Task3"]


# -------------------------------------------------------------------------- the adoption lag
def test_head_behind_the_branch_tip_is_a_critical_defect_with_the_count() -> None:
    def runner(argv: list[str]) -> tuple[int, str]:
        if argv[:2] == ["git", "rev-parse"]:
            return 0, "abc123def456\n"
        if argv[:3] == ["git", "rev-list", "--count"]:
            return 0, "232\n"
        return 1, ""
    rows, facts = pw.check_adoption_lag(ROOT, runner=runner)
    assert facts["commits_behind"] == 232
    assert facts["head_descends_from_tip"] is False
    assert any(r["severity"] == "CRITICAL" and "232" in r["evidence"] for r in rows)


def test_head_at_the_tip_is_no_defect() -> None:
    def runner(argv: list[str]) -> tuple[int, str]:
        if argv[:3] == ["git", "rev-list", "--count"]:
            return 0, "0\n"
        return 0, "abc123def456\n"
    rows, facts = pw.check_adoption_lag(ROOT, runner=runner)
    assert rows == [] and facts["head_descends_from_tip"] is True


# ------------------------------------------------------------------------- the git-writer lock
def test_a_lock_that_cannot_be_taken_is_the_four_day_outage() -> None:
    rows, facts = pw.check_git_writer_lock(
        ROOT, prober=lambda _n: {"measured": True, "taken": False,
                                 "why": "Access to the path 'Local\\MT5-GitWriter' is denied"})
    assert len(rows) == 1 and rows[0]["severity"] == "CRITICAL"
    assert "denied" in rows[0]["evidence"]
    assert facts["taken"] is False


def test_a_lock_that_can_be_taken_right_now_is_no_defect() -> None:
    rows, _f = pw.check_git_writer_lock(
        ROOT, prober=lambda _n: {"measured": True, "taken": True, "name": "Global\\X"})
    assert rows == []


def test_the_mutex_names_are_read_from_the_helper_not_retyped() -> None:
    names = pw._mutex_names(ROOT)
    assert any("MT5-GitWriter-v2" in n for n in names), names


# ------------------------------------------------------- orphaned workers and commit headroom
def test_orphaned_workers_holding_commit_are_a_critical_defect() -> None:
    rows, _f = pw.check_processes(
        reaper=lambda: {"measured": True, "orphans": 72, "orphan_commit_mb": 147_000,
                        "workers_total": 72, "killed": 0, "applied": False})
    assert any(r["check"] == "orphan_workers" and r["severity"] == "CRITICAL" for r in rows)
    assert any("147000" in r["evidence"] for r in rows)


def test_the_commit_floor_is_derived_from_the_measured_limit_never_a_machine_size() -> None:
    """CLAUDE.md's cautionary case: a floor sized for a 96 GB box, applied to the 8 GB box that
    actually trades, stood the gauntlet down twice."""
    assert pw.commit_floor_mb(8_186) == 2_048          # the floor holds on a small host
    assert pw.commit_floor_mb(251_000) == 20_080       # and scales with a large one
    assert pw.commit_floor_mb(100) == 2_048


# ----------------------------------------------------------------- producer/consumer agreement
def test_a_required_edge_whose_artifact_does_not_exist_is_a_defect(tmp_path: Path) -> None:
    rows, facts = pw.check_edge_paths(tmp_path)
    assert facts["edges_checked"] > 0
    assert rows and all(r["check"] == "path_pair" for r in rows)
    assert all(r["key"].endswith(":absent") for r in rows)


def test_the_leg_to_script_map_is_derived_from_the_cycle_itself() -> None:
    legs = pw.leg_scripts(ROOT)
    assert legs.get("control_plane") == "research/control_plane.py"
    assert legs.get("plumbing_watchdog") == "research/plumbing_watchdog.py"


def test_a_path_read_by_two_modules_and_written_by_none_is_the_research_bandit_shape(
        tmp_path: Path) -> None:
    d = tmp_path / "desks" / "mt5" / "research"
    d.mkdir(parents=True)
    (d / "reader_a.py").write_text('P = "reports/NOBODY_WRITES.json"\nopen(P).read()\n', "utf-8")
    (d / "reader_b.py").write_text('q = "reports/NOBODY_WRITES.json"\n', "utf-8")
    (d / "producer.py").write_text('W = "reports/WRITTEN.json"\nW.write_text("{}")\n'
                                   'x = "reports/WRITTEN.json"\n', "utf-8")
    (d / "other.py").write_text('y = "reports/WRITTEN.json"\n', "utf-8")
    rows, facts = pw.check_orphan_artifact_paths(tmp_path)
    assert [r["organ"] for r in rows] == ["reports/NOBODY_WRITES.json"]
    assert "reports/WRITTEN.json" not in facts["orphan_paths"], \
        "a constant written far from its literal is still written"


# ------------------------------------------------------------------- escalation and the ledger
def test_a_defect_seen_twice_escalates_and_keeps_its_first_sighting() -> None:
    row = pw.defect("adoption_task", "MT5-AdoptRelease", "gone", "reinstall")
    first = NOW - timedelta(hours=5)
    prior = {row["key"]: {"first_seen": first.isoformat(), "passes": 1}}
    aged, ledger = pw.age_defects([row], prior, NOW)
    assert aged[0]["passes"] == 2
    assert aged[0]["escalated"] is True
    assert aged[0]["age_s"] == 5 * 3600
    assert aged[0]["past_escalation_window"] is True      # adoption_task's window is 3h
    assert ledger[row["key"]]["first_seen"] == first.isoformat(timespec="seconds")


def test_a_defect_on_its_first_pass_is_published_but_not_yet_escalated() -> None:
    row = pw.defect("path_pair", "a -> b", "e", "r")
    aged, _ledger = pw.age_defects([row], {}, NOW)
    assert aged[0]["passes"] == 1
    assert aged[0]["escalated"] is False
    assert aged[0]["past_escalation_window"] is False


def test_a_healed_defect_leaves_the_ledger_so_a_recurrence_ages_honestly() -> None:
    row = pw.defect("orphan_workers", "pool workers", "e", "r")
    prior = {"orphan_workers:pool workers": {"first_seen": (NOW - timedelta(days=3)).isoformat(),
                                             "passes": 99},
             "adoption_task:gone": {"first_seen": NOW.isoformat(), "passes": 4}}
    _aged, ledger = pw.age_defects([row], prior, NOW)
    assert set(ledger) == {"orphan_workers:pool workers"}


def test_every_defect_row_carries_an_escalation_window_from_its_check() -> None:
    for check, window in pw.ESCALATION_S.items():
        assert pw.defect(check, "x", "e", "r")["escalate_after_s"] == window


def test_the_alerts_page_names_every_escalated_defect_with_its_repair(tmp_path: Path) -> None:
    doc = {"at": NOW.isoformat(),
           "defects": [{"organ": "MT5-AdoptRelease", "check": "adoption_task", "age_s": 345_600,
                        "passes": 96, "escalated": True, "evidence": "four days behind",
                        "repair": "Adopt-And-Seal.ps1"},
                       {"organ": "quiet", "check": "path_pair", "escalated": False,
                        "age_s": 0, "passes": 1, "evidence": "e", "repair": "r"}]}
    text = pw.render_alerts(doc, tmp_path / "PLUMBING_ALERTS.md")
    assert "MT5-AdoptRelease" in text and "Adopt-And-Seal.ps1" in text
    assert "quiet" not in text
    assert (tmp_path / "PLUMBING_ALERTS.md").exists()


def test_the_report_carries_the_bit_the_dashboard_and_the_fence_both_read(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(pw, "check_task", lambda *a, **k: ([], {"measured": True}))
    monkeypatch.setattr(pw, "check_adoption_lag", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_git_writer_lock", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_processes", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_declared_tasks", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_edge_paths", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_orphan_artifact_paths", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_fences_ran", lambda *a, **k: ([], {}))
    doc = pw.run(budget_s=5.0, now=NOW, write=False, state_path=tmp_path / "s.json")
    assert doc["PLUMBING_MOVING"] is True
    assert doc["n_defects"] == 0 and doc["n_past_escalation_window"] == 0
    assert set(doc["checks_run"]) and not doc["checks_skipped_for_budget"]


def test_a_check_that_raises_becomes_a_defect_rather_than_killing_the_watchdog(
        tmp_path: Path, monkeypatch: Any) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("the box hung up")
    monkeypatch.setattr(pw, "check_task", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_adoption_lag", boom)
    monkeypatch.setattr(pw, "check_git_writer_lock", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_processes", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_declared_tasks", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_edge_paths", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_orphan_artifact_paths", lambda *a, **k: ([], {}))
    monkeypatch.setattr(pw, "check_fences_ran", lambda *a, **k: ([], {}))
    doc = pw.run(budget_s=5.0, now=NOW, write=False, state_path=tmp_path / "s.json")
    assert doc["n_defects"] == 1
    assert "the box hung up" in doc["defects"][0]["evidence"]


# ==============================================================================================
#                          THE REGRESSION GUARDS -- fixes may not be reverted
# ==============================================================================================
def test_the_launchers_spawn_through_the_tree_killing_runner() -> None:
    """MEASURED 2026-09-22: `subprocess.run(..., timeout=)` kills the child it started and
    nothing else, so a timed-out gauntlet leaves its worker pool behind -- 72 of them held
    147 GB of a 251 GB commit limit and every later leg died of STATUS_COMMITMENT_LIMIT."""
    for rel in ("desks/mt5/research/hourly_cycle.py",
                "desks/mt5/research/department_resident.py"):
        src = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        assert "proctree" in src, f"{rel} no longer reaches libs/ops/proctree.py"
        assert "proctree.run" in src, f"{rel} imports proctree but does not use its runner"


def test_the_reaper_runs_first_in_the_reconcilers_apply_pass() -> None:
    """Freeing the commit limit is the precondition of every repair, not one of them. A pass that
    reaped last would spend its budget watching every actuator fail for a reason none can name."""
    src = (ROOT / "libs/ops/control_plane/reconciler.py").read_text(encoding="utf-8")
    assert "reap_orphans" in src, "the reconciler no longer reaps at all"
    i_reap = src.index("reap_orphans")
    i_plan = src.index("work = plan(obs, reg)")
    i_apply = src.index("repairs = apply_plan(")
    assert i_reap < i_plan < i_apply, "the reaper must precede planning and every other repair"


def test_the_adoption_task_is_daily_repeating_hourly_under_system() -> None:
    """A -Once trigger with a long RepetitionDuration is what the scheduler folded to nine days,
    leaving `Next Run Time: N/A` and four days of shipped code that never reached the box."""
    src = (ROOT / "desks/mt5/scripts/install_adopt_release_task.ps1").read_text(encoding="utf-8")
    assert "New-ScheduledTaskTrigger -Daily" in src
    assert "RepetitionInterval (New-TimeSpan -Hours 1)" in src
    assert "RepetitionDuration (New-TimeSpan -Days 1)" in src
    assert '-UserId "SYSTEM" -LogonType ServiceAccount' in src


def test_the_watchdogs_own_task_is_registered_the_same_way() -> None:
    """The organ that watches for an expired trigger may not be registered in that shape."""
    src = (ROOT / "desks/mt5/scripts/install_plumbing_watchdog_task.ps1").read_text("utf-8")
    assert "New-ScheduledTaskTrigger -Daily" in src
    assert "RepetitionInterval (New-TimeSpan -Minutes 15)" in src
    assert "RepetitionDuration (New-TimeSpan -Days 1)" in src
    assert '-UserId "SYSTEM" -LogonType ServiceAccount' in src


def test_all_four_git_writers_use_the_lock_helper() -> None:
    """The lock moved to MT5-GitWriter-v2 because the legacy name could not be OPENED under
    another principal's descriptor. A writer that reverts to its own mutex re-opens the outage."""
    writers = ("Adopt-And-Seal.ps1", "intel_ship_adopt.ps1", "Seal-IfClean.ps1",
               "sync_shadow_to_git.ps1")
    for name in writers:
        src = (ROOT / "desks/mt5/scripts" / name).read_text(encoding="utf-8", errors="replace")
        assert "GitWriterMutex.ps1" in src, f"{name} no longer dot-sources the lock helper"
        assert "Open-GitWriterMutex" in src, f"{name} does not take the shared lock"
    helper = (ROOT / "desks/mt5/scripts/GitWriterMutex.ps1").read_text(encoding="utf-8")
    assert "MT5-GitWriter-v2" in helper


def test_the_live_sleeve_policy_still_bans_fx_and_m15_at_both_doors() -> None:
    """The forex sleeves came back twice after retirement. Both doors, every time."""
    from mt5desk import live_policy as lp
    pol = lp.policy()
    fx = {"name": "chfnok_carry_asia", "symbol": "CHFNOK", "status": "LIVE"}
    m15 = {"name": "xau_m15", "symbol": "XAUUSD", "timeframe": "M15", "status": "LIVE"}
    gold = {"name": "gold_asia", "symbol": "XAUUSD", "timeframe": "H1", "status": "LIVE"}
    assert lp.refuse(fx, pol), "an FX sleeve is refused"
    assert lp.refuse(m15, pol), "an M15 sleeve is refused"
    assert not lp.refuse(gold, pol), "the gold book still passes"
    promoter = (ROOT / "desks/mt5/research/promoter.py").read_text(encoding="utf-8")
    assert "live_policy" in promoter, "the WRITE door no longer applies the policy"
    core = (ROOT / "desks/mt5/mt5desk/decision_core.py").read_text(encoding="utf-8")
    assert "live_policy" in core, "the READ door no longer applies the policy"


def test_the_watchdog_is_wired_to_a_clock_a_layer_and_a_fence() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS 7). An organ with no clock is not built, it is written."""
    cycle = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("plumbing_watchdog"' in cycle
    assert '_costed("bottleneck_attack"' in cycle
    manifest = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    assert 'name="MT5-PlumbingWatchdog"' in manifest and "every 15 minutes" in manifest
    gate = (ROOT / "scripts/run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_plumbing_watchdog.py", ())' in gate
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["plumbing_watchdog"] == "meta"
    assert LEG_LAYER["bottleneck_attack"] == "meta"


def test_the_dashboard_renders_the_watchdogs_report() -> None:
    """The third of three surfaces a human meets without asking. Events and the alerts page are
    the other two; a defect that reaches none of them is a defect that is being logged at."""
    src = (ROOT / "scripts/build_zentech_state.py").read_text(encoding="utf-8")
    assert '"plumbing": _read(DESK / "reports" / "PLUMBING_WATCHDOG.json")' in src


def test_the_watchdog_loads_repo_scripts_by_path_not_by_package() -> None:
    """`tests/scripts/__init__.py` makes a REGULAR package called `scripts`, which beats the repo
    root's namespace package wherever it sits on sys.path. The watchdog's task check silently
    took its ImportError branch under pytest and reported "not importable" instead of the box's
    27 disabled clocks -- a watchdog defeated by an import rule is the silent stop it exists to
    end. Both call sites load by file path now, and this pins that."""
    src = (ROOT / "desks/mt5/research/plumbing_watchdog.py").read_text(encoding="utf-8")
    code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if "from scripts" in ln or "import scripts" in ln], \
        "the watchdog must load repo scripts by file path, never as the `scripts` package"
    assert '_load_by_path("check_scheduled_tasks"' in src
    assert '_load_by_path("run_law_gate"' in src


def test_every_fence_the_law_gate_registers_is_checked_for_having_run() -> None:
    rows, facts = pw.check_fences_ran(ROOT, NOW)
    assert facts.get("measured") is not False
    assert facts["declared_fences"] > 20, "the gate's fence list is not being read"
    assert all(r["check"] == "fence_ran" for r in rows)


def test_the_defect_state_ledger_round_trips(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    rows = [pw.defect("adoption_task", "MT5-AdoptRelease", "e", "r")]
    _aged, ledger = pw.age_defects(rows, {}, NOW)
    pw._write_json(p, {"at": NOW.isoformat(), "defects": ledger})
    assert pw._load_first_seen(p) == {k: dict(v) for k, v in ledger.items()}
    assert json.loads(p.read_text(encoding="utf-8"))["defects"]
