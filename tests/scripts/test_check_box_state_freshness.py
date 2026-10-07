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
    "desks/mt5/data/RELEASE.json",
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


@needs_git
def test_a_fresh_stamp_written_by_ci_does_not_make_the_box_fresh(tmp_path: Path) -> None:
    """2026-10-06: CI's release seal rewrote RELEASE.json (a published path) with a fresh
    generated_utc, and the fence read the box FRESH while its last own write was 12 days old."""
    now = datetime.now(UTC)
    repo = _repo(tmp_path, now - timedelta(days=12), now - timedelta(days=12))
    rel = repo / "desks/mt5/data/RELEASE.json"
    rel.parent.mkdir(parents=True, exist_ok=True)
    rel.write_text(json.dumps({"generated_utc": now.isoformat()}), "utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=quant-ci", "commit", "-q", "-m", "seal release")
    doc = fence.measure(repo, ref="HEAD")
    assert doc["verdict"] == "STALE", doc
    assert doc["stamps_ignored_not_box_written"] == {"desks/mt5/data/RELEASE.json": "quant-ci"}
    assert doc["age_h"] > 200


@needs_git
def test_a_shallow_clone_names_the_truncation_not_an_absent_box(tmp_path: Path) -> None:
    """Audit should-fix: the box's commit lies below a --depth 1 graft."""
    now = datetime.now(UTC)
    src = _repo(tmp_path, None, now - timedelta(hours=1))
    _git(src, "-c", "user.name=quant-ci", "commit", "-q", "--allow-empty", "-m", "ci on top")
    other = src / "x.json"
    other.write_text("{}", "utf-8")
    _git(src, "add", ".")
    _git(src, "-c", "user.name=quant-ci", "commit", "-q", "-m", "ci touches nothing published")
    health = src / "desks/mt5/reports/shadow/shadow_health.json"
    health.write_text(json.dumps({"status": "OPERATING"}), "utf-8")
    _git(src, "add", ".")
    _git(src, "-c", "user.name=quant-ci", "commit", "-q", "-m", "ci rewrites the stamp-less file")
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", f"file://{src}", str(shallow))
    doc = fence.measure(shallow, ref="HEAD")
    assert doc["shallow"] is True
    assert doc["verdict"] == "UNMEASURED" and doc["why"].startswith("shallow clone"), doc


@needs_git
def test_a_merge_of_box_writes_keeps_box_authorship(tmp_path: Path) -> None:
    """Audit should-fix: a non-TREESAME merge (a conflict resolved by someone else) of two
    box-written sides is still the box's content, not the merger's."""
    now = datetime.now(UTC)
    repo = _repo(tmp_path, now - timedelta(hours=1), now - timedelta(hours=1))
    health = repo / "desks/mt5/reports/shadow/shadow_health.json"
    _git(repo, "checkout", "-q", "-b", "side")
    health.write_text(json.dumps({"updated_at": (now - timedelta(minutes=30)).isoformat(),
                                  "side": 1}), "utf-8")
    _git(repo, "commit", "-qam", "box side")
    _git(repo, "checkout", "-q", "live")
    health.write_text(json.dumps({"updated_at": (now - timedelta(minutes=20)).isoformat(),
                                  "main": 1}), "utf-8")
    _git(repo, "commit", "-qam", "box main")
    subprocess.run(["git", "merge", "-q", "side"], cwd=str(repo), capture_output=True,
                   check=False)
    health.write_text(json.dumps({"updated_at": (now - timedelta(minutes=20)).isoformat(),
                                  "main": 1, "side": 1}), "utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=quant-ci", "commit", "-q", "--no-edit")
    plain = subprocess.run(["git", "log", "-1", "--format=%an", "--",
                            "desks/mt5/reports/shadow/shadow_health.json"], cwd=str(repo),
                           capture_output=True, text=True, check=True).stdout.strip()
    assert plain == "quant-ci", "fixture must put the merger on top"
    doc = fence.measure(repo, ref="HEAD")
    assert doc["verdict"] == "FRESH", doc
    assert doc["stamps_ignored_not_box_written"] == {}


@needs_git
def test_a_merge_with_a_non_box_side_is_not_box_written(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    repo = _repo(tmp_path, now - timedelta(days=3), now - timedelta(days=3))
    health = repo / "desks/mt5/reports/shadow/shadow_health.json"
    _git(repo, "checkout", "-q", "-b", "side")
    health.write_text(json.dumps({"updated_at": now.isoformat(), "side": 1}), "utf-8")
    _git(repo, "-c", "user.name=someone", "commit", "-qam", "not the box")
    _git(repo, "checkout", "-q", "live")
    health.write_text(json.dumps({"updated_at": now.isoformat(), "main": 1}), "utf-8")
    _git(repo, "commit", "-qam", "box main")
    subprocess.run(["git", "merge", "-q", "side"], cwd=str(repo), capture_output=True,
                   check=False)
    health.write_text(json.dumps({"updated_at": now.isoformat(), "both": 1}), "utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=quant-ci", "commit", "-q", "--no-edit")
    doc = fence.measure(repo, ref="HEAD")
    assert "desks/mt5/reports/shadow/shadow_health.json" in doc["stamps_ignored_not_box_written"]


@pytest.mark.parametrize(("name", "ok"), [
    ("Contabo MT5 Desk", True), ("contabo", True), ("CONTABO box", True),
    ("Contabot", False), ("ex-Contabo", False), ("Not Contabo", False), ("", False),
])
def test_one_box_identity_predicate(name: str, ok: bool) -> None:
    """Audit should-fix: the commit search and the per-file check use the SAME predicate."""
    assert fence.is_box(name) is ok
    src = (ROOT / "scripts/check_box_state_freshness.py").read_text("utf-8")
    assert "--author=" not in src and ".lower() not in" not in src


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
