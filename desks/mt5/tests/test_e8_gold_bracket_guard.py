"""E8 gold: a stand-down reaches resting legs, and a bracket must fit the floor and the cap.

1. On a pass where `e8_guard.assess(...).may_open` is False (STOOD_DOWN, CAPPED, BREACHED,
   PASSED) this lane cancels its own journalled entry orders still resting, so a twin placed
   before the verdict cannot fill after it. Filled positions, their stops and orders the lane did
   not send are never touched; a failed cancel is logged, never raised, and retried next pass.
2. Both legs of a bracket, each grossed up for slip (measured, else DEFAULT_BRACKET_SLIP), must
   fit the guard's room to today's floor -- in addition to the committed-risk x SLIP_BUFFER check.
3. A leg whose take-profit alone would cross the daily profit cap headroom is refused, and the
   window with it; the cap is e8_guard's, and 0.95% risk at RR 2 still fits a fresh day.

The fixture is test_e8_gold_guard_and_open_risk's: the afternoon window is due at 17:30 with a
33.5-point stop and a 67-point target, 500 USD of risk -> 0.14 lots at a 100 oz contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_e8_gold_guard_and_open_risk as h  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from prop import e8_guard  # noqa: E402

#: The journal row of a placed leg, exactly as it was before these rails existed.
_SENT_KEYS = {"at", "window", "side", "price", "sl", "tp", "lot", "stop_dist", "risk_usd",
              "sizing", "risk_frac", "risk_source", "armed", "status", "order_id"}


class _Venue(h._Venue):
    """The shared fake, with resting orders the lane can cancel and an armed send."""

    def __init__(self, *, equity: float = 100_000.0, resting: list[int] | None = None,
                 cancel_fails: int = 0, cancel_raises: bool = False) -> None:
        super().__init__(equity=equity)
        self.sent: list[tuple[str, float, float]] = []
        self.resting = list(resting or [])
        self.cancelled: list[int] = []
        self._fails = cancel_fails
        self._cancel_raises = cancel_raises

    def orders(self, symbol: str | None = None) -> list[dict]:
        return [{"id": oid, "stopPrice": 4250.0} for oid in self.resting]

    def place_stop(self, symbol: str, side: str, lot: float, *, price: float, stop: float,
                   take_profit: float) -> int:
        self.sent.append((side, float(lot), float(price)))
        return 7000 + len(self.sent)

    def cancel(self, order_id: int) -> bool:
        if self._fails > 0:
            self._fails -= 1
            if self._cancel_raises:
                raise ConnectionError("venue answered with an HTML page")
            return False
        self.cancelled.append(int(order_id))
        self.resting.remove(int(order_id))
        return True


def _guard(equity: float = 100_000.0, *, day_start: float = 100_000.0,
           stood_down: bool = False) -> dict[str, Any]:
    return {"day": e8_guard.server_day(), "day_start": day_start,
            "peak_equity": max(equity, day_start), "stood_down": stood_down}


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *,
             guard: dict[str, Any] | None = None, slip: Any = None) -> Path:
    h._sandbox(monkeypatch, tmp_path, guard=guard)
    monkeypatch.setattr(g, "GOLD_MAX_LOT_FILE", tmp_path / "E8_GOLD_MAX_LOT.json")
    p = tmp_path / "E8_GOLD_SLIP.json"
    if slip is not None:
        p.write_text(slip if isinstance(slip, str) else json.dumps(slip), encoding="utf-8")
    monkeypatch.setattr(g, "BRACKET_SLIP_FILE", p)
    return p


def _journal(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "intents.json"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _rail_skips(doc: dict[str, Any], rail: str) -> list[dict[str, Any]]:
    return [s for s in doc["skipped"] if s.get("rail") == rail]


# ------------------------------------------------------------- unchanged when nothing binds

def test_placement_is_unchanged_when_no_rail_binds(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert sorted(venue.sent) == [("buy", 0.14, 4310.0), ("sell", 0.14, 4290.0)]
    assert [p["window"] for p in doc["placed"]] == ["afternoon"]
    assert not _rail_skips(doc, g.DAILY_FLOOR_RAIL) and not _rail_skips(doc, g.PROFIT_CAP_RAIL)
    assert not [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert venue.cancelled == []
    assert doc["bracket_slip"]["slip"] == g.DEFAULT_BRACKET_SLIP
    rows = _journal(tmp_path)
    assert [r["status"] for r in rows] == ["SENT", "SENT"]
    assert all(set(r) == _SENT_KEYS for r in rows), [sorted(r) for r in rows]


def test_max_asia_risk_at_rr2_still_passes_both_rails(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 0.95% of 100k = 950 USD: 2 x 950 x 1.3 = 2,470 <= 2,500 of room on a fresh day, and the
    # 67-point target at 0.28 lots is 1,876 USD, inside the 2,000 cap.
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.sent) == [("buy", 0.28, 4310.0), ("sell", 0.28, 4290.0)]
    assert not _rail_skips(doc, g.DAILY_FLOOR_RAIL) and not _rail_skips(doc, g.PROFIT_CAP_RAIL)
    # The coordinator's figure for a 0.95% leg at RR 2 also fits a fresh day's cap.
    assert g.profit_cap_breach({"buy_stop": 1915.0, "sell_stop": 1915.0},
                               e8_guard.START_BALANCE * e8_guard.DAILY_PROFIT_CAP) is None


# ------------------------------------------------------------- rule 2: today's floor, both legs

def test_a_bracket_whose_two_legs_would_breach_the_floor_is_skipped_and_billed(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Down 100 on the day: 2,400 of room. 2 x 949.05 x 1.3 = 2,467 does not fit, although the
    # older committed-risk check ((0 + 949) x 1.25 = 1,186 against 2,300) would have passed it.
    _sandbox(monkeypatch, tmp_path, guard=_guard(99_900.0))
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = _rail_skips(doc, g.DAILY_FLOOR_RAIL)
    assert skip["window"] == "afternoon" and "today's floor" in skip["why"]
    assert skip["legs"] == 2 and skip["slip"] == g.DEFAULT_BRACKET_SLIP
    assert skip["reason"] == g.DAILY_FLOOR_REASON
    assert skip["room_to_daily_floor"] == pytest.approx(2400.0)
    assert skip["missed_growth_risk_usd"] == pytest.approx(949.05)
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.DAILY_FLOOR_RAIL]
    assert row["status"] == "RAIL_BLOCKED" and row.get("order_id") is None
    assert "MISSED GROWTH" in (tmp_path / "log.json").read_text(encoding="utf-8")
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["windows"]["afternoon"]["skipped"] == g.DAILY_FLOOR_RAIL
    again = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and not _rail_skips(again, g.DAILY_FLOOR_RAIL)
    assert len([r for r in _journal(tmp_path) if r.get("rail") == g.DAILY_FLOOR_RAIL]) == 1
    # Published two-sided beside the lot ceiling's: the risk withheld, the saving UNMEASURED.
    sys.path.insert(0, str(_DESK / "research"))
    import missed_growth as mg
    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "intents.json")
    (line,) = mg.published_e8_gold_lines()["lines"]
    assert line["rail"] == g.DAILY_FLOOR_RAIL and line["n_blocked"] == 1
    assert line["cost"]["risk_withheld_usd"] == pytest.approx(949.05)
    assert line["saving"]["verdict"] == mg.UNMEASURED


def test_a_shrunk_leg_is_budgeted_against_the_floor_at_its_shrunk_risk(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 949 USD at a 10 oz contract needs 2.83 lots; the ceiling sends 0.75 (251.25 USD a leg), and
    # 2 x 251.25 x 1.3 = 653 fits the 2,400 that 2 x 949 x 1.3 = 2,467 does not.
    _sandbox(monkeypatch, tmp_path, guard=_guard(99_900.0))
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    monkeypatch.setattr(venue, "details", lambda symbol: {"contractSize": 10.0,
                                                          "currency": "USD", "lotStep": 0.01})
    doc = g.run(venue, h._MT5(), armed=True)
    assert not _rail_skips(doc, g.DAILY_FLOOR_RAIL)
    assert sorted(venue.sent) == [("buy", 0.75, 4310.0), ("sell", 0.75, 4290.0)]
    assert doc["shrunk"][0]["risk_usd"] == pytest.approx(251.25)


def test_the_lanes_measured_slip_replaces_the_default(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard(99_900.0), slip={"slip": 0.0})
    monkeypatch.setattr(g, "RISK_FRAC", 0.0095)
    venue = _Venue(equity=99_900.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["bracket_slip"] == {"slip": 0.0, "source": "E8_GOLD_SLIP.json"}
    assert not _rail_skips(doc, g.DAILY_FLOOR_RAIL)          # 2 x 949 = 1,898 <= 2,400
    assert len(venue.sent) == 2


@pytest.mark.parametrize("override", [{"slip": -0.1}, {"slip": "0.1"}, {"slip": True}, {},
                                      [0.1], "NaN", '{"slip": Infinity}', "{ not json"])
def test_an_invalid_slip_file_falls_back_to_the_default(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override: Any) -> None:
    _sandbox(monkeypatch, tmp_path, slip=override)
    slip, src = g.bracket_slip()
    assert slip == g.DEFAULT_BRACKET_SLIP and src.startswith("default DEFAULT_BRACKET_SLIP (")


def test_the_floor_rule_counts_the_legs_actually_sent() -> None:
    assert g.bracket_floor_breach(2, 1000.0, 0.3, 2600.0) is None        # 2,600 <= 2,600
    assert g.bracket_floor_breach(2, 1000.0, 0.3, 2599.0) is not None
    assert g.bracket_floor_breach(1, 1000.0, 0.3, 1300.0) is None        # one leg: 1,300


# ------------------------------------------------------------- rule 3: the daily profit cap

def test_a_target_past_the_profit_cap_headroom_skips_the_window(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Up 1,500 today: 500 of counted profit left. 0.15 lots x 67 points x 100 oz = 1,005 USD.
    _sandbox(monkeypatch, tmp_path, guard=_guard(101_500.0))
    venue = _Venue(equity=101_500.0)
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert venue.sent == [] and doc["placed"] == []
    (skip,) = _rail_skips(doc, g.PROFIT_CAP_RAIL)
    cap = e8_guard.START_BALANCE * e8_guard.DAILY_PROFIT_CAP
    assert skip["profit_cap_headroom_usd"] == pytest.approx(cap - 1500.0)
    assert skip["target_profit_usd"] == {"buy_stop": 1005.0, "sell_stop": 1005.0}
    assert "daily profit cap" in skip["why"] and skip["reason"] == g.PROFIT_CAP_REASON
    assert skip["missed_growth_risk_usd"] == pytest.approx(507.5)
    (row,) = [r for r in _journal(tmp_path) if r.get("rail") == g.PROFIT_CAP_RAIL]
    assert row["status"] == "RAIL_BLOCKED"


def test_the_headroom_is_the_guards_cap_less_todays_profit() -> None:
    cap = e8_guard.START_BALANCE * e8_guard.DAILY_PROFIT_CAP
    up = e8_guard.assess(101_200.0, state=_guard(101_200.0), persist=False)
    down = e8_guard.assess(99_500.0, state=_guard(99_500.0), persist=False)
    assert up.profit_cap_headroom == pytest.approx(cap - 1200.0)
    assert down.profit_cap_headroom == pytest.approx(cap), "a losing day leaves the whole cap"
    assert g.profit_cap_breach({"buy_stop": 800.0}, 800.0) is None
    assert "buy_stop" in (g.profit_cap_breach({"buy_stop": 800.01, "sell_stop": 10.0}, 800.0)
                          or "")


def test_an_unmeasurable_rail_defers_and_never_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())

    def boom(*a: Any, **k: Any) -> Any:
        raise ArithmeticError("no figures")

    monkeypatch.setattr(g, "bracket_floor_breach", boom)
    venue = _Venue()
    doc = g.run(venue, h._MT5(), armed=True)
    assert venue.sent == [] and "bracket rails unmeasurable" in " ".join(
        str(s.get("why")) for s in doc["skipped"])
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "afternoon" not in saved["windows"], "a deferral is not a spent window"


# ------------------------------------------------------------- rule 1: stand-down cancels

_OWN = (9001, 9002)
_PROTECTIVE, _HUMAN = 555, 777


def _resting_bracket(tmp_path: Path) -> None:
    """The afternoon bracket placed at 17:00 and still resting, journalled as this lane's."""
    legs = {"buy_stop": {"id": _OWN[0], "price": 4310.0, "sl": 4276.5, "tp": 4377.0,
                         "lot": 0.14},
            "sell_stop": {"id": _OWN[1], "price": 4290.0, "sl": 4323.5, "tp": 4223.0,
                          "lot": 0.14}}
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    state["windows"]["afternoon"] = {"placed_hour": 17.0, "orders": legs, "position_id": None,
                                     "shadow": False}
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with (tmp_path / "intents.json").open("a", encoding="utf-8") as fh:
        for side, leg in legs.items():
            fh.write(json.dumps({"at": "2026-10-15T17:00:00+00:00", "window": "afternoon",
                                 "side": side, "status": "SENT", "order_id": leg["id"],
                                 "risk_usd": 500.0, **{k: leg[k] for k in
                                                       ("price", "sl", "tp", "lot")}}) + "\n")


@pytest.mark.parametrize(("guard", "equity", "verdict"), [
    (_guard(stood_down=True), 100_000.0, "STOOD_DOWN"),
    (_guard(102_050.0), 102_050.0, "CAPPED"),
    (_guard(97_400.0), 97_400.0, "BREACHED"),
])
def test_a_refusing_verdict_cancels_our_resting_legs_only(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, guard: dict[str, Any], equity: float,
        verdict: str) -> None:
    _sandbox(monkeypatch, tmp_path, guard=guard)
    _resting_bracket(tmp_path)
    venue = _Venue(equity=equity, resting=[*_OWN, _PROTECTIVE, _HUMAN])
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == verdict
    assert sorted(venue.cancelled) == list(_OWN)
    assert venue.resting == [_PROTECTIVE, _HUMAN], "a stop or a human's order is never touched"
    acts = [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert sorted(a["order_id"] for a in acts) == list(_OWN)
    assert all(a["ok"] and a["verdict"] == verdict for a in acts)
    # Management on the same pass does not try the same ids again.
    assert not [a for a in doc["actions"] if a["act"] in ("oco_cancel", "ttl_cancel",
                                                          "eod_cancel", "stale_cancel")]
    assert venue.sent == []


def test_an_ok_verdict_leaves_the_resting_bracket_alone(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard())
    _resting_bracket(tmp_path)
    venue = _Venue(resting=[*_OWN, _PROTECTIVE, _HUMAN])
    doc = g.run(venue, h._MT5(), armed=True)
    assert doc["guard_decision"]["verdict"] == "OK"
    assert venue.cancelled == []
    assert not [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]


@pytest.mark.parametrize("raises", [True, False])
def test_a_failed_cancel_is_logged_never_raised_and_retried_next_pass(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raises: bool) -> None:
    _sandbox(monkeypatch, tmp_path, guard=_guard(stood_down=True))
    _resting_bracket(tmp_path)
    venue = _Venue(resting=[*_OWN], cancel_fails=2, cancel_raises=raises)
    doc = g.run(venue, h._MT5(), armed=True)
    acts = [a for a in doc["actions"] if a["act"] == g.STAND_DOWN_CANCEL]
    assert len(acts) == 2 and not any(a["ok"] for a in acts)
    assert all("tried again next pass" in a["why"] for a in acts)
    assert venue.resting == list(_OWN)
    assert f"{g.STAND_DOWN_CANCEL} FAILED" in (tmp_path / "log.json").read_text(encoding="utf-8")
    again = g.run(venue, h._MT5(), armed=True)
    assert sorted(venue.cancelled) == list(_OWN) and venue.resting == []
    assert all(a["ok"] for a in again["actions"] if a["act"] == g.STAND_DOWN_CANCEL)


def test_a_filled_entry_is_not_a_resting_leg() -> None:
    own = {9001: {"window": "afternoon"}, 9002: {"window": "afternoon"}}
    assert g.stand_down_cancels({9001, 9002, 555}, {9001: 42}, own) == [9002]
    assert g.stand_down_cancels({555, 777}, {}, own) == []
