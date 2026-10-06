"""The two #117 organs' box-local audit trails are IGNORED, not left untracked-and-unignored.

Audit 2026-10-06: `desks/mt5/data/build_failures.jsonl` (build_failure_bank) and
`desks/mt5/data/experiment_contract_history.jsonl` (check_experiment_contracts --report) were
neither tracked nor ignored, so every hourly pass left the box's tree dirty. Each is read only by
its own writer on the host that writes it -- nothing reads either from git -- so they are audit
trails and belong in .gitignore.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAILS = ("desks/mt5/data/build_failures.jsonl",
          "desks/mt5/data/experiment_contract_history.jsonl",
          "logs/gate_calibration.json")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          check=False)


def test_audit_trails_are_ignored_and_untracked() -> None:
    for rel in TRAILS:
        assert _git("check-ignore", "-q", "--no-index", rel).returncode == 0, rel
        assert _git("ls-files", "--error-unmatch", rel).returncode != 0, rel


def test_writers_still_name_the_ignored_paths() -> None:
    """If a writer moves its trail, this pin must move with it, or the new path is dirty again."""
    assert "build_failures.jsonl" in (
        ROOT / "desks/mt5/research/build_failure_bank.py").read_text("utf-8")
    assert "experiment_contract_history.jsonl" in (
        ROOT / "scripts/check_experiment_contracts.py").read_text("utf-8")
