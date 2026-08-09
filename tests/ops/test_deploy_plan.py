"""RANK 7 inbound deploy: the properties that keep "merge is deploy" from shipping stale code.

Two matter more than the rest, and they point in OPPOSITE directions on purpose:
  * a change that reaches the executor MUST restart it (under-restarting reproduces the
    2026-07-26 incident -- new code on disk, pre-fix code owning the book);
  * a change that reaches the DEAD-MAN must NOT restart it (a restart is a window with no ruin
    rail, and no unattended script opens that window).
Anything that gets those two backwards is the failure this file exists to catch.
"""

from __future__ import annotations

from pathlib import Path

from libs.ops.deploy_plan import (
    TIER_RESTART,
    TIER_RUIN,
    import_closure,
    plan,
)

_EXECUTOR = "scripts/run_cashcarry_executor.py"
_DEADMAN = "scripts/run_deadman_switch.py"


class TestTheRuinRailIsNeverRestartedByAScript:
    def test_a_deadman_change_escalates_rather_than_restarts(self) -> None:
        p = plan([_DEADMAN])
        assert [a.unit for a in p.escalations] == ["quant-deadman.service"]
        assert p.restarts == [], "a script must never restart the ruin rail"

    def test_the_escalation_says_why_out_loud(self) -> None:
        # an operator reading this at 3am must not have to know the doctrine to act correctly
        why = plan([_DEADMAN]).escalations[0].why
        assert "RUIN RAIL" in why and "not restarted here" in why

    def test_the_directive_verb_is_escalate_so_the_shell_cannot_restart_it(self) -> None:
        # the shell dispatches on this verb; ESCALATE has no systemctl branch
        assert plan([_DEADMAN]).directives()[0].startswith("ESCALATE\t")

    def test_the_ruin_rail_is_tiered_above_ordinary_restarts(self) -> None:
        assert TIER_RUIN > TIER_RESTART


class TestAChangeThatReachesTheExecutorRestartsIt:
    def test_a_direct_edit_restarts_it(self) -> None:
        assert [a.unit for a in plan([_EXECUTOR]).restarts] == ["quant-cashcarry.service"]

    def test_a_transitive_libs_change_restarts_it_too(self) -> None:
        # THE case a hand-written path list gets wrong: nothing in scripts/ changed at all
        p = plan(["libs/execution/carry_accounting.py"])
        assert [a.unit for a in p.restarts] == ["quant-cashcarry.service"]

    def test_it_names_the_path_that_invalidated_it_not_just_the_unit(self) -> None:
        a = plan(["libs/execution/carry_accounting.py"]).restarts[0]
        assert a.trigger == "libs/execution/carry_accounting.py"
        assert "imports" in a.why

    def test_a_direct_edit_is_reported_in_preference_to_an_incidental_import(self) -> None:
        # both paths hit the executor; the operator should read the direct cause
        a = plan([_EXECUTOR, "libs/execution/carry_accounting.py"]).restarts[0]
        assert a.trigger == _EXECUTOR and "changed directly" in a.why


class TestTheBlastRadiusIsComputedNotWritten:
    """A hand-kept list rots the first time somebody adds an import -- silently."""

    def test_the_executor_closure_is_real_and_nonempty(self) -> None:
        c = import_closure(_EXECUTOR)
        assert len(c) > 20, "the executor genuinely reaches a large first-party surface"
        assert "libs/execution/carry_accounting.py" in c

    def test_the_ruin_rail_is_dependency_free_by_design(self) -> None:
        # this is WHY an ordinary libs/ commit cannot invalidate the deadman; if this ever
        # fails, the ruin rail grew a dependency and its isolation needs re-arguing
        assert import_closure(_DEADMAN) == set()

    def test_a_module_never_appears_in_its_own_closure(self) -> None:
        assert _EXECUTOR not in import_closure(_EXECUTOR)

    def test_an_import_cycle_terminates(self, tmp_path: Path) -> None:
        # a deploy that hangs on a cycle is a deploy that never happens
        (tmp_path / "libs").mkdir()
        (tmp_path / "libs" / "__init__.py").write_text("", "utf-8")
        (tmp_path / "libs" / "a.py").write_text("from libs.b import x\n", "utf-8")
        (tmp_path / "libs" / "b.py").write_text("from libs.a import y\n", "utf-8")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "e.py").write_text("from libs.a import z\n", "utf-8")
        assert import_closure("scripts/e.py", tmp_path) == {"libs/a.py", "libs/b.py"}

    def test_a_missing_entry_yields_an_empty_closure_rather_than_raising(self) -> None:
        assert import_closure("scripts/does_not_exist_at_all.py") == set()

    def test_third_party_imports_are_not_treated_as_repo_paths(self, tmp_path: Path) -> None:
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "e.py").write_text(
            "import pandas as pd\nimport numpy\nfrom websockets import connect\n", "utf-8")
        assert import_closure("scripts/e.py", tmp_path) == set()

    def test_a_syntactically_broken_module_does_not_abort_the_plan(self, tmp_path: Path) -> None:
        # refusing to deploy because an UNRELATED file cannot be parsed is a self-inflicted outage
        (tmp_path / "libs").mkdir()
        (tmp_path / "libs" / "__init__.py").write_text("", "utf-8")
        (tmp_path / "libs" / "broken.py").write_text("def (((\n", "utf-8")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "e.py").write_text("from libs.broken import x\n", "utf-8")
        assert import_closure("scripts/e.py", tmp_path) == {"libs/broken.py"}


class TestNothingChangedIsSilentlyDropped:
    def test_every_changed_path_lands_in_exactly_one_bucket(self) -> None:
        changed = [_EXECUTOR, _DEADMAN, "ops/crontab.manifest", "docs/GAP_REGISTER.md",
                   "libs/execution/carry_accounting.py"]
        p = plan(changed)
        assert set(p.changed) == set(changed)
        # accounted = anything that produced an action or a scheduler warning
        assert set(p.no_restart).isdisjoint(p.scheduler_stale)
        assert "docs/GAP_REGISTER.md" in p.no_restart

    def test_a_docs_only_commit_restarts_nothing(self) -> None:
        p = plan(["docs/graveyard.md", "docs/EXECUTION_QUEUE.md"])
        assert p.actions == [] and p.scheduler_stale == []
        assert len(p.no_restart) == 2, "cron re-execs each tick, so these are live already"

    def test_an_empty_commit_is_not_a_crash(self) -> None:
        p = plan([])
        assert p.changed == [] and p.actions == [] and p.directives() == []

    def test_blank_lines_from_git_diff_are_ignored(self) -> None:
        assert plan(["", "  ", "docs/x.md"]).changed == ["docs/x.md"]

    def test_windows_path_separators_normalise(self) -> None:
        # the desk was authored on Windows and still runs there; a backslash must not read as
        # an unrelated path and silently skip the restart
        assert plan(["libs\\execution\\carry_accounting.py"]).restarts != []


class TestSchedulerSourceChangesAreReportedNotApplied:
    def test_a_manifest_change_warns(self) -> None:
        assert plan(["ops/crontab.manifest"]).scheduler_stale == ["ops/crontab.manifest"]

    def test_it_never_becomes_a_restart_or_an_escalation(self) -> None:
        p = plan(["ops/crontab.manifest"])
        assert p.actions == [], "the installed crontab is stale -- no PROCESS is invalidated"

    def test_the_directive_demands_a_drift_review_before_the_installer(self) -> None:
        d = plan(["ops/crontab.manifest"]).directives()[0]
        assert d.startswith("SCHEDULER\t")
        # the manifest's own header forbids running the installer before reviewing live drift
        assert "check_scheduler_manifest.py" in d and "BEFORE" in d


class TestTheSupervisionMapCannotForkFromTheWatchdog:
    """Two copies of the same map is how §42's four capacity constants drifted apart."""

    def test_it_matches_watchdog_units_exactly(self) -> None:
        import ast

        from libs.ops.deploy_plan import _OWNED

        # parsed rather than imported: scripts/watchdog.py has import-time side effects and is
        # not an importable module, but its _UNITS literal is the thing that must agree
        src = Path("scripts/watchdog.py").read_text("utf-8")
        tree = ast.parse(src)
        units: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_UNITS" for t in node.targets
            ):
                units = ast.literal_eval(node.value)
                break
        assert units, "could not find _UNITS in scripts/watchdog.py"
        assert {k: v[0] for k, v in _OWNED.items()} == units, (
            "deploy_plan._OWNED and watchdog._UNITS disagree -- one of them will restart the "
            "wrong process, or miss one entirely")
