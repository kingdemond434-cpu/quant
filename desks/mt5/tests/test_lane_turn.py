"""Turn-taking on certification_lane: a waiting certifier gets the lane at the judge's next sweep
boundary; a dead, stale or foreign waiter never parks the judge."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import lane_turn  # noqa: E402


def _write(root: Path, **over) -> None:
    doc = {"pid": os.getpid(), "host": socket.gethostname(), "who": "qquant_gates",
           "since": time.time()}
    doc.update(over)
    lane_turn.waiter_path(root=root).write_text(json.dumps(doc), encoding="utf-8")


def test_announce_then_clear_round_trips(tmp_path):
    lane_turn.announce("qquant_gates", root=tmp_path)
    assert lane_turn.waiting(root=tmp_path)["who"] == "qquant_gates"
    lane_turn.clear(root=tmp_path)
    assert lane_turn.waiting(root=tmp_path) is None


def test_clear_never_removes_a_successors_record(tmp_path):
    _write(tmp_path, pid=os.getpid() + 1)
    lane_turn.clear(root=tmp_path)
    assert lane_turn.waiter_path(root=tmp_path).exists()


def test_stale_foreign_or_malformed_waiters_are_ignored(tmp_path):
    _write(tmp_path, since=time.time() - lane_turn.WAITER_FRESH_S - 1)
    assert lane_turn.waiting(root=tmp_path) is None
    _write(tmp_path, host="another-box")
    assert lane_turn.waiting(root=tmp_path) is None
    lane_turn.waiter_path(root=tmp_path).write_text("{not json", encoding="utf-8")
    assert lane_turn.waiting(root=tmp_path) is None
    assert lane_turn.yield_to_waiter(root=tmp_path, sleep=lambda s: None) is None


def test_judge_holds_off_until_the_waiter_takes_its_turn(tmp_path):
    _write(tmp_path)
    t = [0.0]
    naps = []

    def sleep(s):
        naps.append(s)
        t[0] += s
        if len(naps) == 3:                         # the certifier got the lane and finished
            lane_turn.waiter_path(root=tmp_path).unlink()

    out = lane_turn.yield_to_waiter(root=tmp_path, sleep=sleep, clock=lambda: t[0], poll_s=10)
    assert out["outcome"] == "TOOK_TURN" and out["held_s"] == 30.0 and len(naps) == 3


def test_the_hold_is_bounded(tmp_path):
    _write(tmp_path)
    t = [0.0]

    def sleep(s):
        t[0] += s

    out = lane_turn.yield_to_waiter(root=tmp_path, sleep=sleep, clock=lambda: t[0],
                                    max_s=60, poll_s=10)
    assert out["outcome"] == "TIMED_OUT" and out["held_s"] == 60.0


def test_budgets_fit_the_hourly_trigger_and_outlive_the_waiter():
    assert lane_turn.CERT_WAIT_S < 60 * 60
    assert lane_turn.WAITER_FRESH_S > lane_turn.CERT_WAIT_S
    assert lane_turn.YIELD_MAX_S <= lane_turn.CERT_WAIT_S


def test_both_ends_are_wired():
    launcher = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    resident = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    assert "lane_turn.announce(" in launcher and "lane_turn.clear()" in launcher
    loop = resident[resident.index("def _resident_loop("):]
    assert loop.index("_yield_to_certifier(") < loop.index('status="SWEEPING"')


def test_resident_loop_yields_before_its_next_sweep(tmp_path, monkeypatch):
    sys.path.insert(0, str(DESK / "scripts"))
    import run_sharded_gauntlet as rsg

    monkeypatch.setattr(lane_turn, "_root", lambda: tmp_path)
    monkeypatch.setattr(rsg, "_write_state", lambda state: None)
    monkeypatch.setattr(rsg, "resident_stop", lambda *a, **k: {})
    _write(tmp_path)
    t = [0.0]
    order = []

    def sleep(s):
        order.append("nap")
        t[0] += s
        lane_turn.waiter_path(root=tmp_path).unlink(missing_ok=True)

    def sweep():
        order.append("sweep")
        return 0

    state = {"sweeps": 0, "failures": 0, "lane_held": 0, "hung_kills": 0, "busy_seconds": 0.0}
    rsg._resident_loop(state, sweep, sleep, lambda: t[0], 0.0, None, 1)
    assert order == ["nap", "sweep"]
    assert state["certifier_turns"] == 1 and state["last_certifier_turn"]["outcome"] == "TOOK_TURN"


def test_deferral_is_never_silent_past_the_contract(tmp_path):
    out = tmp_path / "CERTIFIER_LANE.json"
    rcs = [lane_turn.record_outcome("DEFERRED", path=out) for _ in range(lane_turn.STARVED_STREAK)]
    assert rcs[:-1] == [0] * (lane_turn.STARVED_STREAK - 1)
    assert rcs[-1] == lane_turn.STARVED_RC
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "STARVED" and doc["deferred_streak"] == lane_turn.STARVED_STREAK
    assert lane_turn.record_outcome("RAN", rc=0, path=out) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "OK" and doc["deferred_streak"] == 0 and doc["last_ran_utc"]
    assert lane_turn.record_outcome("RAN", rc=3, path=out) == 3


def test_the_lane_lock_beats_only_on_measured_progress():
    resident = (DESK / "scripts" / "run_sharded_gauntlet.py").read_text("utf-8")
    tick = resident[resident.index("    def tick(self)"):]
    tick = tick[:tick.index("\n    def ", 10)]
    assert "_beat_sweep_locks()" in tick
    assert "self.progress.measured and self._idle <=" in tick
