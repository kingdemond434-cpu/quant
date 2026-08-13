"""The law gate reaps the HEAD checkouts its own OOM-killed runs leave behind (R0407, one
producer on).

`full_gate` removes its scratch worktree in a `finally`, which covers every path the interpreter
walks out of and NOT the one that leaks: SIGKILL. These tests pin the three properties that make
the reaper safe to run unattended -- it takes the dead, it leaves the living, and it never raises.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "run_law_gate_under_test", _ROOT / "scripts/run_law_gate.py")
assert _spec and _spec.loader
law_gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = law_gate
_spec.loader.exec_module(law_gate)


@pytest.fixture
def fake_tmp(tmp_path, monkeypatch):
    """A private tempdir, so the test can never reap a real sibling session's scratch."""
    monkeypatch.setattr(law_gate.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


def _checkout(root: Path, name: str, age_s: float) -> Path:
    d = root / name
    (d / "t").mkdir(parents=True)
    (d / "t" / "marker").write_text("x", "utf-8")
    stamp = time.time() - age_s
    import os
    os.utime(d, (stamp, stamp))
    return d


def test_reaps_a_checkout_older_than_any_live_run(fake_tmp):
    """The leak: a run killed before `finally`, its 150MB owned by no process."""
    dead = _checkout(fake_tmp, "lawgate-head-dead", law_gate._ORPHAN_AFTER_S + 60)

    assert law_gate._reap_stale_checkouts(_ROOT) == 1
    assert not dead.exists()


def test_leaves_a_checkout_a_live_run_could_still_be_reading(fake_tmp):
    """The failure that would be WORSE than the leak: deleting a slow sibling's HEAD checkout
    mid-verdict. The threshold is >3x the maximum lifetime precisely so this cannot happen."""
    live = _checkout(fake_tmp, "lawgate-head-live", law_gate._ORPHAN_AFTER_S - 60)

    assert law_gate._reap_stale_checkouts(_ROOT) == 0
    assert (live / "t" / "marker").exists()


def test_leaves_other_producers_scratch_entirely_alone(fake_tmp):
    """It owns ONE prefix. /tmp is shared with the executor, three recorders and several agent
    sessions; a reaper that widened its own scope is the race the fence refuses to run."""
    someone_else = _checkout(fake_tmp, "wt-head", law_gate._ORPHAN_AFTER_S * 10)
    pytest_orphan = _checkout(fake_tmp, "pytest-of-quant", law_gate._ORPHAN_AFTER_S * 10)

    assert law_gate._reap_stale_checkouts(_ROOT) == 0
    assert someone_else.exists()
    assert pytest_orphan.exists()


def test_unreadable_tmp_is_never_the_gates_verdict(fake_tmp, monkeypatch):
    """Best-effort by construction: tidy /tmp is not a precondition for enforcing the laws, so a
    reaper that raised would convert a hygiene problem into a refused push."""
    def boom(*_a, **_k):
        raise OSError("permission denied")

    monkeypatch.setattr(law_gate.Path, "glob", boom)
    assert law_gate._reap_stale_checkouts(_ROOT) == 0
