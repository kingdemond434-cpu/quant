"""THE PARITY GATE: every account runs the same position mechanisms (zuck 2026-11-03).

`mt5desk.mechanism_parity` is the registry; this fails the build when a module that opens
positions is not a registered lane, when a lane's manager stops calling its shared decision, or
when the shared decision itself stops protecting a winner the same way on every MT5 account.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import mechanism_parity as mp  # noqa: E402
from mt5desk import mt5_manage as mm  # noqa: E402


def _calls(fn: ast.FunctionDef) -> set[str]:
    out = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                out.add(f"{node.func.value.id}.{node.func.attr}")
    return out


def test_every_module_that_opens_positions_is_a_registered_lane() -> None:
    found = set()
    for sub in ("prop", "mt5desk"):
        for f in sorted((_DESK / sub).glob("*.py")):
            src = f.read_text("utf-8")
            if any(m in src for m in mp.OPENS_POSITIONS):
                found.add(f.relative_to(_DESK).as_posix())
    unregistered = found - set(mp.LANES) - set(mp.NOT_LANES)
    assert not unregistered, (
        f"{sorted(unregistered)} open positions but are no lane in mechanism_parity.LANES: a new "
        f"account lane must run the same management as every other account")
    assert set(mp.LANES) <= found, "a registered lane no longer opens positions: update LANES"


@pytest.mark.parametrize("path", sorted(mp.LANES))
def test_each_lane_manages_through_the_shared_decision(path: str) -> None:
    fn_name, required = mp.LANES[path]
    tree = ast.parse((_DESK / path).read_text("utf-8"))
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn_name]
    assert fns, f"{path}: the managing function {fn_name} is gone"
    missing = set(required) - _calls(fns[0])
    assert not missing, f"{path}:{fn_name} no longer calls {sorted(missing)}"


def test_every_mt5_lane_calls_the_one_mt5_decision() -> None:
    """Fusion, FTMO gold, FTMO sleeves (and every prop account, which runs the FTMO modules)."""
    mt5_lanes = [p for p in mp.LANES if p.startswith("mt5desk/") or "ftmo" in p]
    assert all("_mm.stop_move" in mp.LANES[p][1] for p in mt5_lanes)
    assert len(mt5_lanes) == 3


# ------------------------------------------------- the shared decision, as every account sees it

def _terminal(*, side: int, entry: float, sl: float, highs: list[float], lows: list[float],
              bid: float, ask: float) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    t0 = 1_800_000_000 - (1_800_000_000 % 60)
    m1 = [{"time": t0 + 60 * i, "open": entry, "high": h, "low": lo, "close": entry}
          for i, (h, lo) in enumerate(zip(highs, lows, strict=True))]
    h1 = [{"time": t0 - 3600 * (40 - i), "open": entry, "high": entry + 1.0,
           "low": entry - 1.0, "close": entry} for i in range(40)]
    mt5 = SimpleNamespace(
        POSITION_TYPE_BUY=0, TIMEFRAME_M1=1, TIMEFRAME_H1=16385,
        copy_rates_from_pos=lambda sym, tf, start, n: m1 if tf == 1 else h1,
        symbol_info_tick=lambda sym: SimpleNamespace(bid=bid, ask=ask))
    p = SimpleNamespace(ticket=7, symbol="XAUUSD", type=0 if side == 1 else 1, price_open=entry,
                        sl=sl, tp=0.0, time=t0)
    info = SimpleNamespace(trade_tick_value=1.0, trade_tick_size=0.01, point=0.01, spread=0,
                           trade_stops_level=0)
    return mt5, p, info


def test_a_winner_past_the_trigger_gets_the_break_even_floor() -> None:
    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[100.5, 101.2],
                             lows=[99.8, 100.4], bid=101.0, ask=101.02)
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True)
    assert move.new_stop is not None and move.new_stop >= 100.0 and move.breakeven_floor


def test_a_trade_short_of_the_trigger_keeps_its_stop() -> None:
    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[100.3, 100.5],
                             lows=[99.8, 100.1], bid=100.4, ask=100.42)
    assert mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True).new_stop is None


def test_a_level_behind_the_market_is_never_sent() -> None:
    # the floor is earned, but price has fallen back under it: a stop there is a market exit
    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[101.2, 100.2],
                             lows=[100.0, 99.9], bid=99.95, ask=99.97)
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True)
    assert move.new_stop is None


def test_a_short_gets_the_mirror_image() -> None:
    mt5, p, info = _terminal(side=-1, entry=100.0, sl=101.0, highs=[100.2, 99.6],
                             lows=[99.5, 98.8], bid=98.98, ask=99.0)
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True)
    assert move.new_stop is not None and move.new_stop <= 100.0


def test_the_initial_risk_is_captured_once_and_kept() -> None:
    store: dict = {}
    assert mm.original_stop_distance(store, 7, 100.0, 99.0) == (1.0, True)
    # the stop has moved since: R stays measured against the opening risk
    assert mm.original_stop_distance(store, 7, 100.0, 100.2) == (1.0, False)
    assert mm.original_stop_distance(store, 8, 100.0, 0.0) == (None, False)


# ------------------------------------------- the FTMO lanes run it on their own positions

def test_the_ftmo_sleeve_lane_sends_the_floor_on_its_own_position() -> None:
    from prop import ftmo_executor as fx

    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[100.5, 101.2],
                             lows=[99.8, 100.4], bid=101.0, ask=101.02)
    sent: list[dict] = []
    mt5.TRADE_ACTION_SLTP = 6
    mt5.symbol_info = lambda sym: info
    mt5.order_send = lambda req: (sent.append(req), SimpleNamespace(retcode=10009))[1]
    st: dict = {}
    doc: dict = {"actions": [], "alerts": []}
    fx.protect(mt5, st, doc, p, cet="2026-11-03", armed=True)
    (req,) = sent
    assert req["action"] == 6 and req["position"] == 7 and req["sl"] >= 100.0
    assert doc["actions"][0]["act"] == "breakeven_floor" and doc["actions"][0]["ok"]
    # shadow when unarmed: the decision is recorded, nothing is sent
    sent.clear()
    p.sl = 99.0
    doc = {"actions": [], "alerts": []}
    fx.protect(mt5, {}, doc, p, cet="2026-11-03", armed=False)
    assert sent == [] and doc["actions"][0].get("shadow")


def test_the_ftmo_gold_lane_manages_its_own_position_without_e8() -> None:
    from prop import ftmo_follower as ff

    mt5, p, info = _terminal(side=-1, entry=100.0, sl=101.0, highs=[100.2, 99.6],
                             lows=[99.5, 98.8], bid=98.98, ask=99.0)
    # gold runs the full ratchet, which reads H1: two hours since entry, the second a 1.2R run
    h0 = p.time - (p.time % 3600)
    h1 = [{"time": h0 - 3600 * (40 - i), "open": 100.0, "high": 101.0, "low": 99.0,
           "close": 100.0} for i in range(40)]
    h1 += [{"time": h0, "open": 100.0, "high": 100.2, "low": 99.5, "close": 99.6},
           {"time": h0 + 3600, "open": 99.6, "high": 99.6, "low": 98.8, "close": 98.99}]
    mt5.copy_rates_from_pos = lambda sym, tf, start, n: h1
    mt5.symbol_info = lambda sym: info
    new, why = ff.native_stop(mt5, {}, p)
    assert new is not None and new <= 100.0, why
