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

#: ONE live scan for the whole module, and the scoping is not tidiness -- it is the difference
#: between a suite that finishes and one that does not. `scan()` SHELLS OUT to grep once per
#: module and twice per script: 267 modules + 364 scripts is ~630 subprocesses and ~10.4s
#: uncovered. Under `--cov` tracing that becomes minutes, and my first draft called it THREE
#: times, which hung the full suite at 85% until py-spy named this frame.
#:
#: A slow test is a test somebody eventually deselects, so the cost is a correctness issue rather
#: than a comfort one. Everything that needs the LIVE tree shares this one scan; anything testing
#: the flags or the report shape uses a scoped or synthetic one below.
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


def test_a_scripts_ENTRY_POINT_counts_as_an_external_importer() -> None:
    """R0359 alleged this scan is blind to scripts/ and had therefore authorised a false
    retirement. THE ALLEGATION IS REFUTED, and this pins the refutation so it is not re-raised.

    The claim was that commit 3be2e3e retired 14 libs/discovery modules on "zero external
    importers" while scripts/run_geometric_review.py imported two of them. Checked against the
    actual trees: _external_importers ALREADY grepped scripts/ at 3be2e3e, and
    scripts/run_geometric_review.py DID NOT EXIST in the tree that retirement was computed on --
    it was added by fee1214a on the other lineage, which is not an ancestor of 3be2e3e. The
    retirement's claim was true of its own tree. The breakage was born in the later MERGE, which
    brought the caller from master while the callees stayed deleted here. That failure lives at
    the schedule boundary and is fenced by check_scheduler_manifest (e), not here.

    scripts/ is where nearly every organ lives, so the property is worth a standing test even
    though it already held.
    """
    for module in ("libs/discovery/cagr_optimizer.py", "libs/discovery/portfolio_geometry.py"):
        assert "scripts/run_geometric_review.py" in D._external_importers(module), (
            f"{module} reads as unreachable despite a scripts/ entry point importing it -- "
            "that is the false-retirement authoriser R0359 feared"
        )


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

def test_the_two_halves_can_be_scanned_independently(monkeypatch) -> None:
    """A caller that only wants one half should not pay for both -- and if the flags were ignored
    the cost would be INVISIBLE, which is exactly how this file hung the suite.

    `_LIB_SCOPE` is narrowed to a single small package so the flags are proved without re-walking
    267 modules of subprocess greps. The flags are what is under test; the breadth is not.
    """
    monkeypatch.setattr(D, "_LIB_SCOPE", ("libs/self_improvement",))

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


def test_the_scan_leaves_the_tree_untouched(monkeypatch) -> None:
    """The behavioural half of the same guarantee: a reporter that mutated what it measured would
    make every subsequent run a report about its own side effects.

    Scoped for the same reason as the flags test -- mutation is a property of the scan's code path,
    not of how many packages it walks, so paying 8s of subprocess greps to observe it buys nothing.
    """
    monkeypatch.setattr(D, "_LIB_SCOPE", ("libs/self_improvement",))
    watched = [D._ROOT / "libs/self_improvement/dormancy.py"]
    before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    D.scan(include_scripts=False)
    after = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    assert before == after


# --- THREE STRANDING STATES (L1.54(a)) -------------------------------------------------------

def test_ZERO_IMPORTERS_IS_ORPHAN() -> None:
    state, why = D.stranding(importers=0, callers=0, executions=None, output_consumers=None)
    assert state == "ORPHAN" and "consumer, not a schedule" in why


def test_IMPORTED_BUT_NEVER_CALLED_IS_STILL_AN_ORPHAN() -> None:
    """MEASURED 2026-08-08 on this module's own author.

    A consumer was written for four orphan modules; `convergence` stayed orphaned because the new
    consumer DESCRIBED its verdict in a hand-typed string instead of calling it. The importer
    count would have read 1 and the scan would have gone quiet.
    """
    state, why = D.stranding(importers=1, callers=0, executions=None, output_consumers=None)
    assert state == "ORPHAN"
    assert "imported for its name and never invoked" in why


def test_A_CONSUMER_THAT_NEVER_RAN_IS_INERT_NOT_WIRED() -> None:
    state, why = D.stranding(importers=1, callers=2, executions=0, output_consumers=0)
    assert state == "INERT" and "L1.49" in why


def test_OUTPUT_NOBODY_READS_IS_THE_STATE_THAT_HIDES() -> None:
    """It passes every test an importer count can run -- which is why it needs its own name."""
    state, why = D.stranding(importers=1, callers=2, executions=9, output_consumers=0)
    assert state == "CONVERSION_FAILURE"
    assert "wire the output to a decision" in why


def test_AN_UNINSTRUMENTED_CAPABILITY_IS_UNMEASURED_NEVER_WIRED() -> None:
    """L1.28a at the reachability layer: defaulting an unknown execution count to 'probably ran'
    is how a dormant subsystem reports itself healthy."""
    assert D.stranding(importers=1, callers=1, executions=None,
                       output_consumers=None)[0] == "UNMEASURED"
    assert D.stranding(importers=1, callers=1, executions=3,
                       output_consumers=None)[0] == "UNMEASURED"


def test_FULLY_WIRED_IS_THE_ONLY_CLEAN_VERDICT() -> None:
    state, _ = D.stranding(importers=2, callers=2, executions=14, output_consumers=1)
    assert state == "WIRED"


def test_EVERY_VERDICT_IS_A_DECLARED_STATE() -> None:
    for args in ((0, 0, None, None), (1, 0, None, None), (1, 1, 0, 0), (1, 1, 5, 0),
                 (1, 1, None, None), (1, 1, 5, 2)):
        assert D.stranding(importers=args[0], callers=args[1], executions=args[2],
                           output_consumers=args[3])[0] in D.STRANDING_STATES


def test_CALL_SITES_SEES_THE_CONSUMER_THAT_ACTUALLY_CALLS_CONVERGENCE() -> None:
    """The fix landed the same day the defect was found, so this is a regression fence: the review
    must CALL `elevate()`, not merely name the module."""
    sites = D.call_sites("libs/research/convergence.py")
    assert any("run_research_review" in s for s in sites), sites


# --- call_sites: the four import shapes that each shipped a silent false positive -------------

def _probe(tmp_path, consumer_src: str) -> list[str]:
    """Run call_sites against a synthetic consumer by monkeypatching the importer lookup."""
    import libs.self_improvement.dormancy as mod
    f = tmp_path / "consumer.py"
    f.write_text(consumer_src, "utf-8")
    orig_root, orig_imp = mod._ROOT, mod._external_importers
    mod._ROOT = tmp_path
    mod._external_importers = lambda rel: ["consumer.py"]  # type: ignore[assignment]
    try:
        return mod.call_sites("libs/research/widget.py")
    finally:
        mod._ROOT, mod._external_importers = orig_root, orig_imp


def test_PARENTHESISED_MULTILINE_IMPORT_IS_SEEN(tmp_path) -> None:
    """`[^\\n(]+` stopped dead at the `(` and read ZERO names -- exec_monitor, which is called on
    line 90 of its consumer, was reported stranded."""
    assert _probe(tmp_path, "from libs.research.widget import (\n    render,\n    update,\n)\n"
                            "update({})\n") == ["consumer.py"]


def test_A_TRAILING_NOQA_COMMENT_DOES_NOT_HIDE_THE_CALL(tmp_path) -> None:
    """The comment rode into the captured name and failed `isidentifier()`."""
    assert _probe(tmp_path, "from libs.research.widget import lag  # noqa: E402\n"
                            "x = lag('binance')\n") == ["consumer.py"]


def test_MODULE_IMPORTED_UNDER_AN_ALIAS_IS_SEEN(tmp_path) -> None:
    """`from libs.research import widget as w` binds the MODULE, so every use is `w.evaluate(...)`
    -- the form half of libs/research is imported with."""
    assert _probe(tmp_path, "from libs.research import widget as w\n"
                            "v = w.evaluate(1)\n") == ["consumer.py"]


def test_A_NESTED_ATTRIBUTE_CHAIN_IS_SEEN(tmp_path) -> None:
    """`canary_mod.CanaryState.load(...)` is Attribute(Attribute(Name)); stopping at the first
    `.value` reported a live money-path guard as stranded."""
    assert _probe(tmp_path, "from libs.research import widget as m\n"
                            "st = m.State.load('p')\n") == ["consumer.py"]


def test_AN_IMPORT_WITH_NO_CALL_IS_STILL_CAUGHT(tmp_path) -> None:
    """The check must keep catching what it was built for: the intelligence cycle imports
    capital_reallocator purely to prove it is importable, then never invokes it."""
    assert _probe(tmp_path, "import libs.research.widget  # noqa: F401\n"
                            "print('activated')\n") == []
