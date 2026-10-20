"""E8 gold leaves placement evidence that names the host (2026-10-20).

Measured on the trading box: `scripts/check_placement_interlock.py` read only the gateway's
`decision_ledger.jsonl` (last row 10-16), and `prop/e8_gold.py` wrote only its state and pass
report, so an E8 window that stopped placing was invisible to the fence and nothing recorded which
host had sent the E8 gold orders. Pinned here, through `e8_gold.run` itself:

  1. every pass rewrites a heartbeat naming the host (host_identity verdict, hostname, machine
     id) and the pass time -- a flat pass and a failed connection included;
  2. each due window's decision is ONE ledger row per change of (outcome, reason) per day, so a
     one-gold-at-a-time deferral held for many passes is one row, and a pass with nothing due
     writes none -- the property that keeps the fence's breach (a) from reading it as a halt;
  3. a failed evidence write never raises and never changes what was placed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_evidence as ev  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402
from test_e8_gold_guard_and_open_risk import (  # noqa: E402
    _ENTRY,
    _MT5,
    _STOP,
    _sandbox,
    _short,
    _Venue,
)

_SPEC = importlib.util.spec_from_file_location(
    "check_placement_interlock_e8", _ROOT / "scripts" / "check_placement_interlock.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)


def _rows() -> list[dict[str, Any]]:
    path = ev.decisions_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _beat() -> dict[str, Any]:
    return json.loads(ev.heartbeat_path().read_text("utf-8"))


class _ArmedVenue(_Venue):
    sent: list[tuple[str, float]]

    def place_stop(self, symbol: str, side: str, lot: float, **kw: Any) -> int:
        self.sent = [*getattr(self, "sent", []), (side, lot)]
        return 7000 + len(self.sent)


# ------------------------------------------------------------------------ 1. the heartbeat

def test_a_flat_pass_with_a_window_due_writes_heartbeat_and_one_decision(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    doc = g.run(_Venue(), _MT5(), armed=False)
    beat = _beat()
    assert beat["lane"] == "e8_gold" and beat["status"] == "OK" and beat["armed"] is False
    for key in ("verdict", "hostname", "machine_id"):
        assert beat["host"][key], key
    assert beat["at"] == doc["at"] and beat["open_xau_positions"] == 0
    assert doc["host"] == beat["host"]
    [row] = _rows()
    assert row["lane"] == "e8_gold" and row["sleeve"] == "e8_gold:afternoon"
    assert (row["outcome"], row["reason"], row["taken"]) == ("WOULD_PLACE", "shadow_unarmed",
                                                              False)
    assert row["window"] == "afternoon" and row["server_date"] == "2026-10-15"
    assert row["lot"] > 0 and row["risk_usd"] == pytest.approx(doc["risk_usd"], rel=0.5)
    assert row["host"] == beat["host"]["hostname"] and row["host_verdict"]


def test_a_pass_with_nothing_due_writes_a_heartbeat_and_no_decision(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am", "afternoon"))
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert doc["placed"] == [] and _rows() == []
    assert _beat()["status"] == "OK" and _beat()["decisions"] == 0


def test_a_failed_connection_still_writes_the_heartbeat(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(g, "OUT", tmp_path / "report.json")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    g._failed_pass("VENUE_UNAVAILABLE", armed=True)
    beat = _beat()
    assert beat["status"] == "VENUE_UNAVAILABLE" and beat["host"]["verdict"]
    assert json.loads((tmp_path / "report.json").read_text("utf-8"))["host"] == beat["host"]


def test_the_account_is_read_from_the_sdk_handle_and_never_raises() -> None:
    class Api:
        account_id = 1234567

    class Venue:
        _api = Api()

    class Broken:
        @property
        def _api(self) -> Any:
            raise RuntimeError("not connected")

    assert ev.account_label(Venue()) == "tradelocker:1234567"
    assert ev.account_label(Broken()) == ev.UNMEASURED
    assert ev.account_label(object()) == ev.UNMEASURED


# ----------------------------------------------------------- 2. rows only at decision points

def test_a_one_at_risk_deferral_held_for_many_passes_is_one_row(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    at_risk = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _STOP, 9101: _STOP})
    for _ in range(12):                                   # an hour of five-minute passes
        doc = g.run(at_risk, _MT5(), armed=False)
        assert doc["placed"] == []
    [row] = _rows()
    assert (row["outcome"], row["reason"]) == ("DEFERRED", "one_at_risk")
    assert "one gold trade at risk" in row["why"] and row["risk_usd"] > 0
    # The earlier trades ratchet to break-even: the window places, and that is a new row.
    freed = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _ENTRY, 9101: _ENTRY})
    g.run(freed, _MT5(), armed=False)
    assert [(r["outcome"], r["reason"]) for r in _rows()] == [
        ("DEFERRED", "one_at_risk"), ("WOULD_PLACE", "shadow_unarmed")]


def test_an_armed_placement_is_taken_and_names_its_lot(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _ArmedVenue()
    doc = g.run(venue, _MT5(), armed=True)
    assert [p["window"] for p in doc["placed"]] == ["afternoon"] and venue.sent
    [row] = _rows()
    assert (row["outcome"], row["reason"], row["taken"]) == ("PLACED", "placed", True)
    assert row["lot"] == pytest.approx(max(lot for _side, lot in venue.sent))
    assert row["armed"] is True


def test_a_guard_stand_down_is_recorded_as_a_deferral_once(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, guard={
        "day": e8_guard.server_day(), "day_start": 100_000.0, "peak_equity": 100_000.0,
        "stood_down": True})
    for _ in range(3):
        assert g.run(_Venue(), _MT5(), armed=False)["placed"] == []
    [row] = _rows()
    assert (row["outcome"], row["reason"]) == ("DEFERRED", "guard_stood_down")
    assert row["window"] == "afternoon"


def test_a_new_server_day_records_the_same_decision_again() -> None:
    state: dict[str, Any] = {"date": "2026-10-15", "windows": {}, "carried": {}}
    first = [{"window": "afternoon", "outcome": "DEFERRED", "reason": "one_at_risk"}]
    state["evidence"] = {"afternoon": "DEFERRED:one_at_risk"}
    assert ev.pending_rows(first, state) == []
    rolled = g.rollover_state(state, "2026-10-16")
    assert "evidence" not in rolled and ev.pending_rows(first, rolled) == first


# ------------------------------------------------------------------------- 3. fail safe

def test_an_unwritable_evidence_dir_changes_nothing_that_was_placed(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    baseline = g.run(_Venue(), _MT5(), armed=False)
    _sandbox(monkeypatch, tmp_path)                       # the same fresh day again
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", "utf-8")
    monkeypatch.setenv(ev.DIR_ENV, str(blocker))          # every write under it now fails
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert doc["placed"] == baseline["placed"] and doc["skipped"] == baseline["skipped"]
    assert doc["decisions_recorded"] == 0 and doc["heartbeat"] is None
    # v2: the row the write could not land is KEPT in the state (and marked, so it is not
    # re-derived as a duplicate); the next writable pass writes it with its own stamp.
    state = json.loads(g.STATE.read_text("utf-8"))
    [kept] = state["evidence_pending"]
    assert (kept["outcome"], kept["reason"]) == ("WOULD_PLACE", "shadow_unarmed")
    assert state["evidence"] == {"afternoon": "WOULD_PLACE:shadow_unarmed"}


def test_an_identity_helper_that_raises_is_recorded_unmeasured(monkeypatch, tmp_path) -> None:
    from libs.ops import host_identity

    def boom(*a: Any, **k: Any) -> Any:
        raise OSError("registry unreadable")

    monkeypatch.setattr(host_identity, "identify", boom)
    _sandbox(monkeypatch, tmp_path)
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    assert doc["host"]["verdict"] == ev.UNMEASURED and _beat()["host"]["verdict"] == ev.UNMEASURED


def test_the_collector_and_the_outcome_never_raise() -> None:
    d = ev.Decisions(risk_of=lambda _w: 1 / 0)
    d.note("asia", ev.DEFERRED, ev.R_ONE_AT_RISK)         # risk_of raised: the row is lost, quietly
    assert d.rows == []
    assert ev.window_outcome({"buy_stop": {"lot": "bad"}}, {}, armed=True, unsizeable=False)[:2] \
        == (ev.PLACED, ev.R_PLACED)
    assert ev.stand_down_reason(float("nan"), None, {}) == ev.R_EQUITY_UNREADABLE


# ------------------------------------------------------- the fence reads these rows correctly

#: How the fence must classify every code this lane writes. A new code added to e8_evidence
#: without a line here fails the test below, so its breach semantics are decided on purpose.
_EXPECTED_EXEMPT = {
    ev.R_SHADOW, ev.R_LEGS_UNAVAILABLE, ev.R_KELLY_ZERO, ev.R_ONE_AT_RISK,
    ev.R_RISK_BUDGET, "guard_capped", "guard_passed", "guard_breached",
    ev.R_LEG_ABANDONED, ev.R_UNOWNED_POSITION,
}
#: v2: venue_rejected BREACHES (audit of 75004b6a) now that a re-send writes a PLACED row.
_EXPECTED_BREACH = {
    ev.R_UNSIZEABLE, ev.R_SIDE_UNREADABLE, ev.R_RISK_UNMEASURABLE, ev.R_EQUITY_UNREADABLE,
    ev.R_GUARD_UNREADABLE, ev.R_POSITIONS_UNREADABLE, "guard_stood_down", ev.R_VENUE_REJECTED,
}


def test_every_reason_code_the_lane_writes_is_classified_by_the_fence() -> None:
    codes = {v for k, v in vars(ev).items() if k.startswith("R_") and v != ev.R_PLACED}
    codes |= {ev.GUARD_PREFIX + v.value.lower() for v in e8_guard.Verdict
              if v is not e8_guard.Verdict.OK}
    assert codes == _EXPECTED_EXEMPT | _EXPECTED_BREACH
    assert {c for c in codes if c in fence.E8_EXEMPT_REASONS} == _EXPECTED_EXEMPT
    assert fence.E8_LEDGER_REL.endswith(ev.DECISIONS_NAME)
    assert fence.E8_HEARTBEAT_REL.endswith(ev.HEARTBEAT_NAME)


def test_rows_this_lane_writes_read_clean_through_the_fence(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    at_risk = _Venue([_short(100, 9100), _short(101, 9101)], {9100: _STOP, 9101: _STOP})
    for _ in range(40):
        g.run(at_risk, _MT5(), armed=False)
    root = tmp_path / "fence_root"
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / ev.DECISIONS_NAME).write_text(ev.decisions_path().read_text("utf-8"), "utf-8")
    (data / ev.HEARTBEAT_NAME).write_text(ev.heartbeat_path().read_text("utf-8"), "utf-8")
    doc = fence.scan(root)
    lane = doc["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK" and lane["rows_scanned"] == 1
    assert lane["heartbeat"]["hostname"] == _beat()["host"]["hostname"]
    assert doc["verdict"] == "NOT_APPLICABLE"            # no gateway here; E8 OK masks nothing


# ================================================== v2 (audit of 75004b6a, HOLD -> must/should)

from datetime import UTC, datetime, timedelta  # noqa: E402

_LEG = {"price": 4340.0, "sl": 4320.0, "tp": 4380.0, "lot": 0.5, "attempts": 1,
        "why": "VenueError: html", "first_at": "2026-09-28T07:00:05+00:00", "risk_usd": 1000.0}


class _RetryVenue:
    """Just what `_retry_failed_legs` touches."""

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.sent = fail, []

    def min_lot(self, _s: str) -> float:
        return 0.01

    def quote(self, _s: str) -> tuple[float, float]:
        return 4320.0, 4320.3

    def place_stop(self, sym: str, side: str, lot: float, **kw: Any) -> int:
        self.sent.append((side, lot))
        if self.fail:
            raise RuntimeError("<html>502</html>")
        return 901


def _retry_state(orders: dict | None = None) -> dict:
    w = {"placed_hour": 7.0, "orders": orders or {}, "position_id": None,
         "failed": {"buy_stop": dict(_LEG)}}
    return {"date": "2026-09-28", "windows": {"asia": w}, "carried": {}}


def _retry(monkeypatch, tmp_path, venue: _RetryVenue, st: dict, *, hour: float = 8.0,
           **kw: Any) -> ev.Decisions:
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents.jsonl")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    (tmp_path / "intents.jsonl").write_text("", "utf-8")
    decided = ev.Decisions()
    args = {"open_orders": [], "orders_ok": True, "filled": {}, "xau_positions": [],
            "positions_ok": True, "stood_down": False, "armed": True, "hist_rows": [],
            "history_ok": True, "instrument_id": 316, **kw}
    g._retry_failed_legs(venue, st, {"actions": []}, hour=hour, now=datetime.now(UTC),
                         decided=decided, **args)
    return decided


def _outcomes(d: ev.Decisions) -> list[tuple[str, str, str]]:
    return [(r["window"], r["outcome"], r["reason"]) for r in d.rows]


# ---------------------------------------------- must-fix 1: a re-send is a placement, on record

def test_a_successful_re_send_is_a_placed_row(monkeypatch, tmp_path) -> None:
    d = _retry(monkeypatch, tmp_path, _RetryVenue(), _retry_state())
    assert _outcomes(d) == [("asia", ev.PLACED, ev.R_PLACED)]
    assert d.rows[0]["taken"] is True and d.rows[0]["lot"] == 0.5
    assert d.rows[0]["risk_usd"] == 1000.0 and "order 901" in d.rows[0]["why"]


def test_an_adopted_landed_send_is_a_placed_row(monkeypatch, tmp_path) -> None:
    sent_ms = g._iso_ms(_LEG["first_at"])
    book = [{"id": 42, "side": "buy", "stopPrice": 4340.0, "tradableInstrumentId": 316,
             "qty": 0.5, "createdDate": sent_ms + 2_000}]
    v = _RetryVenue()
    d = _retry(monkeypatch, tmp_path, v, _retry_state(), open_orders=book)
    assert v.sent == [] and _outcomes(d) == [("asia", ev.PLACED, ev.R_PLACED)]
    assert "adopted order 42" in d.rows[0]["why"]


def test_a_re_send_refused_again_is_a_venue_rejected_deferral(monkeypatch, tmp_path) -> None:
    d = _retry(monkeypatch, tmp_path, _RetryVenue(fail=True), _retry_state())
    assert _outcomes(d) == [("asia", ev.DEFERRED, ev.R_VENUE_REJECTED)]


def test_an_abandoned_leg_with_nothing_placed_continues_the_venue_rejected_run(
        monkeypatch, tmp_path) -> None:
    d = _retry(monkeypatch, tmp_path, _RetryVenue(), _retry_state(), hour=13.5)
    assert _outcomes(d) == [("asia", ev.SKIPPED, ev.R_VENUE_REJECTED)]
    assert "session is over" in d.rows[0]["why"]


def test_an_abandoned_leg_whose_twin_was_placed_is_leg_abandoned(monkeypatch, tmp_path) -> None:
    st = _retry_state(orders={"sell_stop": {"id": 11, "price": 4300.0}})
    d = _retry(monkeypatch, tmp_path, _RetryVenue(), st, hour=13.5)
    assert _outcomes(d) == [("asia", ev.SKIPPED, ev.R_LEG_ABANDONED)]
    assert ev.abandon_reason("the other leg filled", {}) == ev.R_LEG_ABANDONED


def test_an_unowned_position_abandon_is_its_own_code(monkeypatch, tmp_path) -> None:
    pos = [{"id": 9, "side": "buy", "openDate": 4_102_444_800_000}]
    d = _retry(monkeypatch, tmp_path, _RetryVenue(), _retry_state(), xau_positions=pos)
    assert _outcomes(d) == [("asia", ev.SKIPPED, ev.R_UNOWNED_POSITION)]
    assert d.rows[0]["risk_usd"] == 1000.0


def test_a_retry_without_a_collector_sends_exactly_the_same(monkeypatch, tmp_path) -> None:
    """The evidence is read by nothing that sends: same venue calls, same state, with or without."""
    v1, st1 = _RetryVenue(), _retry_state()
    _retry(monkeypatch, tmp_path, v1, st1)
    v2, st2 = _RetryVenue(), _retry_state()
    monkeypatch.setattr(g, "INTENTS", tmp_path / "intents2.jsonl")
    (tmp_path / "intents2.jsonl").write_text("", "utf-8")
    g._retry_failed_legs(v2, st2, {"actions": []}, hour=8.0, now=datetime.now(UTC),
                         open_orders=[], orders_ok=True, filled={}, xau_positions=[],
                         positions_ok=True, stood_down=False, armed=True, hist_rows=[],
                         history_ok=True, instrument_id=316)
    assert v1.sent == v2.sent and st1 == st2


class _RejectingVenue(_ArmedVenue):
    """Refuses every send while `refuse` is set; accepts afterwards."""
    refuse = True

    def place_stop(self, symbol: str, side: str, lot: float, **kw: Any) -> int:
        if self.refuse:
            raise RuntimeError("<html>502</html>")
        return super().place_stop(symbol, side, lot, **kw)


def test_a_full_pass_refusal_then_re_send_reads_ok_through_the_fence(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _RejectingVenue()
    first = g.run(venue, _MT5(), armed=True)
    assert (first["decisions"][0]["outcome"], first["decisions"][0]["reason"]) == \
        (ev.DEFERRED, ev.R_VENUE_REJECTED)
    venue.refuse = False
    g.run(venue, _MT5(), armed=True)
    rows = _rows()
    assert rows[0]["reason"] == ev.R_VENUE_REJECTED
    assert rows[-1]["outcome"] == ev.PLACED and rows[-1]["taken"] is True, rows
    assert venue.sent
    root = tmp_path / "fence_root"
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / ev.DECISIONS_NAME).write_text(ev.decisions_path().read_text("utf-8"), "utf-8")
    (data / ev.HEARTBEAT_NAME).write_text(ev.heartbeat_path().read_text("utf-8"), "utf-8")
    lane = fence.scan(root)["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK" and not any(r["breach"] for r in lane["runs"].values())


# ------------------------------------------- must-fix 2: the heartbeat carries its failure clock

def test_the_heartbeat_carries_last_ok_and_failing_since() -> None:
    t0 = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
    ok = ev.write_heartbeat("OK", at=t0, armed=True)
    assert ok and ok["last_ok_at"] == t0.isoformat() and ok["failing_since"] is None
    f1 = ev.write_heartbeat("VENUE_UNAVAILABLE", at=t0 + timedelta(minutes=5), armed=True)
    f2 = ev.write_heartbeat("MT5_UNAVAILABLE", at=t0 + timedelta(minutes=10), armed=True)
    assert f1 and f2
    assert f2["failing_since"] == (t0 + timedelta(minutes=5)).isoformat()
    assert f2["last_ok_at"] == t0.isoformat()
    back = ev.write_heartbeat("OK", at=t0 + timedelta(minutes=15), armed=True)
    assert back and back["failing_since"] is None
    assert back["last_ok_at"] == (t0 + timedelta(minutes=15)).isoformat()


def test_a_torn_previous_heartbeat_starts_the_failure_clock_at_this_pass() -> None:
    ev.heartbeat_path().parent.mkdir(parents=True, exist_ok=True)
    ev.heartbeat_path().write_text('{"status": "VENUE_UNAV', "utf-8")
    t = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    beat = ev.write_heartbeat("NO_BARS", at=t, armed=False)
    assert beat and beat["failing_since"] == t.isoformat() and beat["last_ok_at"] is None


def test_a_failed_connection_pass_reads_unmeasured_through_the_fence(
        monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(g, "OUT", tmp_path / "report.json")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    ev.write_heartbeat("OK", at=datetime.now(UTC) - timedelta(minutes=5), armed=True)
    g._failed_pass("VENUE_UNAVAILABLE", armed=True)
    root = tmp_path / "fence_root"
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / ev.HEARTBEAT_NAME).write_text(ev.heartbeat_path().read_text("utf-8"), "utf-8")
    lane = fence.scan(root)["lanes"]["e8_gold"]
    assert lane["verdict"] == "UNMEASURED" and lane["heartbeat"]["status"] == "VENUE_UNAVAILABLE"
    assert lane["heartbeat"]["last_ok_at"]


# ------------------------------------------------------------ should-fix: pending rows survive

def test_a_lost_placed_row_is_kept_and_written_next_pass_across_the_rollover(
        monkeypatch) -> None:
    """The audit's false HALT: refusal, a lost PLACED row, a refusal the next day."""
    host = {"hostname": "box", "machine_id": "m", "verdict": "TRADING"}
    d1 = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
    st: dict[str, Any] = {"date": "2026-10-15", "windows": {}, "carried": {}}
    ev.record_decisions([{"window": "afternoon", "outcome": ev.DEFERRED,
                          "reason": "guard_stood_down", "taken": False}], st, now=d1,
                        server_date="2026-10-15", account="tradelocker:1", armed=True,
                        host=host)
    real = ev.decisions_path()
    blocked = real.parent / "blocked"
    blocked.write_text("x", "utf-8")
    monkeypatch.setenv(ev.DIR_ENV, str(blocked))        # every write under it now fails
    placed = [{"window": "afternoon", "outcome": ev.PLACED, "reason": ev.R_PLACED,
               "taken": True}]
    assert ev.record_decisions(placed, st, now=d1 + timedelta(minutes=5),
                               server_date="2026-10-15", account="tradelocker:1",
                               armed=True, host=host) == []
    monkeypatch.setenv(ev.DIR_ENV, str(real.parent))
    assert [r["outcome"] for r in st["evidence_pending"]] == [ev.PLACED]
    rolled = g.rollover_state(st, "2026-10-16")
    ev.carry_pending(st, rolled)
    assert "evidence" not in rolled and len(rolled["evidence_pending"]) == 1
    d2 = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)
    written = ev.record_decisions([{"window": "afternoon", "outcome": ev.DEFERRED,
                                    "reason": "guard_stood_down", "taken": False}], rolled,
                                  now=d2, server_date="2026-10-16", account="tradelocker:1",
                                  armed=True, host=host)
    assert [r["outcome"] for r in written] == [ev.PLACED, ev.DEFERRED]
    assert written[0]["decided_at"] == (d1 + timedelta(minutes=5)).isoformat(timespec="seconds")
    assert "evidence_pending" not in rolled
    root = real.parent / "fence_root"
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / ev.DECISIONS_NAME).write_text(real.read_text("utf-8"), "utf-8")
    ev.write_heartbeat("OK", at=datetime.now(UTC), armed=True)
    (data / ev.HEARTBEAT_NAME).write_text(ev.heartbeat_path().read_text("utf-8"), "utf-8")
    lane = fence.scan(root, now=d2 + timedelta(hours=1))["lanes"]["e8_gold"]
    assert lane["verdict"] == "OK", lane                 # v1 read this HALTED


def test_pending_rows_are_bounded() -> None:
    st: dict[str, Any] = {"evidence_pending": [{"window": "w", "n": i}
                                               for i in range(ev.PENDING_MAX + 50)]}
    new: dict[str, Any] = {}
    ev.carry_pending(st, new)
    assert len(new["evidence_pending"]) == ev.PENDING_MAX
    assert new["evidence_pending"][-1]["n"] == ev.PENDING_MAX + 49
    ev.carry_pending(st, st)                                          # same day: untouched
    assert len(st["evidence_pending"]) == ev.PENDING_MAX + 50


# --------------------------------------------- should-fix: heartbeat via tmp + os.replace

def test_a_refused_replace_writes_in_place_and_leaves_no_temp(monkeypatch) -> None:
    """WinError 5 on a destination a reader holds open: os.replace refuses, the write lands."""
    def refuse(*_a: Any, **_k: Any) -> None:
        raise PermissionError(13, "Access is denied", None, 5)

    monkeypatch.setattr(ev.os, "replace", refuse)
    beat = ev.write_heartbeat("OK", at=datetime.now(UTC), armed=True)
    assert beat is not None and _beat()["status"] == "OK"
    assert not list(ev.heartbeat_path().parent.glob(".*.tmp"))


def test_a_read_only_heartbeat_returns_none_never_raises(monkeypatch) -> None:
    def refuse(*_a: Any, **_k: Any) -> None:
        raise PermissionError(13, "Access is denied", None, 5)

    real_write = Path.write_text

    def write(self: Path, *a: Any, **k: Any) -> int:
        if self == ev.heartbeat_path():
            raise PermissionError(13, "Access is denied", None, 5)
        return real_write(self, *a, **k)

    monkeypatch.setattr(ev.os, "replace", refuse)
    monkeypatch.setattr(Path, "write_text", write)
    said: list[str] = []
    assert ev.write_heartbeat("OK", at=datetime.now(UTC), armed=True, log=said.append) is None
    assert said and not list(ev.heartbeat_path().parent.glob(".*.tmp"))


def test_a_refused_replace_changes_nothing_a_pass_places(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path)
    venue = _ArmedVenue()
    base = g.run(venue, _MT5(), armed=True)
    sent = list(venue.sent)

    def refuse(*_a: Any, **_k: Any) -> None:
        raise PermissionError(13, "Access is denied", None, 5)

    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setenv(ev.DIR_ENV, str(tmp_path / "other_evidence"))
    monkeypatch.setattr(ev.os, "replace", refuse)
    venue2 = _ArmedVenue()
    doc = g.run(venue2, _MT5(), armed=True)
    assert venue2.sent == sent and doc["placed"] == base["placed"]
    assert doc["skipped"] == base["skipped"] and doc["actions"] == base["actions"]


# ------------------------------------------------ should-fix: nothing in the pass can raise

def test_window_outcome_and_heartbeat_extra_never_raise() -> None:
    class Bad(dict):
        def __iter__(self) -> Any:
            raise RuntimeError("bad legs")

        def __bool__(self) -> bool:
            return True

    out = ev.window_outcome(Bad(), {}, armed=True, unsizeable=False)
    assert out[0] == ev.SKIPPED and "not derived" in out[2]
    beat = ev.write_heartbeat("OK", at=datetime.now(UTC), armed=False,
                              extra={"status": "clobber", "hour": object()})
    assert beat and beat["status"] == "OK"                  # extra never overwrites the core
    assert ev.write_heartbeat("OK", at=datetime.now(UTC), armed=False,
                              extra="not a dict") is not None   # type: ignore[arg-type]


# ----------------------------------------------- should-fix: a bounded, published ledger

def test_the_ledger_is_rotated_to_its_newest_rows(monkeypatch) -> None:
    monkeypatch.setattr(ev, "LEDGER_MAX_BYTES", 2_000)
    monkeypatch.setattr(ev, "LEDGER_KEEP_LINES", 3)
    host = {"hostname": "box"}
    st: dict[str, Any] = {}
    t = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
    for i in range(20):
        ev.record_decisions([{"window": f"w{i}", "outcome": ev.DEFERRED, "reason": "x" * 50}],
                            st, now=t, server_date="2026-10-20", account=ev.UNMEASURED,
                            armed=False, host=host)
    rows = _rows()
    assert len(rows) <= 3 + 2 and rows[-1]["window"] == "w19"
    assert ev.decisions_path().stat().st_size <= 2_000 + 1_000


_SYNC = _ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def test_both_evidence_files_are_published_by_the_box() -> None:
    import re
    import subprocess
    src = _SYNC.read_text("utf-8", errors="ignore")
    start = src.index("$reportPaths = @(")
    listed = re.findall(r'"([^"]+)"', src[start:src.index("\n)", start)])
    for name in (ev.HEARTBEAT_NAME, ev.DECISIONS_NAME):
        rel = f"desks/mt5/data/{name}"
        assert rel in listed, rel
        ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=_ROOT)
        assert ignored.returncode == 1, f"{rel} is gitignored, so publishing it stages nothing"
    assert fence.E8_LEDGER_REL in listed and fence.E8_HEARTBEAT_REL in listed


class _IdApi:
    account_id = 7654321

    @staticmethod
    def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
        return []


class _IdVenue(_ArmedVenue):
    _api = _IdApi()


def test_no_account_id_reaches_either_published_file(monkeypatch, tmp_path) -> None:
    """The repository is public: only the keyed pseudonym is written, never the id."""
    _sandbox(monkeypatch, tmp_path)
    doc = g.run(_IdVenue(), _MT5(), armed=True)
    assert doc["account"] == "tradelocker:7654321"          # the unpublished pass report only
    for path in (ev.heartbeat_path(), ev.decisions_path()):
        text = path.read_text("utf-8")
        assert "7654321" not in text, path
        assert '"account":' not in text
    ref = _beat()["account_ref"]
    assert ref.startswith("tradelocker:") and len(ref.split(":", 1)[1]) == 16
    assert _rows()[0]["account_ref"] == ref
    assert ev.account_ref("tradelocker:7654321") == ref                    # stable
    assert ev.account_ref("tradelocker:7654322") != ref                    # per account
    import hashlib
    assert hashlib.sha256(b"tradelocker:7654321").hexdigest()[:16] not in ref  # keyed, not bare


def test_without_a_key_the_account_is_unkeyed_never_raw(monkeypatch, tmp_path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", "utf-8")
    monkeypatch.setenv(ev.KEY_FILE_ENV, str(blocker / "e8_evidence.key"))
    assert ev.account_ref("tradelocker:7654321") == f"tradelocker:{ev.UNKEYED}"
    assert ev.account_ref(ev.UNMEASURED) == ev.UNMEASURED
    monkeypatch.setenv(ev.KEY_ENV, "k" * 40)
    assert ev.account_ref("tradelocker:7654321") not in (f"tradelocker:{ev.UNKEYED}",
                                                        "tradelocker:7654321")
