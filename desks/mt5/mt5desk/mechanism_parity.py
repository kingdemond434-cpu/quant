"""EVERY ACCOUNT RUNS THE SAME MECHANISMS: the registry the parity gate holds each lane to.

WHY (zuck 2026-11-03 19:58Z: "ftmo fusion etc must always have same mechanisms all etc as other
accounts all must be just as same as each other"). Measured that day: the Fusion gateway ratcheted
every open stop (break-even floor + chandelier), E8 ran the same ratchet on gold and the floor on
its sleeves, while FTMO's gold lane only copied E8's acknowledged stop and FTMO's sleeve lane ran
no stop management at all. Nothing failed when the lanes drifted, so they drifted.

THE RULE. Every module that opens positions on any account is a LANE here, and each lane names
the function that manages its open positions and the shared decision that function must call:
  * MT5 lanes (Fusion, FTMO, every prop account the fleet runs) call `mt5_manage.stop_move`, the
    one decision: the break-even floor for a fixed-bracket certificate, plus the chandelier
    otherwise;
  * TradeLocker lanes (E8) cannot use MT5 bars, so they call the same `position_manager` core
    that `stop_move` wraps: `ratchet` on gold, `breakeven_armed` + `breakeven_level` on sleeves.
A firm's own limits (daily loss, max loss, profit caps) gate entries and sizes in each lane; they
never change WHICH mechanisms run. `tests/test_mechanism_parity.py` fails the build when an
order-sending module is missing here or a lane's manager stops calling its shared decision.
"""
from __future__ import annotations

#: module (relative to desks/mt5) -> (the managing function, the shared calls it must make)
LANES: dict[str, tuple[str, tuple[str, ...]]] = {
    "mt5desk/gateway.py": ("manage_open_positions", ("_mm.stop_move",)),
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
OPENS_POSITIONS = ("TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING", "venue.place", ".place(")
