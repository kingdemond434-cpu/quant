"""Judge P0 (2026-11-25): the off-box rule checks can read JUDGE_EFFICIENCY.json and the
certified non-exotic total."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"


def test_judge_efficiency_rides_the_box_sync_and_is_not_gitignored() -> None:
    ps1 = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/JUDGE_EFFICIENCY.json",' in ps1
    r = subprocess.run(["git", "check-ignore", "-q", "desks/mt5/reports/JUDGE_EFFICIENCY.json"],
                       cwd=ROOT, check=False)
    assert r.returncode == 1                       # 1 = not ignored


def test_shadow_health_publishes_certified_non_exotic_total() -> None:
    src = (DESK / "research" / "shadow_cycle.py").read_text("utf-8")
    assert '"certified_non_exotic_total"' in src
    assert 'census["excluded"].get(' in src and '"exotic"' in src
