#!/usr/bin/env python3
"""L1.57 -- A VERDICT WITHOUT A DENOMINATOR IS AN OPINION.

Three halves, because removing any one of them re-opens the hole:

HALF ONE -- the primitive refuses. `fence_exit(status, passing, scanned=0)` must NOT return 0,
however passing the status is. And the refusal must be computed from the arguments in hand, not
from a successful registry import, or an unwritable `data/` silently restores the pass.

HALF TWO -- the wiring is live. Each fence wired this cycle must actually pass `scanned=` at its
exit site, and each must FAIL when its scope discovery returns nothing. These are behavioural
tests driving the real `main()` through a subprocess, because the defect being pinned is
specifically that the in-body status was fine while the exit code lied (the R0237 lesson).

HALF THREE -- the meta-fence cannot itself pass vacuously. `check_denominators` governs the
denominators of every other fence; a version of it that reported a clean board while discovering
zero fences would be the exact joke it exists to end.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.denominator import is_vacuous, summarise  # noqa: E402
from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402

# ---------------------------------------------------------------- half one: the primitive

def test_passing_status_over_zero_scan_is_refused() -> None:
    """The whole law in one assertion: OK over nothing examined is not a pass."""
    assert fence_exit("OK", {"OK"}) == 0                      # unchanged when undeclared
    assert fence_exit("OK", {"OK"}, scanned=1) == 0
    assert fence_exit("OK", {"OK"}, scanned=0) == FAIL


def test_non_integer_scan_counts_are_refused() -> None:
    """A failed scope discovery hands back a float/str/empty container -- not one is a count.

    `True` is in here deliberately: `bool` is an `int` subclass, so a stray truthiness flag
    passed as a count would otherwise sail through as "1 thing scanned". `scanned=None` is
    excluded because None means UNDECLARED, which is the coverage ratchet's business, not a
    refusal (see test_passing_status_over_zero_scan_is_refused).
    """
    for bad in (float("nan"), 0.0, 1.0, "3", [], {}, True):
        assert fence_exit("OK", {"OK"}, scanned=bad) == FAIL, bad


def test_failing_status_is_never_rescued_or_relabelled() -> None:
    """One-way valve: this may only turn passes into failures, never the reverse."""
    assert fence_exit("DARK", {"OK"}, scanned=0) == FAIL
    assert fence_exit("DARK", {"OK"}, scanned=99) == FAIL
    assert not is_vacuous(0, passed=False)      # a failing verdict is not "vacuous"


def test_refusal_does_not_depend_on_the_registry_being_writable(monkeypatch) -> None:
    """If telemetry breaks, the REFUSAL must survive it -- otherwise an unwritable data/
    silently restores every vacuous pass. This is the failure mode the first draft had."""
    import libs.ops.denominator as den

    def _boom(*a: object, **k: object) -> None:
        raise OSError("registry unwritable")

    monkeypatch.setattr(den, "record", _boom)
    assert fence_exit("OK", {"OK"}, scanned=0) == FAIL
    assert fence_exit("OK", {"OK"}, scanned=5) == 0


# ---------------------------------------------------------------- half two: the wiring is live

def _run(script: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    import os
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, str(_ROOT / "scripts" / script), *args],
                          capture_output=True, text=True, cwd=_ROOT, env=e, timeout=180)


def test_wired_fences_declare_a_denominator_at_their_exit_site() -> None:
    """Source-level: removing `scanned=` from any wired fence fails this test.

    A source scan rather than a per-fence behavioural test, for the reason recorded in
    test_fence_exit_map: behavioural tests only cover the fences someone remembered.
    """
    wired = ["check_exploration.py", "check_llm_routing.py", "check_calendar_gates.py",
             "check_denominators.py", "check_utilisation.py", "check_mypy_ratchet.py"]
    for name in wired:
        src = (_ROOT / "scripts" / name).read_text("utf-8")
        assert "scanned=" in src, f"{name} no longer declares a denominator (L1.57)"
        assert "fence_exit(" in src, f"{name} no longer routes its exit through fence_exit"


def test_exploration_fence_fails_when_its_family_is_empty(tmp_path) -> None:
    """THE PROVING INSTANCE. `_FAMILY` is mutated at import; empty it and the old code hit
    `len(fresh) < n / 2` == `0 < 0.0` == False and reported OK with n_organs 0."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_ce", str(_ROOT / "scripts" / "check_exploration.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod._FAMILY.clear()
    rep = mod.build_report()
    assert rep["n_organs"] == 0
    assert rep["status"] == "UNMEASURED", "an empty exploration family must never read OK"
    assert mod.fence_exit(rep["status"], mod._PASSING, scanned=rep["n_organs"],
                          of="t", fence="t") == FAIL


def test_timidity_fence_consults_the_surfaces_it_scanned() -> None:
    """`prompt_surfaces_scanned` was published and left out of the failure expression."""
    src = (_ROOT / "scripts" / "check_timidity_language.py").read_text("utf-8")
    tail = src.split("failed = (")[-1]
    assert "blind" in tail, "the zero-denominator guard is no longer in the failure expression"
    assert "prompt_surfaces_scanned" in src


def test_calendar_gate_scan_publishes_its_denominator() -> None:
    """A CLEAN verdict must state how many files earned it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_cg", str(_ROOT / "scripts" / "check_calendar_gates.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.scan()
    assert mod.N_SCANNED > 100, "the repo-wide *.py walk matched almost nothing -- scope is broken"


def test_a_permanently_failing_fence_still_declares_its_denominator() -> None:
    """Found while running this build: check_calendar_gates early-returns 1 on its violations
    path without touching fence_exit, so while its 69-item migration backlog stands it never
    reached its declaration site -- making a permanently-FAILING fence indistinguishable from an
    UNWIRED one in the coverage ratchet. Both paths must declare."""
    src = (_ROOT / "scripts" / "check_calendar_gates.py").read_text("utf-8")
    fail_path = src.split("MIGRATION CHECKLIST")[-1].split("return 1")[0]
    assert "record(" in fail_path, "the failing path no longer declares its denominator"


# ---------------------------------------------------------------- half three: the meta-fence

def test_meta_fence_refuses_to_certify_an_empty_board() -> None:
    """check_denominators must fail rather than report a clean board over zero fences."""
    empty = summarise(_ROOT, scope=[])
    assert empty["n_fences"] == 0
    assert empty["coverage"] is None, "coverage over zero fences must not read as a number"
    assert fence_exit("OK", {"OK", "PARTIAL"}, scanned=empty["n_fences"],
                      of="t", fence="t") == FAIL


def test_meta_fence_runs_and_reports_a_measured_denominator() -> None:
    r = _run("check_denominators.py", "--json")
    assert r.returncode in (0, 2), r.stderr[-800:]
    rep = json.loads(r.stdout)
    assert rep["n_fences"] > 20, "scope discovery found implausibly few fences"
    assert rep["status"] in ("OK", "PARTIAL", "VACUOUS", "UNMEASURED")
    if rep["status"] in ("OK", "PARTIAL"):
        assert rep["n_declared"] > 0, "a passing board with zero declarations is vacuous"


def test_unmeasured_never_reads_as_ok() -> None:
    """L1.28a, pinned: the two blind statuses must both exit non-zero."""
    passing = frozenset({"OK", "PARTIAL"})
    assert fence_exit("UNMEASURED", passing, scanned=42, of="t", fence="t") == FAIL
    assert fence_exit("VACUOUS", passing, scanned=42, of="t", fence="t") == FAIL


# --------------------------------------------------------------------------------------------
# R0417 -- the two highest-blast-radius fences named by the coverage queue. Behavioural, not
# source-level: both failure modes are "the fence ran, measured NOTHING, and exited 0", which a
# grep for `scanned=` cannot distinguish from a fence that measured everything.
# --------------------------------------------------------------------------------------------

# The per-test `_isolated_registry` fixture that used to sit here became the suite-wide autouse
# `_denominator_registry_in_tmp` in tests/conftest.py (R0474): these tests drive real fence
# mains under SYNTHETIC scopes, so their `scanned=` counts are fiction, and check_denominators
# reads the LAST row per fence -- but so does every OTHER test that touches fence_exit, which is
# why the redirect had to stop being opt-in.


def test_suite_never_writes_the_live_denominator_registry(tmp_path) -> None:
    """R0474, pinned: inside the suite, the registry's default root IS this test's tmp_path.

    Asserted on `_root()` rather than on the live file's size because cron fences legitimately
    append to the live registry while the suite runs -- a size assertion would flake on every
    real fence firing.
    """
    import libs.ops.denominator as den

    assert den._root() == tmp_path
    fence_exit("OK", {"OK"}, scanned=3, of="t", fence="t")
    row = den.load(tmp_path).get("t")
    assert row is not None and row["n_scanned"] == 3, "the redirected registry took the row"


def test_a_fully_dark_utilisation_board_does_not_exit_zero(
        tmp_path, monkeypatch) -> None:
    """Every ceiling UNMEASURED must never render as "no ceiling is unexplainedly idle".

    `Ceiling.status` returns UNMEASURED before any idle branch, so an unmeasured ceiling cannot
    enter `idle_unexplained`. Kill every reading and the old expression was `not []` -> exit 0:
    a board that measured nothing reported the same verdict as a fully saturated one, inverting
    this fence's own law (L1.28a -- unmeasured utilisation counts as ZERO).
    """
    import scripts.check_utilisation as U

    dark = [U.Ceiling(name=f"c{i}", limit=100.0, used=0.0, unit="u", measured=False,
                      binding_constraint="", why_it_matters="t") for i in range(10)]
    monkeypatch.setattr(U, "collect", lambda: dark)
    monkeypatch.setattr(U, "_OUT", tmp_path / "utilisation.json")
    # --json, because the human-readable branch prints `_OUT.relative_to(_ROOT)` and _OUT is
    # redirected into tmp_path here. Same main(), same exit expression.
    monkeypatch.setattr(sys, "argv", ["check_utilisation.py", "--json"])

    rep = U.build()
    assert rep["idle_unexplained"] == [], "precondition: the dark board looks clean to the old test"
    assert len(rep["unmeasured"]) == 10
    assert U.main() != 0, "a board with zero live readings must not exit 0 (L1.57)"


def test_a_measured_utilisation_board_still_passes(
        tmp_path, monkeypatch) -> None:
    """The other direction, so the fix cannot be 'fail always' (L1.43: a fence red from day one
    gets switched off)."""
    import scripts.check_utilisation as U

    live = [U.Ceiling(name=f"c{i}", limit=100.0, used=100.0, unit="u", measured=True,
                      binding_constraint="", why_it_matters="t") for i in range(3)]
    monkeypatch.setattr(U, "collect", lambda: live)
    monkeypatch.setattr(U, "_OUT", tmp_path / "utilisation.json")
    # --json, because the human-readable branch prints `_OUT.relative_to(_ROOT)` and _OUT is
    # redirected into tmp_path here. Same main(), same exit expression.
    monkeypatch.setattr(sys, "argv", ["check_utilisation.py", "--json"])
    assert U.main() == 0


def test_mypy_ratchet_with_nothing_checkable_does_not_exit_zero(
        tmp_path, monkeypatch) -> None:
    """Uncheckable files are POPPED from `counts`, so "mypy could not run" and "mypy found no
    errors" produced byte-identical reports: total_errors 0, n_files_checked 0, exit 0. The
    ratchet it feeds would then record that phantom perfection as the new floor."""
    import scripts.check_mypy_ratchet as M

    targets = ["scripts/a.py", "scripts/b.py"]
    monkeypatch.setattr(M, "_targets", lambda: targets)
    monkeypatch.setattr(M, "measure", lambda t: ({}, list(t)))   # every target uncheckable
    monkeypatch.setattr(M, "_BASELINE", tmp_path / "mypy_ratchet.json")
    monkeypatch.setattr(sys, "argv", ["check_mypy_ratchet.py"])
    assert M.main() != 0, "zero files checked must not read as a clean ratchet (L1.57)"


def test_mypy_ratchet_passes_when_files_were_actually_checked(
        tmp_path, monkeypatch) -> None:
    import scripts.check_mypy_ratchet as M

    monkeypatch.setattr(M, "_targets", lambda: ["scripts/a.py"])
    monkeypatch.setattr(M, "measure", lambda t: ({"scripts/a.py": 0}, []))
    monkeypatch.setattr(M, "_BASELINE", tmp_path / "mypy_ratchet.json")
    monkeypatch.setattr(sys, "argv", ["check_mypy_ratchet.py"])
    assert M.main() == 0
