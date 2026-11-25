"""The delivery guard (zuck 2026-11-25 20:00Z, rule E34): every CLEAR live in 1h, not 24h behind."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import delivery_guard as dg

NOW = datetime(2026, 11, 25, 20, 0, tzinfo=UTC)


def _v(d: Path, name: str, verdict: str, sha: str, branch: str, at: datetime) -> None:
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{name}.json"
    f.write_text(json.dumps({"branch": branch, "line": f"AUDIT {verdict} {sha} merge"}),
                 encoding="utf-8")
    os.utime(f, (at.timestamp(), at.timestamp()))


def test_oldest_copy_wins_and_only_the_newest_verdict_per_branch_is_owed(tmp_path):
    a, b, c = "a" * 40, "b" * 40, "c" * 40
    _v(tmp_path / "x", "p1", "CLEAR", a, "claude/p", NOW - timedelta(hours=5))
    _v(tmp_path / "y", "p1", "CLEAR", a, "claude/p", NOW - timedelta(hours=9))
    _v(tmp_path / "x", "p2", "CLEAR", b, "claude/p", NOW - timedelta(hours=2))  # supersedes a
    _v(tmp_path / "x", "q1", "CLEAR", c, "claude/q", NOW - timedelta(hours=3))
    _v(tmp_path / "x", "q2", "HOLD", c, "claude/q", NOW - timedelta(hours=1))   # q owes nothing
    (tmp_path / "x" / "junk.json").write_text("nope", encoding="utf-8")
    rows = dg.read_verdicts([tmp_path / "x", tmp_path / "y", tmp_path / "missing"])
    assert next(r for r in rows if r["sha"] == a)["at"] == NOW - timedelta(hours=9)
    assert [o["sha"] for o in dg.owed(rows)] == [b]


def _c(sha, h):
    return {"sha": sha, "branch": f"claude/{sha[0]}", "at": NOW - timedelta(hours=h)}


def test_assess_breaches():
    live = {"a" * 40}
    clears = [_c("a" * 40, 30), _c("b" * 40, 0.5)]
    r = dg.assess(clears, has=lambda s: True, live=lambda s: s in live, now=NOW)
    assert r["breach"] == [] and r["pending_n"] == 1 and r["behind_newest_clear_h"] == 0.5
    clears.append(_c("c" * 40, 2))
    r = dg.assess(clears, has=lambda s: s != "c" * 40, live=lambda s: s in live, now=NOW)
    assert "CLEAR_NOT_LIVE_1H" in r["breach"] and r["pending"][0]["object_on_box"] is False
    old = [_c("d" * 40, 30), _c("e" * 40, 0.2)]
    r = dg.assess(old, has=lambda s: True, live=lambda s: False, now=NOW)
    assert r["breach"] == ["CLEAR_NOT_LIVE_1H", "LIVE_24H_BEHIND"]
    assert dg.assess([], has=bool, live=bool, now=NOW)["breach"] == []


def test_repairs_start_only_stopped_tasks_and_not_too_often():
    state = {"started": {"QuantForge-Loop": (NOW - timedelta(minutes=5)).isoformat()}}
    run = {"MT5-AdoptRelease": False, "QuantForge-Loop": False}
    assert dg.repairs(["CLEAR_NOT_LIVE_1H"], state, NOW, running=run.get) == ["MT5-AdoptRelease"]
    assert dg.repairs([], state, NOW, running=run.get) == []
    assert dg.repairs(["X"], {}, NOW, running=lambda t: None) == []  # unknown state: hands off


def _git(root: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True,
                          text=True).stdout.strip()


def test_run_once_end_to_end(tmp_path):
    repo, qb = tmp_path / "repo", tmp_path / "qb"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "one")
    live = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
    owed = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-")
    _v(qb / "inbox" / "verdicts" / "done", "l", "CLEAR", live, "claude/l",
       NOW - timedelta(hours=40))
    _v(qb / "inbox" / "verdicts", "o", "CLEAR", owed, "claude/o", NOW - timedelta(hours=30))
    pages, started = [], []
    doc = dg.run_once(repo, quantbox=qb, now=NOW, running=lambda t: False,
                      start=lambda t: started.append(t) or True, page=pages.append)
    assert doc["pending_n"] == 1 and doc["pending"][0]["sha"] == owed
    assert doc["breach"] == ["CLEAR_NOT_LIVE_1H", "LIVE_24H_BEHIND"]
    assert started == list(dg.REPAIR_TASKS) and len(pages) == 1
    assert doc["drop_connected"] is False
    assert json.loads((repo / dg.REPORT_REL).read_text(encoding="utf-8"))["pending_n"] == 1
    # same shape 15 min later: no second page, no second start inside 30 min
    doc = dg.run_once(repo, quantbox=qb, now=NOW + timedelta(minutes=15), running=lambda t: False,
                      start=lambda t: started.append(t) or True, page=pages.append)
    assert len(pages) == 1 and len(started) == 2
    # 7h later it pages again
    dg.run_once(repo, quantbox=qb, now=NOW + timedelta(hours=7), running=lambda t: True,
                start=lambda t: True, page=pages.append)
    assert len(pages) == 2


def test_the_guardian_runs_it():
    src = (Path(__file__).resolve().parents[2] / "ops" / "run_guardian.cmd").read_text()
    assert "scripts\\delivery_guard.py\" --once" in src
