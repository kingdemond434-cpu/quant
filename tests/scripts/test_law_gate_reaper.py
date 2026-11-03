"""The law gate reaps the HEAD checkouts its own OOM-killed runs leave behind (R0407, one
producer on).

`full_gate` removes its scratch worktree in a `finally`, which covers every path the interpreter
walks out of and NOT the one that leaks: SIGKILL. These tests pin the three properties that make
the reaper safe to run unattended -- it takes the dead, it leaves the living, and it never raises.
"""
from __future__ import annotations

import importlib.util
import os
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
    monkeypatch.setattr(law_gate, "_checkout_base", lambda: tmp_path)
    # The producer now sweeps both bases and prunes Git registrations. Keep both
    # filesystem and Git maintenance inside this fixture's own repository.
    repo = tmp_path / "repo"
    repo.mkdir()
    law_gate.subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.setattr(sys.modules[__name__], "_ROOT", repo)
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


def test_leaves_a_checkout_a_live_run_could_still_be_reading(fake_tmp, monkeypatch):
    """The failure that would be WORSE than the leak: deleting a slow sibling's HEAD checkout
    mid-verdict. The threshold is >3x the maximum lifetime precisely so this cannot happen."""
    live = _checkout(fake_tmp, "lawgate-head-live", law_gate._ORPHAN_AFTER_S - 60)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: {str(live / "t")})

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


# ---------------------------------------------------------------------------------------------
# THE CHECKOUT BELONGS ON DISK (gap-fixer 2026-08-29). The reaper above treats the symptom: it
# knows the checkout lands on a tmpfs and answers by deleting it after two hours. Measured this
# cycle the checkout is 297MB -- DOUBLE the 150MB its docstring cites -- on a 3815MB box with
# zero swap, so one law gate on a dirty tree claims ~50% of typical free RAM for its whole run,
# and no reaper can help while that run is legitimately alive.
# ---------------------------------------------------------------------------------------------


def test_checkout_base_is_not_ram_on_this_box():
    """The property, measured against the real host: wherever the checkout lands, not a tmpfs."""
    base = law_gate._checkout_base()
    assert not law_gate._is_tmpfs(base), f"{base} is RAM -- the 297MB checkout goes back in RAM"


def test_unknown_filesystem_never_reads_as_tmpfs(monkeypatch):
    """Unknown must not read as tmpfs: a wrong True relocates onto a path a host may not have,
    and this gate's verdict must never depend on where its scratch landed."""
    monkeypatch.setattr(law_gate.Path, "read_text",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no /proc")))
    assert law_gate._is_tmpfs(Path("/anything")) is False


def test_a_tmpfs_cache_dir_falls_back_to_tempdir(monkeypatch, tmp_path):
    """If ~/.cache is ITSELF in RAM there is no disk to prefer, and the fallback is exactly
    today's behaviour -- so this change can only improve, never regress."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(law_gate, "_is_tmpfs", lambda p: True)
    assert law_gate._checkout_base() == Path(law_gate.tempfile.gettempdir())


def test_reaper_still_sweeps_the_old_tmp_base(monkeypatch, tmp_path):
    """THE STRANDING BUG THIS AVOIDS. The gate re-execs HEAD's copy of itself, so an older HEAD
    still allocates under gettempdir(), and every orphan predating the move lives there. A
    reaper that swept only the new base would strand the exact pile the move exists to stop."""
    old_base, new_base = tmp_path / "tmp", tmp_path / "cache"
    old_base.mkdir()
    new_base.mkdir()
    stale = old_base / "lawgate-head-stranded"
    stale.mkdir()
    os.utime(stale, (0, 0))
    monkeypatch.setattr(law_gate.tempfile, "gettempdir", lambda: str(old_base))
    monkeypatch.setattr(law_gate, "_checkout_base", lambda: new_base)
    assert law_gate._reap_stale_checkouts(tmp_path) == 1
    assert not stale.exists(), "an orphan in the OLD base was stranded by the relocation"


def test_reaps_an_unheld_checkout_long_before_two_hours(fake_tmp, monkeypatch):
    """2026-11-03: 12 GB of killed pushes' checkouts filled the disk inside one hour."""
    dead = _checkout(fake_tmp, "lawgate-head-killed", law_gate._UNHELD_AFTER_S + 60)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: {"/somewhere/else"})

    assert law_gate._reap_stale_checkouts(_ROOT) == 1
    assert not dead.exists()


def test_a_fresh_unheld_checkout_is_left_for_its_starting_run(fake_tmp, monkeypatch):
    """A run that has made its directory but not yet entered it holds nothing for a moment."""
    young = _checkout(fake_tmp, "lawgate-head-young", law_gate._UNHELD_AFTER_S - 60)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: set())

    assert law_gate._reap_stale_checkouts(_ROOT) == 0
    assert young.exists()


def test_a_blind_process_census_falls_back_to_the_age_rule(fake_tmp, monkeypatch):
    """No /proc is UNMEASURED, never "nobody holds it"."""
    mid = _checkout(fake_tmp, "lawgate-head-mid", law_gate._UNHELD_AFTER_S + 60)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: None)

    assert law_gate._reap_stale_checkouts(_ROOT) == 0
    assert mid.exists()


def test_the_census_sees_this_process(tmp_path):
    held = law_gate._held_paths()
    if held is None:
        pytest.skip("no readable /proc on this host")
    assert os.getcwd() in held


def _with_owner(d: Path, pid: int, age_s: float) -> Path:
    (d / law_gate._OWNER_PID).write_text(str(pid))
    stamp = time.time() - age_s
    os.utime(d, (stamp, stamp))
    return d


def test_a_live_owner_keeps_an_unheld_checkout(fake_tmp, monkeypatch):
    """Auditor 11-03: a live gate using its checkout only through short git/pytest children
    holds no cwd or fd there between steps; its pid file must keep a concurrent gate off it."""
    age = law_gate._UNHELD_AFTER_S + 60
    live = _with_owner(_checkout(fake_tmp, "lawgate-head-live", age), os.getpid(), age)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: {"/somewhere/else"})

    assert law_gate._reap_stale_checkouts(_ROOT) == 0
    assert live.exists()


def test_a_dead_owner_does_not_keep_an_unheld_checkout(fake_tmp, monkeypatch):
    import subprocess
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    age = law_gate._UNHELD_AFTER_S + 60
    dead = _with_owner(_checkout(fake_tmp, "lawgate-head-dead", age), child.pid, age)
    monkeypatch.setattr(law_gate, "_held_paths", lambda: {"/somewhere/else"})

    assert law_gate._reap_stale_checkouts(_ROOT) == 1
    assert not dead.exists()


def test_a_garbled_pid_file_says_nothing(tmp_path):
    (tmp_path / law_gate._OWNER_PID).write_text("not-a-pid")
    assert law_gate._owner_alive(tmp_path) is False
    assert law_gate._owner_alive(tmp_path / "absent") is False
