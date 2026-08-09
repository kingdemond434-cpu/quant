"""FORWARD-COHORT INTEGRITY (L1.6) -- the first tests the desk's most load-bearing integer has had.

The Holm cohort size `m` is the only multiplicity the two-stage law recognises, and the forward bar
is "fixed for life" only while `m` is counted correctly. It had four disagreeing producers, zero
tests, and `concurrent_m()` -- the function whose entire purpose is to supply it -- had zero
callers. Measured 2026-08-05: the axis clocks ran at holm_bar(3)=2.13 against a true cohort of 11
(bar 2.61), an alpha of 0.0167 per clock against a designed 0.0045.

EVERY TEST HERE IS DIRECTIONAL. Understating m LOOSENS the bar and manufactures edge; overstating
it only costs clock time. So the invariants below assert the SIGN of each failure mode, not just
that a number came back -- a fail-safe that floors in the wrong direction would pass a naive
"returns an int" test while doing precisely the damage it was written to prevent.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from libs.research.slot_registry import (
    MAX_FORWARD_SLOTS,
    CohortM,
    cohort_m_for_bar,
    concurrent_m,
    derive_slots,
)

_ROOT = Path(__file__).resolve().parents[2]


# ---------------- the fail-safe: every degraded path must TIGHTEN, never loosen ---------------
def test_cohort_m_is_measured_and_matches_the_registry():
    snap, cohort = derive_slots(), cohort_m_for_bar()
    assert isinstance(cohort, CohortM)
    if snap["complete"]:
        assert cohort.provenance == "MEASURED"
        assert cohort.m == max(int(snap["m_concurrent"]), 1)


def test_incomplete_cohort_floors_at_the_cap_rather_than_undercounting(monkeypatch):
    """An unreadable source makes m a LOWER bound. Using it raw would loosen every bar."""
    import libs.research.slot_registry as sr

    monkeypatch.setattr(sr, "derive_slots", lambda: {
        "m_concurrent": 2, "complete": False, "unknown_sources": ["data/axis_shadow_state.json"]})
    got = sr.cohort_m_for_bar()
    assert got.provenance == "INCOMPLETE-FLOORED"
    assert got.m == MAX_FORWARD_SLOTS          # floored UP to the cap, not left at 2
    assert got.m > 2, "an incomplete cohort must never yield a looser bar than a known one"


def test_unusable_registry_refuses_to_the_cap_instead_of_returning_a_small_m(monkeypatch):
    import libs.research.slot_registry as sr

    def _boom():
        raise OSError("registry gone")

    monkeypatch.setattr(sr, "derive_slots", _boom)
    got = sr.cohort_m_for_bar()
    assert got.provenance == "REFUSED-FLOORED"
    assert got.m == MAX_FORWARD_SLOTS
    assert not got.measured


def test_over_cap_cohort_keeps_the_true_m_not_the_cap(monkeypatch):
    """The cap limits how many clocks may RUN; it is not a ceiling on the bar they pay."""
    import libs.research.slot_registry as sr

    monkeypatch.setattr(sr, "derive_slots", lambda: {
        "m_concurrent": 17, "complete": True, "unknown_sources": []})
    assert sr.cohort_m_for_bar().m == 17


def test_concurrent_m_delegates_to_the_failsafe(monkeypatch):
    """This function had zero callers while the bar ran wrong. It must not be a bare len()."""
    import libs.research.slot_registry as sr

    monkeypatch.setattr(sr, "derive_slots", lambda: {
        "m_concurrent": 1, "complete": False, "unknown_sources": ["x"]})
    assert concurrent_m() == MAX_FORWARD_SLOTS


def test_cohort_m_never_returns_zero(monkeypatch):
    """m=0 would zero out the correction and hand every candidate the uncorrected 1.65 bar."""
    import libs.research.slot_registry as sr

    monkeypatch.setattr(sr, "derive_slots", lambda: {
        "m_concurrent": 0, "complete": True, "unknown_sources": []})
    assert sr.cohort_m_for_bar().m >= 1


# ---------------- the wiring: these fail the moment the repair is reverted --------------------
def test_no_script_computes_a_holm_bar_from_a_local_len():
    """THE REGRESSION TEST. `holm_bar(len(_AXES))` is what charged the desk's multiplicity to one
    script's roster. Checked via AST so that prose describing the defect does not trip it."""
    from scripts.check_cohort_integrity import _scan_bad_bar_sites

    hits, unparseable = _scan_bad_bar_sites()
    assert hits == [], f"Holm bar computed from a local len() at: {hits}"
    assert unparseable == [], f"unparseable source hides the defect from the scan: {unparseable}"


def test_axis_runner_imports_the_registry():
    """If the import goes, the bar falls back to a roster count and nothing else notices."""
    src = (_ROOT / "scripts/run_axis_shadows.py").read_text("utf-8")
    tree = ast.parse(src)
    imported = {
        alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        and node.module == "libs.research.slot_registry" for alias in node.names
    }
    assert "cohort_m_for_bar" in imported


#: Artifacts written by the running desk and excluded from git (`web/*`, `data/*`). Tests that
#: assert on them are asserting about ONE HOST'S DISK, and they were green on the VPS and red in
#: CI on every push from 2026-08-05. The substance is worth keeping, so the precondition is made
#: explicit instead of the assertion being deleted: present -> assert, absent -> skip and NAME the
#: artifact. A silent pass would be the worse of the two failures.
_RUNTIME_ONLY = "written by the running desk; gitignored, so absent from every fresh clone"


def test_axis_artifact_records_the_m_it_used_and_it_is_not_the_axis_count():
    """A bar is only auditable if its artifact says which cohort it was computed against."""
    art = _ROOT / "web/axis_shadows.json"
    if not art.exists():
        pytest.skip(f"web/axis_shadows.json -- {_RUNTIME_ONLY}")
    doc = json.loads(art.read_text("utf-8"))
    assert isinstance(doc.get("m_concurrent"), int)
    assert doc.get("m_provenance") in {"MEASURED", "INCOMPLETE-FLOORED", "REFUSED-FLOORED"}
    assert doc["m_concurrent"] >= cohort_m_for_bar().m


# ---------------- the fence itself: it must not report OK on nothing (L1.28a) -----------------
def _report(monkeypatch, **over):
    import scripts.check_cohort_integrity as f

    base = {"m_concurrent": 11, "complete": True, "unknown_sources": []}
    base.update(over)
    monkeypatch.setattr("libs.research.slot_registry.derive_slots", lambda: base)
    return f


def test_fence_is_green_on_the_live_tree():
    from scripts.check_cohort_integrity import build_report

    rep = build_report()
    # THE DANGEROUS CONDITION IS CHECKED UNCONDITIONALLY, BEFORE ANY SKIP. `too_loose` is an
    # artifact judged against a SMALLER cohort than the registry knows about -- the phantom-edge
    # direction, and the entire reason this fence exists. It must never be skipped for any host.
    assert not rep["too_loose"], f"BAR-TOO-LOOSE: {rep['too_loose']}"

    # The skip now keys on the CAUSE, not on a proxy. It used to key on
    # `data/axis_shadow_state.json` existing, taking that as "this is the live desk" -- but
    # running run_axis_shadows.py once on a clone creates that file while the other seven cohort
    # sources stay absent, flipping the proxy and failing the fence for a reason that is a fact
    # about the host. `unknown_sources` names the sources that could not be read, so it says
    # directly what the proxy was trying to infer.
    #
    # This can only ever skip a report that is FLOORED, which the fence's own detail describes as
    # "bars are safe but the desk is flying on a floor" -- conservative by construction, and the
    # too_loose assertion above still bites underneath it.
    if rep["status"] == "COHORT-INCOMPLETE" and rep["unknown_sources"]:
        pytest.skip(f"cohort sources -- {_RUNTIME_ONLY}. {len(rep['unknown_sources'])} source(s) "
                    f"unreadable on this host, so m is a FLOOR rather than a measurement and the "
                    f"bar is capped conservatively: {rep['detail']}")
    assert rep["status"] == "OK", f"{rep['status']}: {rep['detail']}"
    assert rep["shipped_bar_crosscheck"] == "agrees", "local bar diverges from the shipped one"


def test_fence_fires_when_an_artifact_was_judged_against_a_smaller_cohort(monkeypatch, tmp_path):
    """The exact 2026-08-05 defect, replayed: artifact says m=3, registry says 11."""
    import scripts.check_cohort_integrity as f

    art = tmp_path / "axis.json"
    art.write_text(json.dumps({"m_concurrent": 3}), "utf-8")
    monkeypatch.setattr(f, "_ROOT", tmp_path)
    monkeypatch.setattr(f, "_BAR_ARTIFACTS", {"axis.json": "m_concurrent"})
    monkeypatch.setattr(f, "_OCCUPANCY_ARTIFACTS", {})
    monkeypatch.setattr(f, "_scan_bad_bar_sites", lambda: ([], []))
    rep = f.build_report()
    assert rep["status"] == "BAR-TOO-LOOSE"
    assert rep["too_loose"][0]["m_used"] == 3
    assert rep["too_loose"][0]["bar_required"] > rep["too_loose"][0]["bar_used"]


def test_fence_reports_unmeasured_not_ok_when_nothing_can_be_compared(monkeypatch, tmp_path):
    """An empty measurement set must never read as a healthy one."""
    import scripts.check_cohort_integrity as f

    monkeypatch.setattr(f, "_ROOT", tmp_path)
    monkeypatch.setattr(f, "_BAR_ARTIFACTS", {"absent.json": "m_concurrent"})
    monkeypatch.setattr(f, "_OCCUPANCY_ARTIFACTS", {})
    monkeypatch.setattr(f, "_scan_bad_bar_sites", lambda: ([], []))
    rep = f.build_report()
    assert rep["status"] == "UNMEASURED"
    assert rep["artifacts_checked"] == 0


def test_fence_reports_no_data_when_the_registry_is_unusable(monkeypatch):
    import scripts.check_cohort_integrity as f

    def _boom():
        raise OSError("gone")

    monkeypatch.setattr("libs.research.slot_registry.derive_slots", _boom)
    rep = f.build_report()
    assert rep["status"] == "NO-DATA"
    assert rep["m_true"] == 0


def test_fence_ast_scan_ignores_prose_describing_the_defect(tmp_path, monkeypatch):
    """The first cut of this fence grepped source text and flagged its own docstring. A fence that
    fires on the documentation of the bug it prevents is one somebody switches off."""
    import scripts.check_cohort_integrity as f

    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts/prose.py").write_text(
        '"""Explains that holm_bar(len(_AXES)) was the defect."""\nx = 1\n', "utf-8")
    (tmp_path / "scripts/real.py").write_text(
        "from x import holm_bar\n_A = [1]\nbar = holm_bar(len(_A), rank=1)\n", "utf-8")
    monkeypatch.setattr(f, "_ROOT", tmp_path)
    hits, unparseable = f._scan_bad_bar_sites()
    assert unparseable == []
    assert any("real.py" in h for h in hits)
    assert not any("prose.py" in h for h in hits)


def test_fence_ast_scan_survives_a_byte_order_mark(tmp_path, monkeypatch):
    """A BOM decodes to U+FEFF under plain utf-8 and SyntaxErrors the parse -- which is how
    scripts/research_memory.py was invisible to every AST tool here while importing perfectly."""
    import scripts.check_cohort_integrity as f

    (tmp_path / "scripts").mkdir()
    (tmp_path / "libs").mkdir()
    (tmp_path / "scripts/bom.py").write_bytes(b"\xef\xbb\xbf#!/usr/bin/env python3\nx = 1\n")
    monkeypatch.setattr(f, "_ROOT", tmp_path)
    hits, unparseable = f._scan_bad_bar_sites()
    assert unparseable == [], "a BOM must not blind the scanner"
    assert hits == []


def test_no_tracked_python_file_carries_a_byte_order_mark():
    """Adjacency guard: one BOM already hid a mandated script from every AST tool on the desk."""
    import subprocess

    files = subprocess.run(["git", "ls-files", "*.py"], cwd=_ROOT,
                           capture_output=True, text=True, check=False).stdout.split()
    bad = [f for f in files if (_ROOT / f).read_bytes().startswith(b"\xef\xbb\xbf")]
    assert bad == [], f"BOM-prefixed sources are invisible to ast.parse: {bad}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
