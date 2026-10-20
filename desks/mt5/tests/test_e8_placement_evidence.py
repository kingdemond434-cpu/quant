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
    # nothing was marked, so the next writable pass records the decision it missed
    assert "evidence" not in json.loads(g.STATE.read_text("utf-8"))


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
    ev.R_SHADOW, ev.R_VENUE_REJECTED, ev.R_LEGS_UNAVAILABLE, ev.R_KELLY_ZERO, ev.R_ONE_AT_RISK,
    ev.R_RISK_BUDGET, "guard_capped", "guard_passed", "guard_breached",
}
_EXPECTED_BREACH = {
    ev.R_UNSIZEABLE, ev.R_SIDE_UNREADABLE, ev.R_RISK_UNMEASURABLE, ev.R_EQUITY_UNREADABLE,
    ev.R_GUARD_UNREADABLE, ev.R_POSITIONS_UNREADABLE, "guard_stood_down",
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
