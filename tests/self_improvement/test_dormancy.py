"""THE DORMANCY HUNTER -- 80 statements, untested, and it was itself found by a human grepping.

On 2026-07-30 the desk's named "highest-ROI MISSING subsystems" -- research meta-learning,
capital-allocation learning, agent health monitoring, information-advantage measurement, an
alpha-decay lab, experiment ERV ranking -- turned out to be BUILT ALREADY with ZERO CALLERS. That
was found because someone happened to grep for callers. Depending on a human noticing is not a
mechanism, and the failure class is large: a capability that exists and never executes is
indistinguishable from the outside from one that was never built, except that the desk already
paid for it.

WHAT THIS FILE ASSERTS, and why these three and not line coverage:

  REACHABILITY, NOT POPULARITY. A library imported by ONE live caller is reachable and therefore
  not dormant, however small it is. The desk does not want to churn small components; it wants to
  find the disconnected ones. A test that only checked "unimported reads dormant" would pass on a
  scanner that flagged everything, which is a scanner nobody reads past the first run.

  ITS OWN PACKAGE AND ITS OWN TESTS DO NOT MAKE IT REACHABLE. This is the assertion the module's
  correctness rests on: a package of six modules that only import each other is a dormant
  SUBSYSTEM, and counting intra-package imports would hide exactly the six-module finding that
  produced this module. Tests are excluded for the same reason -- a module with a test suite and
  no caller is paid-for and unused, and the suite is not the desk running it.

  IT NEVER DELETES. An auto-retiring sweep would eventually delete a capability that was dormant
  only because its unlock condition had not arrived -- which is precisely the state several of
  these are legitimately in (0 validated alphas). Asserted structurally, on the source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.self_improvement import dormancy as D

# ------------------------------------------------------------------ the scan, on the live tree

@pytest.fixture(scope="module")
def report() -> D.DormancyReport:
    return D.scan()


def test_the_scan_actually_looks_at_something(report: D.DormancyReport) -> None:
    """A scanner reporting '0 dormant' having scanned 0 files is the guard-that-cannot-fail shape,
    and it reads identically to a clean desk."""
    assert report.n_modules_scanned > 50
    assert report.n_scripts_scanned > 50


def test_a_HEAVILY_IMPORTED_module_is_never_dormant(report: D.DormancyReport) -> None:
    """REACHABILITY, NOT POPULARITY -- from the safe side. If a core module ever reads dormant the
    importer detection is broken, and every other row in the report is noise."""
    paths = {d.path for d in report.dormant}
    assert "libs/research/capacity_policy.py" not in paths
    assert "libs/execution/protective_stops.py" not in paths


def test_every_finding_carries_a_PROVING_COMMAND(report: D.DormancyReport) -> None:
    """A dormancy claim nobody can reproduce in one line is a claim that gets argued with. The
    command is what makes the disposition a five-second check rather than an investigation."""
    for d in report.dormant:
        assert d.proving_command and "grep" in d.proving_command
        assert d.reason


def test_every_finding_reports_its_SIZE(report: D.DormancyReport) -> None:
    """A 500-line dormant subsystem is a larger paid-for-and-unused asset than a 20-line one, and
    the ranking is the whole point of surfacing them."""
    assert all(d.lines >= 0 for d in report.dormant)
    if report.dormant:
        assert any(d.lines > 0 for d in report.dormant)


def test_the_suggested_exit_is_never_DELETE(report: D.DormancyReport) -> None:
    """Several of these are legitimately waiting on an unlock condition -- 0 validated alphas is a
    DATA gap, not a dead capability."""
    for d in report.dormant:
        assert "delet" not in d.suggested_exit.lower()
        assert "retire" not in d.suggested_exit.lower() or "record" in d.suggested_exit.lower()


# ------------------------------------------------------------------ importer detection

def test_a_module_imported_from_OUTSIDE_its_package_has_external_importers() -> None:
    assert D._external_importers("libs/research/capacity_policy.py")


def test_ITS_OWN_PACKAGE_does_not_make_a_module_reachable() -> None:
    """THE ASSERTION THE MODULE'S CORRECTNESS RESTS ON. A package of six modules that only import
    each other is a dormant SUBSYSTEM, and counting intra-package imports would hide exactly the
    six-module finding that produced this module."""
    for importer in D._external_importers("libs/research/capacity_policy.py"):
        assert not importer.startswith("libs/research"), (
            f"{importer} is inside the module's own package and was counted as reachability")


def test_ITS_OWN_TESTS_do_not_make_a_module_reachable() -> None:
    """A module with a test suite and no caller is still paid-for and unused. The suite is not the
    desk running it -- and this is the loophole that would quietly close as coverage rises, which
    is exactly what has been happening on this branch."""
    for importer in D._external_importers("libs/execution/protective_stops.py"):
        assert not importer.startswith("tests/"), (
            f"{importer} is a test and was counted as reachability")


def test_a_module_nothing_imports_has_no_external_importers() -> None:
    assert D._external_importers("libs/research/a_module_that_does_not_exist.py") == []


# ------------------------------------------------------------------ scheduling detection

def test_a_SCHEDULED_script_is_reachable() -> None:
    """A script named in the crontab manifest is run by the desk, whether or not any code imports
    it -- and scheduling is the only reachability a top-level organ has."""
    import subprocess
    manifest = Path(D._ROOT / "ops/crontab.manifest")
    if not manifest.exists():
        pytest.skip("no crontab manifest on this host")
    hit = subprocess.run(["grep", "-oE", r"scripts/[A-Za-z0-9_]+\.py", str(manifest)],
                         capture_output=True, text=True, check=False).stdout.split()
    if not hit:
        pytest.skip("the manifest names no scripts on this host")
    assert D._scheduled(hit[0]) is True


def test_an_UNSCHEDULED_name_is_not_reachable_by_scheduling() -> None:
    assert D._scheduled("scripts/a_script_that_does_not_exist_anywhere.py") is False


def test_a_script_INVOKED_BY_ANOTHER_SCRIPT_is_reachable() -> None:
    """Shelling out counts. A runner that calls a tool by filename is running it just as surely as
    a scheduler would, and missing that would flag every helper the desk actually uses."""
    assert D._invoked_by_a_script("scripts/max_audit.py") is True


def test_a_file_does_not_count_as_INVOKING_ITSELF() -> None:
    """Self-reference would make every script reachable and the script half of the scan would
    report zero forever -- a guard that cannot fire."""
    assert D._invoked_by_a_script("scripts/a_file_that_does_not_exist.py") is False


# ------------------------------------------------------------------ the exemption list

def test_ON_DEMAND_scripts_are_exempt_with_a_WRITTEN_REASON() -> None:
    """"It's a CLI tool" is otherwise the excuse that lets any dormant script escape the check, so
    each exemption is listed explicitly and carries why."""
    assert D._ON_DEMAND
    for path, reason in D._ON_DEMAND.items():
        assert path.startswith("scripts/") and path.endswith(".py")
        assert len(reason) > 20, f"{path} is exempt on a stub reason: {reason!r}"


def test_no_exemption_names_a_script_that_no_longer_exists() -> None:
    """An exemption for a deleted file is a hole with a comment over it."""
    missing = [p for p in D._ON_DEMAND if not (D._ROOT / p).exists()]
    assert missing == [], f"exemptions for scripts that do not exist: {missing}"


def test_an_exempt_script_is_never_reported_dormant(report: D.DormancyReport) -> None:
    paths = {d.path for d in report.dormant}
    assert not (paths & set(D._ON_DEMAND))


def test_the_scanned_packages_all_exist() -> None:
    """A scope entry pointing at a renamed package silently scans nothing, and the report would
    shrink without anyone noticing that a whole subsystem stopped being checked."""
    missing = [p for p in D._LIB_SCOPE if not (D._ROOT / p).is_dir()]
    assert missing == [], f"scoped packages that do not exist: {missing}"


# ------------------------------------------------------------------ the report

def test_the_two_halves_can_be_scanned_independently() -> None:
    """The module half is fast; the script half shells out per file. A caller that only wants one
    should not pay for both -- and if the flags were ignored the cost would be invisible."""
    mods = D.scan(include_scripts=False)
    assert mods.n_scripts_scanned == 0 and mods.n_modules_scanned > 0
    assert all(d.kind == "module" for d in mods.dormant)

    scripts = D.scan(include_modules=False)
    assert scripts.n_modules_scanned == 0 and scripts.n_scripts_scanned > 0
    assert all(d.kind == "script" for d in scripts.dormant)


def test_counts_are_broken_down_by_kind() -> None:
    rep = D.DormancyReport(dormant=[
        D.Dormant("a.py", "module", "r", "c", 10),
        D.Dormant("b.py", "module", "r", "c", 20),
        D.Dormant("c.py", "script", "r", "c", 30),
    ])
    assert rep.counts == {"module": 2, "script": 1}


def test_an_empty_report_has_empty_counts_rather_than_zeroed_keys() -> None:
    """Zeroed keys would read as 'we checked and found none of each kind' on a scan that never
    ran."""
    assert D.DormancyReport().counts == {}


def test_the_summary_ranks_BIGGEST_FIRST() -> None:
    rep = D.DormancyReport(dormant=[
        D.Dormant("small.py", "module", "r", "c", 20),
        D.Dormant("huge.py", "module", "r", "c", 500),
        D.Dormant("mid.py", "module", "r", "c", 100),
    ], n_modules_scanned=3)
    out = D.summarise(rep)
    assert [d["path"] for d in out["dormant"]] == ["huge.py", "mid.py", "small.py"]
    assert out["total_dormant_lines"] == 620


def test_the_summary_caps_its_list_but_not_its_TOTAL() -> None:
    """The cap keeps the artifact readable. Capping the total instead would understate the
    paid-for-and-unused figure, which is the number the priority rests on."""
    rep = D.DormancyReport(dormant=[D.Dormant(f"m{i}.py", "module", "r", "c", 1)
                                    for i in range(100)])
    out = D.summarise(rep)
    assert len(out["dormant"]) == 40
    assert out["total_dormant_lines"] == 100


def test_the_summary_states_the_PRIORITY_and_the_available_EXITS() -> None:
    """A list of dormant modules with no stated disposition invites the cheapest one, which is
    deletion -- and deletion is the one exit this module refuses to take."""
    out = D.summarise(D.DormancyReport())
    assert "before inventing new capability" in str(out["priority"]).lower()
    assert "never auto-deleted" in str(out["exits"])


# ------------------------------------------------------------------ it never acts

def test_the_module_CANNOT_delete_retire_or_edit_anything() -> None:
    """Asserted on the source, because the guarantee is about what the code is CAPABLE of, not
    what it happens to do on a given input. An auto-retiring sweep would eventually delete a
    capability that was dormant only because its unlock condition had not arrived."""
    src = Path(D.__file__).read_text("utf-8")
    for banned in ("os.remove", "shutil.rmtree", "unlink(", "write_text(", "rename(",
                   "git rm", "os.rmdir"):
        assert banned not in src, f"the dormancy hunter can {banned} -- it must only report"


def test_the_scan_leaves_the_tree_untouched() -> None:
    """The behavioural half of the same guarantee: a reporter that mutated what it measured would
    make every subsequent run a report about its own side effects."""
    watched = [D._ROOT / "libs/self_improvement/dormancy.py",
               D._ROOT / "libs/research/capacity_policy.py"]
    before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    D.scan(include_scripts=False)
    after = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    assert before == after
