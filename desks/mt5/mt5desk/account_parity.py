"""EVERY LIVE ACCOUNT RUNS THE SAME MECHANISMS: the registry the CI parity gate enforces.

zuck, 2026-11-03 19:58Z (standing rule): "ftmo fusion etc must always have same mechanisms all
etc as other accounts all must be just as same as each other". The accounts differ only in each
firm's rule caps (daily loss, max loss, profit cap, request budget, lot cap). Everything that
decides or protects a trade is the same machinery.

`tests/test_account_parity.py` enforces this table, so it cannot drift silently:

  * every file that can send an order (a MetaTrader send, a venue stop modify or a placement)
    belongs to an account below, so a new account or lane cannot go live outside the gate;
  * every account has every MECHANISM: at least one of its lanes carries one of the mechanism's
    markers. A gap fails CI. There is no exemption list: a firm's rule caps are parameters of
    the mechanism, not an excuse to skip it;
  * the shared MetaTrader ratchet (`mt5desk.mt5_ratchet.wanted_stop`) and the gateway's own
    `manage_open_positions` send the same stop on the same terminal, bar for bar.

To add an account, list its lanes here. To add a mechanism, list its markers here. CI then says
which accounts are still missing it.
"""
from __future__ import annotations

#: account -> the files (relative to desks/mt5) that trade or manage it.
LIVE_ACCOUNTS: dict[str, tuple[str, ...]] = {
    "fusion": ("mt5desk/gateway.py",),
    "e8": ("prop/e8_gold.py", "prop/e8_executor.py"),
    "ftmo": ("prop/ftmo_follower.py", "prop/ftmo_executor.py"),
}

#: Files that send orders on behalf of every lane and belong to no single account.
SHARED_SENDERS: frozenset[str] = frozenset({"mt5desk/order_door.py"})

#: mechanism -> source markers; an account has it when any of its lanes contains any marker.
MECHANISMS: dict[str, tuple[str, ...]] = {
    # the chandelier trail composed with the costed break-even floor, never loosening
    "trail_and_breakeven_ratchet": ("_pm.ratchet(", "_ratchet.wanted_stop(",
                                    "trail_decision("),
    # a fixed-bracket certificate gets the break-even floor and never the trail
    "fixed_bracket_breakeven_floor": ("floor_only=", "_pm.breakeven_armed("),
    # a stop level must rest on the right side of the market before it is sent
    "stop_rests_at_venue": ("stop_rests_at_venue(", "_ratchet.wanted_stop("),
    # no account may hold the opposite side of another account's position
    "opposite_side_fence": ("opposite_block(", "ftmo_block(", "_xa.", "cross_account"),
    # every send goes through the logged, never-silent order door
    "order_door": ("order_door",),
}
