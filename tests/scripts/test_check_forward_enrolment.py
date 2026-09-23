"""THE ENROLMENT LAW GATE -- a planted cap must be rejected, and a clockless certificate fails.

The single most important assertion in this file is that a PLANTED CAP GOES RED. A fence over a
rule nobody can re-break is decoration; the way the slot quota comes back is by somebody typing
`MAX_ENROLMENTS = 12` or `enrolled = enrolled[:n]` in good faith six months from now, and this is
what has to catch that edit at the commit.

The second is that the fence does NOT fail on the record of WHY the quota was removed. Those five
files discuss caps at length in their docstrings -- deliberately, because the reasoning is the
only thing that stops the quota being re-invented -- so the scan is AST-based and a fence that
grepped for the word would fail on its own explanation. That case is tested explicitly.

The third is UNMEASURED: an absent artifact on a clean checkout is a real answer, not a pass and
not a failure the checkout could not fix (L1.28a, L1.43 -- a gate that reports RED on every PR is
a gate that gets switched off).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# BY PATH, NOT BY PACKAGE NAME. `tests/scripts/` is itself an importable package called `scripts`,
# and pytest puts `tests/` on sys.path when this file is collected on its own -- at which point
# `import scripts.check_forward_enrolment` resolves to the TEST directory and raises. Loading the
# fence from its own path is the one form that means the same run alone and run in the suite.
_SPEC = importlib.util.spec_from_file_location(
    "check_forward_enrolment_fence", _ROOT / "scripts" / "check_forward_enrolment.py")
assert _SPEC is not None and _SPEC.loader is not None
fence = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = fence
_SPEC.loader.exec_module(fence)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------- a planted cap goes RED
def test_a_planted_cap_constant_is_rejected() -> None:
    src = "MAX_ENROLMENTS = 12\nenrolled = every_certificate()\n"
    found = fence.scan_source(src, "planted.py")
    assert found, "a quota constant must be caught"
    assert "MAX_ENROLMENTS" in found[0]
    assert "no capital" in found[0]


def test_a_planted_slice_of_the_roster_is_rejected() -> None:
    found = fence.scan_source("enrolled = enrolled[:12]\n", "planted.py")
    assert found and "slices the enrolment roster" in found[0]


def test_a_planted_count_gate_is_rejected() -> None:
    src = "if len(enrolled) >= cap:\n    return []\n"
    found = fence.scan_source(src, "planted.py")
    assert found and "count gate on enrolment is a quota" in found[0]


def test_every_cap_spelling_the_fence_declares_is_actually_caught() -> None:
    for name in ("MAX_ENROLMENTS", "ENROLMENT_CAP", "ENROLLMENT_QUOTA", "FORWARD_SLOT_QUOTA",
                 "MAX_FORWARD_CLOCKS", "CLOCK_QUOTA"):
        assert fence.scan_source(f"{name} = 12\n", "planted.py"), name


def test_a_planted_cap_in_the_real_tree_fails_the_portable_half(tmp_path) -> None:
    """The fence reads the tree it is pointed at, so the plant lands in a copy, never in the box."""
    for rel in fence.PATROLLED:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    victim = tmp_path / "desks/mt5/research/shadow_forward.py"
    victim.write_text(victim.read_text(encoding="utf-8") + "\n\nMAX_ENROLMENTS = 12\n",
                      encoding="utf-8")
    fails, _ = fence.check_sources(tmp_path)
    assert any("MAX_ENROLMENTS" in f for f in fails)


def test_the_real_tree_is_clean_today() -> None:
    fails, _ = fence.check_sources()
    assert fails == [], f"the enrolment path already carries a cap: {fails}"


def test_the_fence_does_not_fail_on_the_record_of_why_the_quota_was_removed() -> None:
    """The docstrings say 'cap', 'quota' and 'MAX_FORWARD_SLOTS' on purpose. AST, not grep."""
    prose = ('"""A cap on enrolment is forbidden; MAX_ENROLMENTS would be a quota and '
             'enrolled[:12] would be a slice."""\n# ENROLMENT_CAP = 3 would be a defect\n')
    assert fence.scan_source(prose, "prose.py") == []


def test_removing_the_reconcile_declaration_fails(tmp_path) -> None:
    for rel in fence.PATROLLED:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    victim = tmp_path / "desks/mt5/research/forward_reconcile.py"
    victim.write_text(victim.read_text(encoding="utf-8")
                      .replace('"gates_enrolment": False', '"gates_enrolment": True'),
                      encoding="utf-8")
    fails, _ = fence.check_sources(tmp_path)
    assert any("gates_enrolment" in f for f in fails)


def test_the_ranker_must_keep_declaring_itself_a_report(tmp_path) -> None:
    for rel in fence.PATROLLED:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    victim = tmp_path / "desks/mt5/research/forward_slot_ranker.py"
    victim.write_text(victim.read_text(encoding="utf-8")
                      .replace("REPLACEABLE IS A REPORT, NEVER AN ACT", "REPLACEABLE IS AN ACT"),
                      encoding="utf-8")
    fails, _ = fence.check_sources(tmp_path)
    assert any("stopped declaring itself a report" in f for f in fails)


# -------------------------------------------------------------------------- the state half
def _report(tmp_path, **over) -> Path:
    doc = {"at": NOW.isoformat(), "quota": {"capped": False}, "n_certificates": 170,
           "n_enrolled": 170, "n_missing": 0, "overdue": [],
           "latency_h": {"max": 0.0, "target": 0.0}}
    doc.update(over)
    path = tmp_path / "FORWARD_ENROLMENT.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_a_clean_census_passes(tmp_path) -> None:
    fails, notes = fence.check_state(_report(tmp_path), NOW)
    assert fails == []
    assert any("enrolled=170" in n for n in notes)


def test_a_certificate_clockless_past_one_cycle_fails(tmp_path) -> None:
    overdue = [{"key": "USDZAR.overnight_gap_decay.asia.LONG", "clockless_hours": 91.0,
                "why": "NO CLOCK: certified and accruing no forward evidence"}]
    fails, _ = fence.check_state(_report(tmp_path, n_missing=1, overdue=overdue), NOW)
    assert len(fails) == 1
    assert "CERTIFIED-NOT-ENROLLED" in fails[0]
    assert "91.0h" in fails[0]


def test_a_certificate_missing_but_inside_the_cycle_is_a_note_not_a_breach(tmp_path) -> None:
    fails, notes = fence.check_state(_report(tmp_path, n_missing=2, overdue=[]), NOW)
    assert fails == []
    assert any("none yet past one cycle" in n for n in notes)


def test_a_report_declaring_a_cap_fails(tmp_path) -> None:
    fails, _ = fence.check_state(_report(tmp_path, quota={"capped": True}), NOW)
    assert any("re-introduced" in f for f in fails)


def test_an_absent_artifact_is_unmeasured_not_a_breach(tmp_path) -> None:
    fails, notes = fence.check_state(tmp_path / "nope.json", NOW)
    assert fails == []
    assert any("UNMEASURED" in n for n in notes)


def test_an_unreadable_artifact_is_a_breach(tmp_path) -> None:
    path = tmp_path / "FORWARD_ENROLMENT.json"
    path.write_text("{not json", encoding="utf-8")
    fails, _ = fence.check_state(path, NOW)
    assert fails and "unreadable" in fails[0]


def test_a_stale_census_is_named(tmp_path) -> None:
    old = (NOW - timedelta(hours=9)).isoformat()
    _, notes = fence.check_state(_report(tmp_path, at=old), NOW)
    assert any("has not run" in n for n in notes)


def test_the_cli_runs_both_halves_and_exits_zero_today() -> None:
    assert fence.main(["--surfaces-only"]) == 0
