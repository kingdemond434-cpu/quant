"""Four gold exit defects (audit, fixed 2026-09-29), each pinned by its own regression.

  a. A scalp ADD-ON re-sent the basket's ORIGINAL stop, and its retarget pushed that level back
     onto slices already trailed or floored at break-even. The add-on now carries the tightest
     stop the account holds, and the retarget never loosens a slice's own stop.
  b. The E8 daily rollover dropped open positions from management (a carried row did not carry
     twice; a fill not yet recorded was lost). Rows now ride forward and our own positions are
     RE-ADOPTED from the venue by the entry-order ids this lane sent.
  c. GTC entry legs outlived the day: cancellation walked today's windows only. Our own resting
     entry orders that no window of today owns are now cancelled.
  d. Trail/break-even moves under 0.05R were skipped. The threshold is now one venue stop step.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))
_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from mt5desk import position_manager as pm  # noqa: E402
from prop import e8_gold  # noqa: E402

_GW = _DESK / "mt5desk" / "gateway.py"
_GW_TREE = ast.parse(_GW.read_text(encoding="utf-8"))


def _gw_function(name: str) -> ast.FunctionDef:
    for node in _GW_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"gateway.{name} not found")


# ----------------------------------------------------------------------- a. the add-on stop

def test_a_the_tightest_stop_is_the_highest_for_a_long_and_lowest_for_a_short() -> None:
    assert pm.tightest_stop(side=1, stops=[4290.0, 4300.5, 0.0]) == 4300.5
    assert pm.tightest_stop(side=-1, stops=[4310.0, 4301.2, 0.0]) == 4301.2
    assert pm.tightest_stop(side=1, stops=[0.0, None]) is None


def test_a_never_loosen_keeps_a_trailed_stop_against_the_original() -> None:
    # Long: original 4290, trailed to break-even 4300.04 -> the original must not come back.
    assert pm.never_loosen(side=1, proposed=4290.0, current=4300.04) == 4300.04
    assert pm.never_loosen(side=-1, proposed=4310.0, current=4299.96) == 4299.96
    # A tighter proposal is still applied, and a stop-less position takes the proposal.
    assert pm.never_loosen(side=1, proposed=4305.0, current=4300.04) == 4305.0
    assert pm.never_loosen(side=1, proposed=4290.0, current=0.0) == 4290.0


def test_a_the_add_on_retarget_never_moves_a_trailed_slice_back_to_the_original_stop() -> None:
    sent: list[dict] = []
    positions = [SimpleNamespace(ticket=1, type=0, sl=4300.04),    # floored at break-even
                 SimpleNamespace(ticket=2, type=0, sl=0.0)]         # no stop recorded
    seed = {
        "mt5": SimpleNamespace(TRADE_ACTION_SLTP=6, POSITION_TYPE_BUY=0,
                               order_send=lambda req: sent.append(req) or
                               SimpleNamespace(retcode=10009)),
        "_sleeve_positions": lambda symbol, name: positions,
        "_pm": pm, "MAGIC": 1, "log": lambda msg: None,
    }
    exec(compile(ast.Module(body=[_gw_function("_retarget_sleeve_positions")], type_ignores=[]),
                 "<gw>", "exec"), seed)
    seed["_retarget_sleeve_positions"]("XAUUSD", "scalp", 4290.0, 4330.0)
    assert [r["sl"] for r in sent] == [4300.04, 4290.0]
    assert all(r["tp"] == 4330.0 for r in sent)


def test_a_the_add_on_order_carries_the_current_stop_not_the_basket_opening_stop() -> None:
    src = ast.unparse(_gw_function("resolve_scalp_order"))
    assert "_pm.tightest_stop(" in src and "_sleeve_positions(" in src
    assert "'stop': float(stop_now)" in src
    assert "'stop': float(basket['stop'])" not in src


# ----------------------------------------------------------------------- b. rollover re-adoption

def test_b_a_carried_position_rides_through_a_second_rollover() -> None:
    day1 = {"date": "2026-09-24", "carried": {},
            "windows": {"asia": {"position_id": 7, "orders": {}},
                        "london_am": {"position_id": None, "orders": {}}}}
    day2 = e8_gold.rollover_state(day1, "2026-09-25")
    assert set(day2["carried"]) == {"asia"} and day2["windows"] == {}
    day3 = e8_gold.rollover_state(day2, "2026-09-26")
    assert day3["carried"].get("asia", {}).get("position_id") == 7, \
        "a position carried into yesterday must still be carried today"
    assert e8_gold.rollover_state(day3, "2026-09-26") is day3


def test_b_our_position_filled_before_the_rollover_is_readopted_by_order_id() -> None:
    state = {"date": "2026-09-25", "windows": {}, "carried": {}}
    journal = [{"status": "SENT", "order_id": 11, "window": "afternoon", "side": "buy_stop",
                "price": 4300.0, "sl": 4285.0, "tp": 4330.0, "lot": 0.5},
               {"status": "WOULD_PLACE", "window": "asia", "side": "sell_stop"}]
    own = e8_gold.own_entry_orders(journal, state)
    acts = e8_gold.readopt_positions(state, {11: 501, 99: 777}, {501, 777}, own)
    assert [a["position_id"] for a in acts] == [501], "only OUR order's position is adopted"
    row = state["carried"]["readopted:501"]
    assert row["orders"]["buy_stop"]["sl"] == 4285.0, "the original stop survives for the R scale"
    assert e8_gold._window_for_position(state, 501) is not None
    # Idempotent: a mapped position is not adopted twice.
    assert e8_gold.readopt_positions(state, {11: 501}, {501}, own) == []


def test_b_todays_own_fill_is_left_to_its_window_not_adopted_twice() -> None:
    state = {"date": "2026-09-25", "carried": {},
             "windows": {"asia": {"position_id": None,
                                  "orders": {"buy_stop": {"id": 12, "sl": 4285.0}}}}}
    own = e8_gold.own_entry_orders([], state)
    assert e8_gold.readopt_positions(state, {12: 600}, {600}, own) == []


# ----------------------------------------------------------------------- c. stale GTC entries

def test_c_yesterdays_resting_entry_is_stale_and_todays_and_foreign_orders_are_not() -> None:
    state = {"date": "2026-09-25", "carried": {},
             "windows": {"asia": {"orders": {"buy_stop": {"id": 21}, "sell_stop": {"id": 22}}}}}
    journal = [{"status": "SENT", "order_id": 20, "window": "afternoon", "side": "sell_stop"},
               {"status": "SENT", "order_id": 21, "window": "asia", "side": "buy_stop"}]
    own = e8_gold.own_entry_orders(journal, state)
    # 20: ours, from yesterday -> stale. 21/22: today's legs. 9001: a protective stop / foreign.
    assert e8_gold.stale_entry_orders(state, {20, 21, 22, 9001}, own) == [20]


# ----------------------------------------------------------------------- d. the minimum step

def test_d_a_one_tick_tightening_is_sent_and_a_sub_tick_one_is_not() -> None:
    assert pm.tightens_by_min_step(side=1, new_stop=4300.01, current_stop=4300.00, step=0.01)
    assert pm.tightens_by_min_step(side=-1, new_stop=4299.99, current_stop=4300.00, step=0.01)
    assert not pm.tightens_by_min_step(side=1, new_stop=4300.004, current_stop=4300.0, step=0.01)
    assert not pm.tightens_by_min_step(side=1, new_stop=4299.0, current_stop=4300.0, step=0.01)
    assert pm.tightens_by_min_step(side=1, new_stop=1.10001, current_stop=1.1, step=0.0)


def test_d_a_move_under_005r_is_no_longer_skipped() -> None:
    # A 20-point stop; the trail improves by 0.5 points = 0.025R, well under the old 0.05R floor.
    d = pm.RatchetDecision(4290.5, -0.5, -0.475, 4.0, False, "trail")
    assert d.improvement_r < 0.05
    assert pm.tightens_by_min_step(side=1, new_stop=float(d.new_stop), current_stop=4290.0,
                                   step=0.01)


def test_d_neither_money_path_consults_the_r_threshold() -> None:
    for path in (_GW, _DESK / "prop" / "e8_gold.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert "MIN_RATCHET_IMPROVEMENT_R" not in names, path.name
    assert "_pm.tightens_by_min_step(" in ast.unparse(_gw_function("manage_open_positions"))


# ----------------------------------------------------------------------- b + c through run()

def test_b_c_the_e8_pass_after_rollover_readopts_and_cancels_stale_legs(
        monkeypatch, tmp_path) -> None:
    import test_stop_rests_at_venue as harness

    for name in ("OUT", "GUARD", "LOG"):
        monkeypatch.setattr(e8_gold, name, tmp_path / f"{name.lower()}.json")
    intents = tmp_path / "intents.jsonl"
    intents.write_text("\n".join(json.dumps(r) for r in (
        {"status": "SENT", "order_id": 1, "window": "asia", "side": "sell_stop",
         "price": 4273.7, "sl": harness.EVENT["original_stop"], "tp": 4214.6, "lot": 0.16},
        {"status": "SENT", "order_id": 2, "window": "asia", "side": "buy_stop",
         "price": 4303.25, "sl": 4273.7, "tp": 4362.0, "lot": 0.16})) + "\n", encoding="utf-8")
    monkeypatch.setattr(e8_gold, "INTENTS", intents)
    state = tmp_path / "state.json"
    # Yesterday's state: the sell leg filled after the last pass, so no position_id was recorded.
    state.write_text(json.dumps({"date": "2026-09-23", "carried": {}, "windows": {"asia": {
        "orders": {"sell_stop": {"id": 1}, "buy_stop": {"id": 2}}, "position_id": None,
        "shadow": False, "placed_hour": 7.0}}}), encoding="utf-8")
    monkeypatch.setattr(e8_gold, "STATE", state)

    class _Api:
        @staticmethod
        def get_all_orders(history: bool = False, lookback_period: str = "") -> list:
            return [{"id": 1, "status": "Filled", "positionId": harness._POSITION_ID}]

    class _Venue(harness._GoldVenue):
        _api = _Api()

        def __init__(self, bid: float, ask: float) -> None:
            super().__init__(bid, ask)
            self.cancelled: list[int] = []

        def orders(self, symbol: str | None = None) -> list[dict]:
            return [*super().orders(symbol), {"id": 2, "stopPrice": 4303.25}]

        def cancel(self, order_id: int) -> bool:
            self.cancelled.append(int(order_id))
            return True

    venue = _Venue(4248.00, 4248.40)
    doc = e8_gold.run(venue, harness._MT5(), armed=True)
    acts = {a["act"] for a in doc["actions"]}
    assert "readopt" in acts, doc["actions"]
    assert venue.modified and venue.modified[0][0] == harness._POSITION_ID, \
        "the re-adopted position must be managed by the ratchet on the same pass"
    assert venue.cancelled == [2], "yesterday's resting GTC buy leg must be cancelled"
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert f"readopted:{harness._POSITION_ID}" in saved["carried"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
