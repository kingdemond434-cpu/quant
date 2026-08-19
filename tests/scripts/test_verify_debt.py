"""The verify pass has an ACTUATOR, and its vocabulary cannot drift from its fence.

verify-pass-skipped (max_audit.check_verify_lag) fired for days with nothing anywhere able to
repair it: "verify" is deliberately not in the panel rotation, and only a human PANEL_MISSION
override ever selected it -- an actuatorless law. The repair puts the debt check at the mission
choke point: while a triage-bearing run stands unaudited, the next panel run IS the verify pass.

Two copies of "which missions bear triage" now exist (the fence's inline tuple and the panel's
_TRIAGE_MISSIONS), and two copies of one vocabulary is how leg_modes' 16.9x disagreement
happened -- so the first test here pins them EQUAL by reading the fence's literal out of its
AST. Editing either side without the other fails this file, not a production run.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import run_external_panel as panel  # noqa: E402


def _fence_triage_tuple() -> tuple[str, ...]:
    """The literal `("audit", ...)` inside max_audit.check_verify_lag, read from source."""
    tree = ast.parse((_ROOT / "scripts/max_audit.py").read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "check_verify_lag":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Tuple)
                        and all(isinstance(e, ast.Constant) for e in sub.elts)
                        and "audit" in [e.value for e in sub.elts]):
                    return tuple(e.value for e in sub.elts)
    raise AssertionError("check_verify_lag's triage tuple not found -- fence moved?")


def test_triage_vocabulary_is_lockstep_with_the_fence() -> None:
    assert tuple(panel._TRIAGE_MISSIONS) == _fence_triage_tuple()


def test_verify_is_not_in_the_rotation() -> None:
    """A clock would burn a paid run when there is nothing to audit; only debt selects it."""
    assert "verify" not in panel._ROTATION


def _write_log(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "external_panel_log.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def test_debt_when_triage_has_no_verify_after_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel, "_LOG", _write_log(tmp_path, [
        {"mission": "verify", "ts": "2026-08-01T00:00:00+00:00"},
        {"mission": "audit", "ts": "2026-08-12T03:36:00+00:00"},
    ]))
    assert panel._verify_debt() is True


def test_no_debt_once_a_verify_follows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel, "_LOG", _write_log(tmp_path, [
        {"mission": "audit", "ts": "2026-08-12T03:36:00+00:00"},
        {"mission": "verify", "ts": "2026-08-13T00:00:00+00:00"},
    ]))
    assert panel._verify_debt() is False


def test_non_triage_missions_carry_no_debt(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """generate/data/benchmark produce no triage, so they owe no auditor."""
    monkeypatch.setattr(panel, "_LOG", _write_log(tmp_path, [
        {"mission": "generate", "ts": "2026-08-12T03:36:00+00:00"},
    ]))
    assert panel._verify_debt() is False


def test_missing_or_malformed_log_fails_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel, "_LOG", tmp_path / "absent.jsonl")
    assert panel._verify_debt() is False
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n" + json.dumps(
        {"mission": "audit", "ts": "2026-08-12T00:00:00+00:00"}) + "\n", "utf-8")
    monkeypatch.setattr(panel, "_LOG", bad)
    assert panel._verify_debt() is True, "malformed lines are skipped, not the whole file"


def test_mission_repays_the_debt_before_the_rotation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PANEL_MISSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_external_panel.py"])
    monkeypatch.setattr(panel, "_verify_debt", lambda: True)
    name, prompt = panel._mission()
    assert name == "verify"
    assert prompt, "the verify mission text must load"


def test_override_still_wins_over_the_debt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MONTHLY tier1 forcing must be untouched by the actuator."""
    monkeypatch.setattr(sys, "argv", ["run_external_panel.py"])
    monkeypatch.setenv("PANEL_MISSION", "tier1")
    monkeypatch.setattr(panel, "_verify_debt", lambda: True)
    name, _ = panel._mission()
    assert name == "tier1"


def test_no_debt_runs_the_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PANEL_MISSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_external_panel.py"])
    monkeypatch.setattr(panel, "_verify_debt", lambda: False)
    name, _ = panel._mission()
    assert name in panel._ROTATION or name == "audit"
