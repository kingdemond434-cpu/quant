"""The L1.60 fence: statuses, its self-application, and the three repairs it was built to force.

The regression block at the bottom is the part that matters over time. It pins the ACTUAL fences
that were leaking on 2026-08-12, so reverting any one of the `attempted` counters turns a test
red rather than quietly restoring a denominator that flatters itself.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from libs.ops.attrition import analyse_paths, summarise

_ROOT = Path(__file__).resolve().parents[2]


def _fence() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_cda", _ROOT / "scripts" / "check_denominator_attrition.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_empty_scope_is_unmeasured_never_ok(tmp_path: Path) -> None:
    """L1.28a: an empty measurement set may never read as a clean board."""
    (tmp_path / "scripts").mkdir()
    rep = _fence().build("fences", tmp_path)
    assert rep["status"] == "UNMEASURED"
    assert rep["n_examined"] == 0


def test_unparsed_only_scope_is_unmeasured(tmp_path: Path) -> None:
    """Discovered but unreadable is still UNMEASURED -- not a pass over survivors."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_broken.py").write_text("def f(:\n", "utf-8")
    rep = _fence().build("fences", tmp_path)
    assert rep["status"] == "UNMEASURED"
    assert rep["n_examined"] == 1 and rep["n_unparsed"] == 1


def test_leaking_fence_reports_attrition(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_leak.py").write_text(
        'def s(paths):\n'
        '    n = 0\n'
        '    for p in paths:\n'
        '        try:\n'
        '            t = p.read_text("utf-8")\n'
        '        except OSError:\n'
        '            continue\n'
        '        n += 1\n'
        '    return fence_exit("OK", {"OK"}, scanned=n, of="x")\n', "utf-8")
    rep = _fence().build("fences", tmp_path)
    assert rep["status"] == "ATTRITION"
    assert rep["n_findings"] == 1 and rep["n_from_handler"] == 1
    assert "count the attempt" in rep["next_action"]


def test_partial_when_only_unparsed_alongside_clean(tmp_path: Path) -> None:
    """Unparsed files are surfaced, but a work queue is not a cliff (L1.0/L1.43)."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_clean.py").write_text("x = 1\n", "utf-8")
    (tmp_path / "scripts" / "check_bad.py").write_text("def f(:\n", "utf-8")
    rep = _fence().build("fences", tmp_path)
    assert rep["status"] == "PARTIAL"
    assert rep["n_parsed"] == 1 and rep["n_unparsed"] == 1


@pytest.mark.parametrize(("status", "expected_pass"), [
    ("OK", True), ("PARTIAL", True), ("ATTRITION", False), ("UNMEASURED", False)])
def test_only_declared_statuses_pass(status: str, expected_pass: bool) -> None:
    assert (status in _fence()._PASSING) is expected_pass


def test_fence_declares_its_own_denominator() -> None:
    """Subject to its own law (L1.57): scanned= must be wired, or it could pass vacuously."""
    src = (_ROOT / "scripts" / "check_denominator_attrition.py").read_text("utf-8")
    assert "scanned=rep[\"n_examined\"]" in src
    assert "fence_exit(" in src


def test_live_run_writes_the_artifact() -> None:
    rep = _fence().build("fences", _ROOT)
    assert rep["status"] in {"OK", "PARTIAL", "ATTRITION", "UNMEASURED"}
    assert rep["n_examined"] > 0, "the governed fence set must not be empty on the real tree"
    out = _ROOT / "data" / "denominator_attrition.json"
    if out.exists():
        json.loads(out.read_text("utf-8"))          # the artifact stays parseable


# --- REGRESSION: the three denominators repaired on 2026-08-12 -------------------------------
# Each of these leaked into a published ratio. Reverting the `attempted` counter re-breaks the
# test, which is the only reason the repair survives a future refactor.

@pytest.mark.parametrize("rel", [
    "scripts/check_coverage_floors.py",   # money_path_pct -> the L1.50 ratchet floor
    "scripts/check_calendar_gates.py",    # N_SCANNED -> fence_exit(scanned=)
    "scripts/check_llm_routing.py",       # routed_fraction -> BACKLOG vs OK
])
def test_repaired_fences_stay_counted(rel: str) -> None:
    s = summarise(analyse_paths([_ROOT / rel], _ROOT))
    assert s["n_findings"] == 0, (
        f"{rel} lost its attempt counter: {s['findings']}")


def test_coverage_floors_publishes_what_it_lost() -> None:
    """The money path is 5 modules; the report must say how many it actually measured."""
    import scripts.check_coverage_floors as cf
    report = {"totals": {"percent_covered": 90.0},
              "files": {m: {"summary": {"num_statements": 100, "covered_lines": 80}}
                        for m in cf.MONEY_PATH}}
    full = cf.measure(report)
    assert full["money_path_attempted"] == len(cf.MONEY_PATH)
    assert full["money_path_measured"] == len(cf.MONEY_PATH)
    assert full["money_path_missing"] == []
    assert full["money_path_pct"] == 80.0

    # Now drop the WORST-covered money-path module, the way a renamed file or a dead test run
    # would. Before the repair this RAISED money_path_pct and the L1.50 ratchet locked it in.
    worst, *rest = list(cf.MONEY_PATH)
    report["files"][worst]["summary"] = {"num_statements": 100, "covered_lines": 0}
    with_dark = cf.measure(report)
    del report["files"][worst]
    dropped = cf.measure(report)

    assert with_dark["money_path_pct"] < dropped["money_path_pct"], (
        "the arithmetic under test: losing a dark module RAISES the percentage")
    assert dropped["money_path_missing"] == [worst]
    assert dropped["money_path_measured"] == len(rest)
