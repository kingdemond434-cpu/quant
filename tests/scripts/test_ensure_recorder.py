"""ensure_recorder (R0282): hang detection for all three recorders, without double-spawns.

The failure modes pinned here are the ones that motivated the rewrite: a hung-but-alive
recorder used to get a second copy spawned beside it (futures) or nothing at all (spot/bybit,
whose cron guards see only death); and a raw pgrep -f match can catch the cron guard's SHELL
line on the shared */10 tick, so the terminator must verify /proc cmdline before killing.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.ensure_recorder as ER  # noqa: E402


def test_pids_keeps_the_interpreter_and_filters_the_guard_shell() -> None:
    """A real python running the script matches; a shell whose -c string merely CONTAINS the
    pattern (the cron guard's respawn half) must not -- killing the guard eats a respawn."""
    dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)",
                              "scripts/run_recorder_spot.py"])
    decoy = subprocess.Popen(["/bin/sh", "-c",
                              "sleep 20 # python scripts/run_recorder_spot.py"])
    try:
        time.sleep(0.3)
        pids = ER._pids(r"python.*run_recorder_spot\.py", "scripts/run_recorder_spot.py")
        assert dummy.pid in pids, "the real interpreter+script process must match"
        assert decoy.pid not in pids, "a shell containing the strings in one token must not"
    finally:
        dummy.kill()
        decoy.kill()
        dummy.wait()
        decoy.wait()


def _drive(monkeypatch, tmp_path, *, pids, hb_age_s, we_spawn):
    """Run main() over a single synthetic recorder; record terminate/spawn calls."""
    calls = {"terminated": [], "spawned": []}
    hb = tmp_path / "hb"
    if hb_age_s is not None:
        hb.write_text("x")
        t = time.time() - hb_age_s
        import os
        os.utime(hb, (t, t))
    monkeypatch.setattr(ER, "_RECORDERS", {
        "x": (r"python.*x\.py", hb, "scripts/x.py", we_spawn, tmp_path / "log")})
    monkeypatch.setattr(ER, "_pids", lambda pattern, script: list(pids))
    monkeypatch.setattr(ER, "_terminate", lambda p, grace_s=20.0: calls["terminated"].extend(p))
    monkeypatch.setattr(ER, "_spawn", lambda s, log: calls["spawned"].append(s))
    ER.main()
    return calls


def test_alive_and_fresh_is_untouched(monkeypatch, tmp_path) -> None:
    c = _drive(monkeypatch, tmp_path, pids=[111], hb_age_s=30, we_spawn=True)
    assert c == {"terminated": [], "spawned": []}


def test_hung_futures_is_terminated_before_respawn_not_doubled(monkeypatch, tmp_path) -> None:
    c = _drive(monkeypatch, tmp_path, pids=[111], hb_age_s=3600, we_spawn=True)
    assert c["terminated"] == [111], "the hung process must die first"
    assert c["spawned"] == ["scripts/x.py"], "then the replacement spawns"


def test_hung_cron_guarded_recorder_is_terminated_but_not_spawned_here(monkeypatch,
                                                                       tmp_path) -> None:
    c = _drive(monkeypatch, tmp_path, pids=[222], hb_age_s=3600, we_spawn=False)
    assert c["terminated"] == [222]
    assert c["spawned"] == [], "two spawners for one process is a double-recorder race"


def test_dead_cron_guarded_recorder_is_left_to_its_guard(monkeypatch, tmp_path) -> None:
    c = _drive(monkeypatch, tmp_path, pids=[], hb_age_s=None, we_spawn=False)
    assert c == {"terminated": [], "spawned": []}


def test_dead_futures_is_respawned(monkeypatch, tmp_path) -> None:
    c = _drive(monkeypatch, tmp_path, pids=[], hb_age_s=None, we_spawn=True)
    assert c["terminated"] == []
    assert c["spawned"] == ["scripts/x.py"]


def test_absent_heartbeat_with_live_process_reads_as_hung(monkeypatch, tmp_path) -> None:
    """A recorder that never wrote its heartbeat is indistinguishable from one that hung
    immediately -- both are archiving nothing behind a live process."""
    c = _drive(monkeypatch, tmp_path, pids=[333], hb_age_s=None, we_spawn=False)
    assert c["terminated"] == [333]
