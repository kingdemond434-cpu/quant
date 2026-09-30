"""The fence that goes red when the box's state on the live branch is more than six hours old.

Measured 2026-09-30: the newest stamp inside any box-published file on the live branch was
2026-09-16T16:37:33Z while the orphan re-root re-committed those files on 2026-09-24 -- so the
fence must judge the stamps, not the commit date, and must never pass on absence.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    # `import scripts.x` resolves into the tests/scripts package here, so load by path.
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fence = _load("_quant_check_box_state_freshness", "scripts/check_box_state_freshness.py")
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git required")

_SCRIPT = '''$relPaths = @(
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/live_ledger.jsonl"
)
'''


def _git(cwd: Path, *args: str, date: str | None = None) -> None:
    env = {**os.environ}
    if date:
        env.update(GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, env=env)


def _repo(tmp_path: Path, stamp: datetime | None, commit_at: datetime,
          author: str = "Contabo MT5 Desk") -> Path:
    repo = tmp_path / "r"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    _git(repo, "config", "user.email", "b@example.com")
    _git(repo, "config", "user.name", author)
    _git(repo, "config", "commit.gpgsign", "false")
    script = repo / "desks/mt5/scripts/sync_shadow_to_git.ps1"
    script.parent.mkdir(parents=True)
    script.write_text(_SCRIPT, "utf-8")
    health = repo / "desks/mt5/reports/shadow/shadow_health.json"
    health.parent.mkdir(parents=True)
    health.write_text(json.dumps({"updated_at": stamp.isoformat() if stamp else None,
                                  "status": "OPERATING"}), "utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "state", date=commit_at.strftime("%Y-%m-%dT%H:%M:%S+0000"))
    return repo


@needs_git
def test_fresh_stamps_pass(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, now - timedelta(hours=1), now), ref="HEAD")
    assert doc["verdict"] == "FRESH", doc


@needs_git
def test_a_recommit_of_old_content_is_still_stale(tmp_path: Path) -> None:
    """The 2026-09-24 re-root: a new commit date over 09-16 content."""
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, now - timedelta(days=14), now), ref="HEAD")
    assert doc["verdict"] == "STALE", doc
    assert doc["basis"] == "stamp_inside_state"
    assert doc["age_h"] > 300


@needs_git
def test_the_threshold_is_six_hours(tmp_path: Path) -> None:
    assert fence.THRESHOLD_H == 6.0
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, now - timedelta(hours=7), now), ref="HEAD")
    assert doc["verdict"] == "STALE"


@needs_git
def test_no_stamp_falls_back_to_the_box_commit_date(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, None, now - timedelta(hours=2)), ref="HEAD")
    assert doc["verdict"] == "FRESH" and doc["basis"] == "box_commit_date"


@needs_git
def test_no_box_evidence_is_unmeasured_and_fails(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    doc = fence.measure(_repo(tmp_path, None, now, author="Someone Else"), ref="HEAD")
    assert doc["verdict"] == "UNMEASURED", doc


def test_it_is_a_state_fence_on_the_box_clock_never_a_push_gate() -> None:
    gate = _load("_quant_run_law_gate_bsf", "scripts/run_law_gate.py")
    assert "check_box_state_freshness.py" in {n for n, _ in gate._STATE_FENCES}
    assert "check_box_state_freshness.py" not in {n for n, _ in gate._LAW_FENCES}, (
        "a red freshness fence in --laws-only would refuse the very push that heals it")


@needs_git
def test_d17_metric_and_the_not_armed_line_reach_the_fence(tmp_path: Path) -> None:
    """CRO D17 reads `box_state_age_hours`; NOT-ARMED rides the published meter to this fence."""
    now = datetime.now(UTC)
    repo = _repo(tmp_path, now - timedelta(hours=1), now)
    script = repo / "desks/mt5/scripts/sync_shadow_to_git.ps1"
    script.write_text(_SCRIPT.replace(
        '"desks/mt5/data/live_ledger.jsonl"',
        '"desks/mt5/data/live_ledger.jsonl",\n    "desks/mt5/reports/BOX_STATE_FLOW.json"'),
        "utf-8")
    flow = repo / "desks/mt5/reports/BOX_STATE_FLOW.json"
    flow.write_text(json.dumps({"verdict": "FLOWING", "alerts": {
        "armed": 0, "kinds": [], "line": "ALERTS NOT ARMED: STALLED pages reach no one"}}),
        "utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "meter")
    doc = fence.measure(repo, ref="HEAD")
    assert doc["verdict"] == "FRESH", doc
    assert doc["box_state_age_hours"] == doc["age_h"]
    assert fence.alerts_line(doc) == "ALERTS NOT ARMED: STALLED pages reach no one"
    assert fence.alerts_line({"alerts": {"armed": 1, "line": None}}) is None
    assert fence.alerts_line({}) is None
