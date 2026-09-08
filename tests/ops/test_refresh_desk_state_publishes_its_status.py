"""The VPS's three-minute merge of the desk branch publishes its own status (L0292).

MEASURED 2026-09-08: ops/refresh_desk_state.sh had aborted on the same three conflicts every
three minutes since 2026-09-06 17:08 -- roughly 960 times -- and the only record was a log line
on the VPS. Both machines kept committing; each believed it was deploying the other's work. A
merge that aborts silently is indistinguishable from one that succeeds, so the script now writes
web/refresh_status.json on every tick, and it names the conflicting paths BEFORE `git merge
--abort` erases them. These tests pin that artifact and run the status writer itself.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "refresh_desk_state.sh"
SRC = SCRIPT.read_text("utf-8")


def test_the_script_parses() -> None:
    if not Path("/bin/bash").exists():
        pytest.skip("no bash")
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_every_tick_writes_the_status_artifact() -> None:
    assert 'STATUS="web/refresh_status.json"' in SRC
    assert "last_in_step_at" in SRC and "consecutive_conflicts" in SRC


def test_conflicting_paths_are_captured_before_the_abort() -> None:
    """After `git merge --abort` nothing on disk says what collided."""
    capture = SRC.index("git diff --name-only --diff-filter=U")
    abort = SRC.index("git merge --abort")
    assert capture < abort, "the conflict paths must be read before the abort erases them"


def _writer() -> str:
    """The embedded python status writer, extracted from the heredoc."""
    m = re.search(r"python3 - <<'PY'.*?\n(.*?)\nPY\n", SRC, re.S)
    assert m, "status writer heredoc not found"
    return m.group(1)


def _run_writer(tmp_path: Path, **env: str) -> dict:
    status = tmp_path / "web" / "refresh_status.json"
    base = {"REFRESH_BRANCH": "b", "REFRESH_FETCH_OK": "1", "REFRESH_BEHIND": "0",
            "REFRESH_MERGED": "0", "REFRESH_CONFLICT": "0", "REFRESH_CONFLICT_PATHS": "",
            "REFRESH_MERGE_TAIL": "", "REFRESH_HEAD_BEFORE": "aaaa", "REFRESH_FETCH_HEAD": "bbbb",
            "REFRESH_HEAD_AFTER": "aaaa", "REFRESH_STATUS": str(status)}
    base.update(env)
    subprocess.run([sys.executable, "-"], input=_writer(), text=True, check=True,
                   env={**os.environ, **base}, cwd=tmp_path)
    return json.loads(status.read_text("utf-8"))


def test_a_conflict_is_recorded_with_its_paths_and_streak(tmp_path: Path) -> None:
    one = _run_writer(tmp_path, REFRESH_CONFLICT="1", REFRESH_BEHIND="147",
                      REFRESH_CONFLICT_PATHS="desks/mt5/data/universe/universe.json "
                                             "desks/mt5/research/hourly_cycle.py")
    assert one["conflict"] is True and one["behind_before"] == 147
    assert one["conflict_paths"] == ["desks/mt5/data/universe/universe.json",
                                     "desks/mt5/research/hourly_cycle.py"]
    assert one["consecutive_conflicts"] == 1 and one["first_conflict_at"]
    assert one["last_in_step_at"] is None
    assert "DIVERGED" in one["note"]
    two = _run_writer(tmp_path, REFRESH_CONFLICT="1", REFRESH_BEHIND="148",
                      REFRESH_CONFLICT_PATHS="x")
    assert two["consecutive_conflicts"] == 2
    assert two["first_conflict_at"] == one["first_conflict_at"], "the streak keeps its start"


def test_being_in_step_clears_the_streak_and_stamps_the_time(tmp_path: Path) -> None:
    _run_writer(tmp_path, REFRESH_CONFLICT="1", REFRESH_BEHIND="3", REFRESH_CONFLICT_PATHS="x")
    ok = _run_writer(tmp_path, REFRESH_MERGED="1", REFRESH_BEHIND="3")
    assert ok["consecutive_conflicts"] == 0 and ok["first_conflict_at"] is None
    assert ok["last_in_step_at"] == ok["at"]
    same = _run_writer(tmp_path)                       # nothing to merge: also in step
    assert same["last_in_step_at"] == same["at"] and same["note"] == "in step with origin"


def test_a_failed_fetch_keeps_the_last_in_step_time(tmp_path: Path) -> None:
    ok = _run_writer(tmp_path)
    down = _run_writer(tmp_path, REFRESH_FETCH_OK="0")
    assert down["fetch_ok"] is False and down["last_in_step_at"] == ok["last_in_step_at"]
    assert down["consecutive_conflicts"] == 0
