"""L1.41 build standard -- nothing enters below the bar; timid work is never caught later."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_build_standard import (
    _GOVERNED,
    _SCHEDULE_EXEMPT,
    _has_silent_swallow,
    audit_organ,
    build_report,
)


def test_every_governed_organ_meets_the_standard():
    rep = build_report()
    assert rep["status"] == "OK", rep["detail"]
    assert rep["n_governed"] >= 12


def test_the_fence_governs_itself():
    # A build-standard fence exempt from its own standard is the decoration it exists to detect.
    assert "check_build_standard.py" in _GOVERNED


def test_missing_refusal_path_is_caught(tmp_path):
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts/x.py").write_text("def main():\n    return 0\n", "utf-8")
    r = audit_organ(tmp_path, "x.py", manifest="", matrix_src="", test_blob="")
    assert any("NO-REFUSAL-PATH" in v for v in r["violations"])
    assert any("UNTESTED" in v for v in r["violations"])
    assert any("UNSCHEDULED" in v for v in r["violations"])
    assert any("UNMAPPED" in v for v in r["violations"])


def test_silent_swallow_detected_and_logged_alternative_is_not():
    swallow = ast.parse("try:\n    x=1\nexcept OSError:\n    pass\n")
    assert _has_silent_swallow(swallow) is True
    handled = ast.parse("try:\n    x=1\nexcept OSError as e:\n    notes.append(e)\n")
    assert _has_silent_swallow(handled) is False


def test_schedule_exemptions_carry_a_reason():
    # "No cron line" must be a DECISION, never a default.
    for organ, reason in _SCHEDULE_EXEMPT.items():
        assert organ in _GOVERNED
        assert len(reason) > 40, f"{organ}: exemption reason too thin to be a decision"


def test_missing_organ_fails_rather_than_passing_silently(tmp_path):
    (tmp_path / "scripts").mkdir(parents=True)
    r = audit_organ(tmp_path, "nope.py", manifest="", matrix_src="", test_blob="")
    assert r["ok"] is False and "MISSING" in r["violations"][0]


def test_runs_inside_the_law_gate():
    src = Path("scripts/run_law_gate.py").read_text("utf-8")
    assert "check_build_standard.py" in src        # so every commit/push/CI run enforces it
