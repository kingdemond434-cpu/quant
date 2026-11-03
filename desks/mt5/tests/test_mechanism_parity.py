"""THE PARITY GATE: every account runs the same position mechanisms (zuck 2026-11-03 19:58Z: "ftmo
fusion etc must always have same mechanisms all etc as other accounts all must be just as same as
each other").

Measured that day: the Fusion gateway ratcheted every open stop (break-even floor + chandelier),
E8 ran the same ratchet on gold and the floor on its sleeves, while FTMO's gold lane only copied
E8's acknowledged stop and FTMO's sleeve lane ran no stop management at all. Nothing failed when
the lanes drifted, so they drifted. This fails the build when a module that opens positions is
not a registered lane, when a lane's manager stops calling its shared decision, or when the
Fusion gateway and `mt5_manage.stop_move` (FTMO and every prop account) ever decide differently.
A firm's own limits gate entries and sizes in each lane; they never change WHICH mechanisms run.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import mt5_manage as mm  # noqa: E402

#: module (relative to desks/mt5) -> (the managing function, the shared calls it must make)
LANES: dict[str, tuple[str, tuple[str, ...]]] = {
    # the Fusion gateway keeps its own inline copy; test_the_gateway_decides_like_the_shared_one
    # holds the two to the same decisions
    "mt5desk/gateway.py": ("manage_open_positions", ("_pm.ratchet", "_pm.stop_rests_at_venue")),
    "prop/ftmo_follower.py": ("native_stop", ("_mm.stop_move",)),
    "prop/ftmo_executor.py": ("protect", ("_mm.stop_move",)),
    "prop/e8_gold.py": ("trail_decision", ("_pm.ratchet",)),
    "prop/e8_executor.py": ("manage_breakeven", ("_pm.breakeven_armed", "_pm.breakeven_level")),
}

#: Modules that send orders but are not a lane: the order door is the guard every lane's sends go
#: through, and position_manager is the shared decision itself (it sends nothing; it names the
#: actions in prose).
NOT_LANES: dict[str, str] = {
    "mt5desk/order_door.py": "the guard every lane's sends pass through, not a lane",
    "mt5desk/position_manager.py": "the shared stop decision itself",
}

#: What marks a module as one that opens positions (MT5 request actions, TradeLocker place calls).
OPENS_POSITIONS: tuple[str, ...] = ("TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING", "venue.place",
                                   ".place(")


#: account -> its lanes. Folded in from the superseded account-parity draft (#630): the lane test
#: above proves each MANAGER calls the shared decision; this proves each ACCOUNT carries every
#: mechanism across its lanes, so a firm cannot go live missing one.
ACCOUNTS: dict[str, tuple[str, ...]] = {
    "fusion": ("mt5desk/gateway.py",),
    "e8": ("prop/e8_gold.py", "prop/e8_executor.py"),
    "ftmo": ("prop/ftmo_follower.py", "prop/ftmo_executor.py"),
}

#: mechanism -> source markers; an account has it when any of its lanes holds any marker. There
#: is no exemption list: a firm's caps are parameters of a mechanism, never a reason to skip it.
MECHANISMS: dict[str, tuple[str, ...]] = {
    "trail_and_breakeven_ratchet": ("_pm.ratchet(", "_mm.stop_move(", "trail_decision("),
    "fixed_bracket_breakeven_floor": ("floor_only=", "_pm.breakeven_armed("),
    "stop_rests_at_venue": ("stop_rests_at_venue(", "_mm.stop_move("),
    "opposite_side_fence": ("opposite_block(", "ftmo_block(", "_xa."),
    "order_door": ("order_door",),
}

#: Anything that sends to a venue: a MetaTrader send, a venue stop modify or a placement.
_SENDS = ("order_send(", ".modify_stop(", ".place(")


def _calls(fn: ast.FunctionDef) -> set[str]:
    out = set()
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)):
            out.add(f"{node.func.value.id}.{node.func.attr}")
    return out


def test_every_module_that_opens_positions_is_a_registered_lane() -> None:
    found = set()
    for sub in ("prop", "mt5desk"):
        for f in sorted((_DESK / sub).glob("*.py")):
            src = f.read_text("utf-8")
            if any(m in src for m in OPENS_POSITIONS):
                found.add(f.relative_to(_DESK).as_posix())
    unregistered = found - set(LANES) - set(NOT_LANES)
    assert not unregistered, (
        f"{sorted(unregistered)} open positions but are no lane in mechanism_parity.LANES: a new "
        f"account lane must run the same management as every other account")
    assert set(LANES) <= found, "a registered lane no longer opens positions: update LANES"


@pytest.mark.parametrize("path", sorted(LANES))
def test_each_lane_manages_through_the_shared_decision(path: str) -> None:
    fn_name, required = LANES[path]
    tree = ast.parse((_DESK / path).read_text("utf-8"))
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn_name]
    assert fns, f"{path}: the managing function {fn_name} is gone"
    missing = set(required) - _calls(fns[0])
    assert not missing, f"{path}:{fn_name} no longer calls {sorted(missing)}"


def test_every_mt5_lane_calls_the_one_mt5_decision() -> None:
    """Fusion, FTMO gold, FTMO sleeves (and every prop account, which runs the FTMO modules)."""
    mt5_lanes = [p for p in LANES if "ftmo" in p]
    assert all("_mm.stop_move" in LANES[p][1] for p in mt5_lanes)
    assert len(mt5_lanes) == 2


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
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True,
                       commission_per_lot_side=None)
    assert move.new_stop is not None and move.new_stop >= 100.0 and move.breakeven_floor


def test_a_trade_short_of_the_trigger_keeps_its_stop() -> None:
    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[100.3, 100.5],
                             lows=[99.8, 100.1], bid=100.4, ask=100.42)
    assert mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True,
                       commission_per_lot_side=None).new_stop is None


def test_a_level_behind_the_market_is_never_sent() -> None:
    # the floor is earned, but price has fallen back under it: a stop there is a market exit
    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[101.2, 100.2],
                             lows=[100.0, 99.9], bid=99.95, ask=99.97)
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True,
                       commission_per_lot_side=None)
    assert move.new_stop is None


def test_a_short_gets_the_mirror_image() -> None:
    mt5, p, info = _terminal(side=-1, entry=100.0, sl=101.0, highs=[100.2, 99.6],
                             lows=[99.5, 98.8], bid=98.98, ask=99.0)
    move = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=True,
                       commission_per_lot_side=None)
    assert move.new_stop is not None and move.new_stop <= 100.0


def test_the_initial_risk_is_captured_once_and_kept() -> None:
    store: dict = {}
    assert mm.original_stop_distance(store, 7, 100.0, 99.0, None) == (1.0, True)
    # the stop has moved since: R stays measured against the opening risk
    assert mm.original_stop_distance(store, 7, 100.0, 100.2, None) == (1.0, False)
    assert mm.original_stop_distance(store, 8, 100.0, 0.0, None) == (None, False)
    # first seen AFTER a move (open at deploy, or re-stopped by hand): the opening order's stop
    # is the risk, never the moved one (audit SF2)
    assert mm.original_stop_distance(store, 9, 100.0, 100.5, 98.0) == (2.0, True)


def test_the_opening_facts_are_the_accounts_own() -> None:
    mt5 = SimpleNamespace(
        history_orders_get=lambda position: [SimpleNamespace(time_setup=2, sl=99.5),
                                             SimpleNamespace(time_setup=1, sl=98.0)],
        history_deals_get=lambda position: [
            SimpleNamespace(entry=0, volume=0.5, commission=-1.25),
            SimpleNamespace(entry=1, volume=0.5, commission=-1.25)])
    assert mm.opening_facts(mt5, 7) == (98.0, 2.5)
    broken = SimpleNamespace(history_orders_get=lambda position: None,
                             history_deals_get=lambda position: 1 / 0)
    assert mm.opening_facts(broken, 7) == (None, None)


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
    new, why, failed = ff.native_stop(mt5, {}, p)
    assert new is not None and new <= 100.0 and not failed, why


# ------------------------------------------- the Fusion gateway decides exactly like the shared one

def _gateway_exec() -> object:
    spec = importlib.util.spec_from_file_location("_gw_harness", _DESK / "tests" /
                                                  "test_gateway_adapter.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._exec


@pytest.mark.parametrize("floor_only", [True, False])
@pytest.mark.parametrize(("side", "highs", "lows", "bid"), [
    (1, [100.5, 101.2], [99.8, 100.4], 101.0),      # a long winner past the trigger
    (1, [100.3, 100.5], [99.8, 100.1], 100.4),      # short of the trigger
    (1, [101.2, 100.2], [100.0, 99.9], 99.95),      # earned, then fell back behind the level
    (-1, [100.2, 99.6], [99.5, 98.8], 98.98),       # a short winner
    (1, [101.0, 102.5, 103.4], [99.9, 100.8, 102.0], 103.0),  # a runner the trail can follow
])
def test_the_gateway_decides_like_the_shared_one(side: int, highs: list[float],
                                                  lows: list[float], bid: float,
                                                  floor_only: bool) -> None:
    entry, sl = 100.0, (99.0 if side == 1 else 101.0)
    mt5, p, info = _terminal(side=side, entry=entry, sl=sl, highs=highs, lows=lows,
                             bid=bid, ask=bid + 0.02)
    # one bar series serves every timeframe, so both read the same history
    t0 = p.time
    bars = [{"time": t0 - 3600 * (40 - i), "open": entry, "high": entry + 1.0,
             "low": entry - 1.0, "close": entry} for i in range(40)]
    bars += [{"time": t0 + 60 * i, "open": entry, "high": h, "low": lo, "close": entry}
             for i, (h, lo) in enumerate(zip(highs, lows, strict=True))]
    mt5.copy_rates_from_pos = lambda sym, tf, start, n: bars
    mt5.TRADE_ACTION_SLTP = 6
    mt5.symbol_info = lambda sym: info
    p.comment = "DWfam_x" if floor_only else "DWgold_asia"
    sent: list[dict] = []
    mt5.positions_get = lambda symbol=None, ticket=None: [p] if symbol in (None, "XAUUSD") else []
    mt5.order_send = lambda req: (sent.append(req), SimpleNamespace(retcode=10009, comment=""))[1]
    logs: list[str] = []
    ns = _gateway_exec()(("manage_open_positions", "order_comment", "_original_stop_distance",
                          "_rates_since_position", "_round_trip_per_price_unit"),
                         {"mt5": mt5, "log": logs.append, "MAGIC": 1, "_pm": mm._pm})
    st = {"armed": True, "generic": {"fam_x": {"trail_k": 0.0}} if floor_only else {}}
    sleeves = [{"name": "fam_x", "symbol": "XAUUSD", "exec": "family_market"}] if floor_only else []
    ns["manage_open_positions"](st, sleeves)
    gw = sent[0]["sl"] if sent else None
    shared = mm.stop_move(mt5, p, info, original_dist=1.0, floor_only=floor_only,
                         commission_per_lot_side=None).new_stop
    assert gw == shared, (gw, shared, logs)
    if bid in (101.0, 98.98, 103.0):  # the winners: the comparison is never vacuous
        assert gw is not None, logs


def test_a_mirror_equal_to_the_venue_stop_sends_nothing() -> None:
    """Desk health 2026-11-03: after a mirror the follower re-sent the same stop every minute
    ("sl unchanged"), each one spent from FTMO's daily request budget."""
    from prop import ftmo_follower as ff

    assert not ff._pm.tightens_by_min_step(side=-1, new_stop=3952.66 - 1e-9,
                                           current_stop=3952.66, step=0.01)
    assert ff._pm.tightens_by_min_step(side=-1, new_stop=3951.60, current_stop=3952.66,
                                       step=0.01)
    src = (_DESK / "prop" / "ftmo_follower.py").read_text("utf-8")
    assert "NO NO-OP MODIFIES" in src and "tightens_by_min_step(side=1 if side ==" in src


def test_a_decided_no_move_keeps_ftmo_s_own_stop_not_e8_s(monkeypatch) -> None:
    """Audit of 730b0952c MF: E8's acknowledged stop is the fallback only when FTMO's own decision
    could not be MADE. A decided "no move" (floor not reached) keeps FTMO's stop even when E8's is
    tighter, exactly as Fusion's would stay -- the tighter of two mechanisms is a third one."""
    from prop import ftmo_follower as ff

    mt5, p, info = _terminal(side=1, entry=100.0, sl=99.0, highs=[100.3, 100.5],
                             lows=[99.8, 100.1], bid=100.4, ask=100.42)
    mt5.symbol_info = lambda sym: info
    new, why, failed = ff.native_stop(mt5, {}, p)
    assert new is None and not failed, why
    # the follower's use of it: only `failed` opens the mirror
    src = (_DESK / "prop" / "ftmo_follower.py").read_text("utf-8")
    assert "new, how, failed = native_stop(mt5, st, p)" in src
    assert "if new is None and failed:" in src
    # and a read that could not be made does report failure
    mt5.symbol_info = lambda sym: None
    assert ff.native_stop(mt5, {}, p)[2] is True


def test_every_order_sender_belongs_to_an_account() -> None:
    owned = {f for lanes in ACCOUNTS.values() for f in lanes} | set(NOT_LANES)
    senders = {f.relative_to(_DESK).as_posix()
               for sub in ("prop", "mt5desk") for f in sorted((_DESK / sub).glob("*.py"))
               if any(m in f.read_text("utf-8") for m in _SENDS)}
    stray = sorted(senders - owned)
    assert not stray, f"{stray} can send orders but belong to no account in ACCOUNTS"
    assert set(LANES) == {f for lanes in ACCOUNTS.values() for f in lanes}


@pytest.mark.parametrize("account", sorted(ACCOUNTS))
def test_every_account_runs_every_mechanism(account: str) -> None:
    text = "\n".join((_DESK / f).read_text("utf-8") for f in ACCOUNTS[account])
    missing = [m for m, marks in MECHANISMS.items() if not any(mk in text for mk in marks)]
    assert not missing, (f"account {account!r} does not run {missing}: every live account runs "
                         f"the same mechanisms (zuck 2026-11-03)")
