"""The box's state flow must be MEASURED ON ORIGIN, and a stall must be loud.

MEASURED 2026-09-30 from git alone: the last "mt5 shadow state sync" commit is 2026-09-12 13:04
+0200, every box state file since stops on 2026-09-16, and nothing on the box said so for two
weeks -- MT5-ShadowSync kept running, which is not the same as delivering. These pin the meter
that now says so: FLOWING, STALLED (fresh here, stale on origin), SOURCE_STALE (quiet producers),
UNMEASURED (never a clean verdict from absence), plus the artifact and the event.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import state_publication as sp

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = '''$relPaths = @(
    "desks/mt5/reports/shadow/shadow_health.json",   # a comment with "not/a/path" in it
    "desks/mt5/data/gateway_state.json"
)
$reportPaths = @(
    "desks/mt5/reports/JUDGING_RATE.json"
)
'''


def test_the_parser_reads_both_lists_and_ignores_comments() -> None:
    assert sp.parse_published(_SCRIPT) == [
        "desks/mt5/reports/shadow/shadow_health.json",
        "desks/mt5/data/gateway_state.json",
        "desks/mt5/reports/JUDGING_RATE.json"]


def test_the_real_publisher_carries_the_digest_and_the_meter() -> None:
    listed = sp.published_paths(ROOT)
    assert len(listed) >= 10, f"parsed only {listed} from the real sync script"
    for rel in ("desks/mt5/reports/GATE_VERDICT_DIGEST.json", sp.FLOW_REL):
        assert rel in listed, f"{rel} is not published, so no reader off the box ever sees it"


def _git(cwd: Path, *args: str, date: str | None = None) -> str:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    if date:
        env.update(GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True, env=env).stdout.strip()


def _box(tmp_path: Path, published_hours_ago: float) -> Path:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(bare))
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", str(bare), str(box))
    for k, v in (("user.email", "box@example.com"), ("user.name", "Contabo MT5 Desk (new)"),
                 ("commit.gpgsign", "false"), ("core.hooksPath", "ops/githooks")):
        _git(box, "config", k, v)
    _git(box, "checkout", "-q", "-b", "live")
    script = box / sp.SYNC_REL
    script.parent.mkdir(parents=True)
    script.write_text(_SCRIPT, "utf-8")
    state = box / "desks/mt5/data/gateway_state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}\n", "utf-8")
    _git(box, "add", sp.SYNC_REL, "desks/mt5/data/gateway_state.json")
    when = (datetime.now(UTC) - timedelta(hours=published_hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S+0000")
    _git(box, "commit", "-q", "-m", "mt5 shadow state sync", date=when)
    _git(box, "push", "-q", "origin", "live")
    _git(box, "fetch", "-q", "origin")
    return box


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@needs_git
def test_fresh_on_origin_is_flowing(tmp_path: Path) -> None:
    doc = sp.measure_flow(_box(tmp_path, 0.5))
    assert doc["verdict"] == "FLOWING", doc
    assert doc["local_commits_not_on_origin"] == 0


@needs_git
def test_fresh_here_and_stale_on_origin_is_a_stall(tmp_path: Path) -> None:
    """The 2026-09-12 shape: the box commits and computes, origin never hears of it."""
    box = _box(tmp_path, 40.0)
    state = box / "desks/mt5/data/gateway_state.json"
    state.write_text('{"placed": 1}\n', "utf-8")
    _git(box, "add", "desks/mt5/data/gateway_state.json")
    _git(box, "commit", "-q", "-m", "mt5 shadow state sync (never pushed)")
    doc = sp.measure_flow(box)
    assert doc["verdict"] == "STALLED", doc
    assert doc["local_commits_not_on_origin"] == 1
    assert doc["published_age_h"] > 39
    assert doc["hooks_path"] == "ops/githooks", "the evidence for cause 1 is not recorded"
    assert "delivery is broken" in doc["why"]


@needs_git
def test_quiet_producers_are_not_called_a_delivery_stall(tmp_path: Path) -> None:
    box = _box(tmp_path, 40.0)
    old = time.time() - 30 * 3600
    os.utime(box / "desks/mt5/data/gateway_state.json", (old, old))
    assert sp.measure_flow(box)["verdict"] == "SOURCE_STALE"


@needs_git
def test_no_origin_ref_is_unmeasured_never_flowing(tmp_path: Path) -> None:
    repo = tmp_path / "solo"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    (repo / sp.SYNC_REL).parent.mkdir(parents=True)
    (repo / sp.SYNC_REL).write_text(_SCRIPT, "utf-8")
    doc = sp.measure_flow(repo)
    assert doc["verdict"] == "UNMEASURED", doc


@needs_git
def test_a_stall_writes_the_artifact_and_raises_the_event(tmp_path: Path) -> None:
    box = _box(tmp_path, 40.0)
    (box / "desks/mt5/data/gateway_state.json").write_text('{"x": 2}\n', "utf-8")
    events = tmp_path / "events.jsonl"
    doc = sp.publish_flow(box, events_path=events)
    assert doc["verdict"] == "STALLED"
    written = json.loads((box / sp.FLOW_REL).read_text("utf-8"))
    assert written["verdict"] == "STALLED"
    rows = [json.loads(ln) for ln in events.read_text("utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["STATE_FLOW_STALLED"]
    assert not rows[0].get("unknown_kind"), "STATE_FLOW_STALLED is not in the event vocabulary"


def test_a_meter_that_throws_still_writes_unmeasured(tmp_path: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("git vanished")
    monkeypatch.setattr(sp, "measure_flow", boom)
    doc = sp.publish_flow(tmp_path)
    assert doc["verdict"] == "UNMEASURED"
    assert json.loads((tmp_path / sp.FLOW_REL).read_text("utf-8"))["verdict"] == "UNMEASURED"


def test_stall_watch_and_the_health_board_read_the_verdict() -> None:
    sw = (ROOT / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8", errors="ignore")
    assert "BOX_STATE_FLOW.json" in sw and "STATE FLOW STALLED" in sw
    hb = (ROOT / "desks/mt5/scripts/check_desk_health.py").read_text("utf-8")
    assert "def check_state_flow" in hb and "check_state_flow()" in hb


def test_publish_state_runs_the_digest_and_the_meter() -> None:
    src = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    body = src[src.index("def publish_state"):src.index("def _tape_main")]
    assert body.index("_gate_verdict_digest()") < body.index("subprocess.run(")
    assert "_state_flow()" in body
