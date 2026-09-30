"""The box's own hourly law gate fails a drifted certificate store, and the hourly leg never migrates.

ONE CERTIFICATE TRUTH (principal 2026-09-22) has two halves. `scripts/check_certificate_truth.py`
with `--require-state` is the live half: on a host with desk state, an absent authority file or
any divergence between UNIVERSAL_SURVIVORS.json and a derived store fails. That only protects the
box if the box RUNS it. It does: MT5-LawGate (desks/mt5/ops/box_tasks.manifest, hourly at :40)
runs `scripts/run_law_gate.py --rotate`, and the rotation walks `_LAW_FENCES + _STATE_FENCES`,
invoking every declared argument set of a fence and failing the fence if any invocation fails.

The other half is refused on the clock: `research/certificate_truth.py --apply` retired 837 rows
against a stale canon once (see run_law_gate's LAWS 7 note), and running it automatically was
denied by the permission classifier on 2026-09-30. The hourly leg audits and publishes only.
These tests pin both so neither can drift silently.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts import run_law_gate as lg

ROOT = Path(__file__).resolve().parents[2]


def test_the_state_battery_carries_certificate_truth_with_require_state() -> None:
    assert ("check_certificate_truth.py", ("--require-state",)) in lg._STATE_FENCES
    assert ("check_certificate_truth.py", ()) in lg._LAW_FENCES


def test_the_rotation_the_box_runs_invokes_require_state(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake(root: Path, script: str, extra: tuple[str, ...], timeout: float) -> dict:
        calls.append((script, tuple(extra)))
        ok = not (script == "check_certificate_truth.py" and "--require-state" in extra)
        return {"fence": script, "ok": ok, "rc": 0 if ok else 1,
                "detail": "" if ok else "divergence: sleeves.json holds a certificate the "
                                        "canon does not"}

    monkeypatch.setattr(lg, "_run_fence", fake)
    rep = lg.rotate_gate(tmp_path, budget_s=1e9)
    assert ("check_certificate_truth.py", ("--require-state",)) in calls
    # A drifted store fails the box's own gate, even though the portable half passed.
    row = rep["fences"]["check_certificate_truth.py"]
    assert row["ok"] is False and row["n_invocations"] == 2
    assert rep["ok"] is False
    assert any(f.startswith("check_certificate_truth.py") for f in rep["failures"])


def test_the_box_task_runs_the_full_rotation_not_the_laws_only_half() -> None:
    manifest = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text("utf-8")
    (task,) = re.findall(r'TASK name="MT5-LawGate"[^\n]*', manifest)
    assert 'runs="scripts/run_law_gate.py --rotate' in task
    assert "--laws-only" not in task
    installer = (ROOT / "desks/mt5/scripts/install_law_gate_task.ps1").read_text("utf-8")
    assert "run_law_gate.py --rotate" in installer and "--laws-only" not in installer


def test_the_hourly_certificate_truth_leg_never_applies_the_migration() -> None:
    src = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    call = re.search(r'_costed\("certificate_truth",.*?\)\)', src, re.S)
    assert call, "the certificate_truth leg is gone from the hourly cycle"
    assert '"research/certificate_truth.py"' in call.group(0)
    assert "--apply" not in call.group(0)
