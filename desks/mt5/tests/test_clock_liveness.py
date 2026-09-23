"""A PLANTED FROZEN CLOCK IS DETECTED, REPAIRED, AND FAILS THE FENCE WHILE IT STAYS FROZEN.

The organ's whole claim is that a clock which stops accruing cannot hide, so the test plants
exactly the failure the box was measured to have -- a ledger row reading ACTIVE whose identity
is no longer on the engine's roster -- and asserts the three things that must follow: the census
calls it FROZEN with the right cause, the repair fires and the fence is RED while it stands.

Sessions are the other half: the same clock, stopped for the same wall-clock hours but over a
venue weekend, must read DORMANT_BY_SESSION rather than FROZEN, or the organ would cry freeze
every Saturday and be switched off by Monday.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_clock_liveness as fence  # noqa: E402
import clock_liveness as cl  # noqa: E402


# ------------------------------------------------------------------------------- fixtures
@pytest.fixture
def lane(tmp_path, monkeypatch):
    """A one-lane desk on tmp_path: `main`, hourly, symbol-prefixed keys."""
    shadow = tmp_path / "reports" / "shadow"
    shadow.mkdir(parents=True)
    monkeypatch.setattr(cl, "SHADOW_DIR", shadow)
    monkeypatch.setattr(cl, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(cl, "CONSTRAINTS", tmp_path / "market_constraints.json")
    (tmp_path / "universe.json").write_text(json.dumps(
        {"EURUSD": {"asset_class": "forex"}, "XAUUSD": {"asset_class": "metals"}}),
        encoding="utf-8")
    ln = cl.Lane("main", "shadow_state.json", "shadow_forward", "MT5-Shadow (hourly)", 3600,
                 symbol_prefixed=True)
    monkeypatch.setattr(cl, "LANES", (ln,))
    monkeypatch.setattr(cl, "LANE_BY_NAME", {"main": ln})
    monkeypatch.setattr(cl, "scheduled_tasks", lambda: {"MT5-Shadow": {"state": "Enabled"}})
    return ln


def _write(ln, rows):
    ln.path.write_text(json.dumps(rows, default=str), encoding="utf-8")


def _census(roster, now, host="trading_box"):
    return cl.census(cl.SessionCalendar(), roster, now, {"MT5-Shadow": {"state": "Enabled"}},
                     host=host, host_why="test")


def _wednesday(hour: int = 12) -> datetime:
    """2026-09-23 is a Wednesday: a full Fusion trading day for every instrument class."""
    return datetime(2026, 9, 23, hour, 0, tzinfo=UTC)


# --------------------------------------------------------------------------------- the tests
def test_planted_frozen_clock_is_detected_with_its_cause(lane):
    now = _wednesday()
    _write(lane, {"EURUSD.carry.continuous": {
        "status": "ACTIVE", "n": 7,
        "last_attempt_at": (now - timedelta(days=3)).isoformat()}})
    rows = _census(set(), now)          # an EMPTY roster: the engine no longer visits the key
    assert len(rows) == 1
    row = rows[0]
    assert row["verdict"] == cl.FROZEN, row
    assert row["cause"] == "off_roster", row
    assert row["expected_bars"] > row["freeze_bars"] > 0
    assert row["actual_bars"] == 0
    assert row["organ"] == "shadow_forward"


def test_an_accruing_clock_is_not_frozen(lane):
    now = _wednesday()
    _write(lane, {"EURUSD.carry.continuous": {
        "status": "ACTIVE", "last_attempt_at": (now - timedelta(minutes=30)).isoformat()}})
    assert _census({"EURUSD.carry.continuous"}, now)[0]["verdict"] == cl.ACCRUING


def test_a_weekend_gap_is_dormant_by_session_and_never_frozen(lane):
    """Sunday 12:00 UTC, last advance Saturday: the venue was shut, so nothing is late."""
    sunday = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    _write(lane, {"XAUUSD.asia": {
        "status": "ACTIVE",
        "last_attempt_at": datetime(2026, 9, 19, 12, 0, tzinfo=UTC).isoformat()}})
    row = _census({"XAUUSD.asia"}, sunday)[0]
    assert row["verdict"] == cl.DORMANT, row
    assert row["expected_bars"] == 0, row


def test_a_terminal_row_is_retired_not_frozen(lane):
    now = _wednesday()
    _write(lane, {"EURUSD.carry.continuous": {
        "status": "RETIRED_ORPHAN",
        "last_attempt_at": (now - timedelta(days=30)).isoformat()}})
    row = _census(set(), now)[0]
    assert row["verdict"] == cl.RETIRED
    assert row["expected_bars"] == 0


def test_off_the_trading_box_every_clock_is_unmeasured_never_frozen(lane):
    now = _wednesday()
    _write(lane, {"EURUSD.carry.continuous": {
        "status": "ACTIVE", "last_attempt_at": (now - timedelta(days=9)).isoformat()}})
    row = _census(set(), now, host="build_box")[0]
    assert row["verdict"] == cl.UNMEASURED
    assert "not a freeze" in row["why"]


def test_a_lane_whose_keys_are_not_symbols_never_claims_the_instrument_is_gone(tmp_path,
                                                                               monkeypatch):
    """The scalp lane keys by STRATEGY name. Splitting on the dot there yields a string in no
    registry, and `instrument_gone` would RETIRE four live XAUUSD clocks."""
    shadow = tmp_path / "reports" / "shadow"
    shadow.mkdir(parents=True)
    monkeypatch.setattr(cl, "SHADOW_DIR", shadow)
    monkeypatch.setattr(cl, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(cl, "CONSTRAINTS", tmp_path / "nope.json")
    (tmp_path / "universe.json").write_text(json.dumps({"XAUUSD": {"asset_class": "metals"}}),
                                            encoding="utf-8")
    ln = cl.Lane("scalp", "scalp.json", "scalp_shadow", "MT5-Shadow (hourly)", 3600,
                 nested="sleeves")
    monkeypatch.setattr(cl, "LANES", (ln,))
    monkeypatch.setattr(cl, "LANE_BY_NAME", {"scalp": ln})
    monkeypatch.setattr(cl, "scheduled_tasks", lambda: {"MT5-Shadow": {"state": "Enabled"}})
    now = _wednesday()
    ln.path.write_text(json.dumps({"sleeves": {"xau_m5_anti_breakout_overlap": {
        "status": "ACCUMULATING", "timeframe": "M5",
        "last_attempt_at": (now - timedelta(days=4)).isoformat()}}}), encoding="utf-8")
    row = _census(None, now)[0]
    assert row["verdict"] == cl.FROZEN
    assert row["cause"] == "symbol_unresolved", row
    assert row["symbol_from"] == "UNRESOLVED"


def test_the_repair_is_proven_by_the_clock_moving_not_by_a_return_code(lane, monkeypatch):
    """An actuator that exits 0 and moves nothing is UNPROVEN; one that moves the stamp is
    REPAIRED. That asymmetry is the whole postcondition."""
    now = _wednesday()
    key = "EURUSD.carry.continuous"
    was = (now - timedelta(days=3)).isoformat()
    _write(lane, {key: {"status": "ACTIVE", "last_attempt_at": was}})
    pc = cl.clock_advanced_postcondition([("main", key, cl.parse_ts(was))])
    proved, why = pc.check({})
    assert proved is False and "none of the 1 aimed clock(s) advanced" in why
    _write(lane, {key: {"status": "ACTIVE", "last_attempt_at": now.isoformat()}})
    proved, why = pc.check({})
    assert proved is True and "advanced" in why


def test_repair_fires_at_the_frozen_clock_and_is_recorded(lane, monkeypatch):
    now = _wednesday()
    key = "EURUSD.carry.continuous"
    _write(lane, {key: {"status": "ACTIVE",
                        "last_attempt_at": (now - timedelta(days=3)).isoformat()}})
    frozen = [c for c in _census(set(), now) if c["verdict"] == cl.FROZEN]
    assert frozen
    monkeypatch.setattr(cl, "DESK", lane.path.parent.parent.parent)
    fired: list[list[str]] = []

    def fake_run(argv, timeout_s, cwd):
        fired.append(list(argv))
        # the repair the actuator stands for: the engine visits the key and stamps it
        _write(lane, {key: {"status": "ACTIVE", "last_attempt_at": now.isoformat()}})
        return {"rc": 0, "tail": ""}

    import libs.ops.control_plane.actuators as act
    monkeypatch.setattr(act, "_default_runner", fake_run)
    out = cl.repair(frozen, budget_s=5.0, apply=True)
    assert out and out[0]["actuator"] == "clock_reenrol"
    assert out[0]["result"] == "REPAIRED", out
    assert fired and "clock_reenrol.py" in " ".join(fired[0])


def test_instrument_gone_retires_with_a_reason_and_keeps_the_evidence(lane):
    now = _wednesday()
    key = "DELISTED.carry.continuous"
    _write(lane, {key: {"status": "ACTIVE", "n": 11, "cum_r": 0.42,
                        "last_attempt_at": (now - timedelta(days=5)).isoformat()}})
    frozen = [c for c in _census(set(), now) if c["verdict"] == cl.FROZEN]
    assert frozen[0]["cause"] == "instrument_gone"
    cl.retire_gone(frozen)
    row = json.loads(lane.path.read_text())[key]
    assert row["status"] == "RETIRED_INSTRUMENT_GONE"
    assert row["n"] == 11 and row["cum_r"] == 0.42        # evidence is never destroyed
    assert "no longer lists this symbol" in row["status_why"]


# ------------------------------------------------------------------------------- the fence
def _report(frozen_rows, at=None, **extra):
    return {"at": (at or datetime.now(UTC)).isoformat(), "clocks_total": 10,
            "frozen_after": len(frozen_rows), "frozen_before": len(frozen_rows),
            "frozen": frozen_rows, "counts": {}, "repairs": [], **extra}


FROZEN_ROW = {"lane": "main", "key": "EURUSD.carry.continuous", "timeframe": "H1",
              "lag_bars": 71, "freeze_bars": 23, "cause": "off_roster"}


def test_fence_is_red_while_a_clock_stays_frozen():
    out = fence.judge(_report([FROZEN_ROW]), {"lowest_frozen": 1}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("FROZEN main" in f for f in out["findings"])


def test_fence_is_green_when_nothing_is_frozen():
    out = fence.judge(_report([]), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.OK, out["findings"]


def test_fence_fails_when_the_frozen_count_rises_above_the_ratchet():
    doc = _report([])
    doc["frozen_after"] = 4
    out = fence.judge(doc, {"lowest_frozen": 2}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("ratchet floor" in f for f in out["findings"])


def test_fence_fails_on_a_stale_report():
    old = datetime.now(UTC) - timedelta(hours=9)
    out = fence.judge(_report([], at=old), {"lowest_frozen": 0}, require_state=True)
    assert out["verdict"] == fence.FAIL
    assert any("has stopped" in f for f in out["findings"])


def test_fence_is_unmeasured_off_the_box_and_a_defect_on_it():
    assert fence.judge(None, None, require_state=False)["verdict"] == fence.UNMEASURED
    assert fence.judge(None, None, require_state=True)["verdict"] == fence.FAIL


def test_the_ratchet_only_falls(tmp_path):
    p = tmp_path / "ratchet.json"
    assert cl.ratchet_write(9, p)["lowest_frozen"] == 9
    assert cl.ratchet_write(3, p)["lowest_frozen"] == 3
    assert cl.ratchet_write(7, p)["lowest_frozen"] == 3        # it may never rise
    assert cl.ratchet_read(p)["last_frozen"] == 7


def test_the_leg_is_wired_to_a_clock_and_a_layer():
    """UNWIRED OR IDLE IS A DEFECT (LAWS 7). The organ is done only when it has a leg and a
    layer, so the wiring is asserted here rather than hoped for."""
    from libs.research import layers
    assert layers.LEG_LAYER["clock_liveness"] == "meta"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("clock_liveness"' in cycle
    assert '"research/clock_liveness.py", "--once", "--budget-s", "300"' in cycle
    assert '"clock_liveness": clk' in cycle
    # the leg names its department in LEG_DEPARTMENT's `forward` block
    dept = cycle.split('# forward:', 1)[1].split('# meta:', 1)[0]
    assert '"clock_liveness"' in dept
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert "check_clock_liveness.py" in gate


# --------------------------------------------------------------------------------- 24/7
def test_a_disabled_clock_task_is_enabled_and_run_not_merely_noted():
    """The sharpened law: where a lane that advances clocks is off, turn it on in the same
    pass. Reporting `DISABLED` and moving on is the failure, not the finding."""
    calls: list[tuple[str, ...]] = []
    rows = cl.ensure_24x7({"MT5-Shadow": {"state": "Disabled", "repeat": "N/A",
                                          "schedule_type": "HOURLY"}},
                          apply=True, runner=lambda argv: (calls.append(tuple(argv)), 0)[1])
    shadow = next(r for r in rows if r["task"] == "MT5-Shadow")
    assert shadow["verdict"] == "ENABLED_AND_RUN", shadow
    assert any("/ENABLE" in c for c in calls)
    assert any("/Run" in c for c in calls)


def test_a_lane_that_only_fires_once_a_day_is_put_on_a_repetition():
    calls: list[tuple[str, ...]] = []
    rows = cl.ensure_24x7({"MT5-ForwardReconcile": {"state": "Enabled", "repeat": "N/A",
                                                    "schedule_type": "Daily"}},
                          apply=True, runner=lambda argv: (calls.append(tuple(argv)), 0)[1])
    row = next(r for r in rows if r["task"] == "MT5-ForwardReconcile")
    assert row["verdict"] == "REPEATING_24X7", row
    assert any("/RI" in c and str(cl.REPAIR_INTERVAL_MIN) in c for c in calls)


def test_a_repeating_task_is_left_alone():
    calls: list[tuple[str, ...]] = []
    rows = cl.ensure_24x7({"MT5-Dept-Forward": {"state": "Enabled",
                                                "repeat": "0 Hour(s), 10 Minute(s)",
                                                "schedule_type": "Daily"}},
                          apply=True, runner=lambda argv: (calls.append(tuple(argv)), 0)[1])
    row = next(r for r in rows if r["task"] == "MT5-Dept-Forward")
    assert row["verdict"] == "RUNNING_24X7" and not row["acted"]
    assert not calls


def test_an_absent_task_is_named_not_silently_passed():
    rows = cl.ensure_24x7({}, apply=False)
    assert {r["verdict"] for r in rows} == {"ABSENT"}
    assert len(rows) == len(cl.CLOCK_TASKS)
