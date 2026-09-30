"""Probe the configured MT5 terminal (path from mt5desk.config).
Prints account, trade mode, algo toggle. If allow_send=1, sends a far-OTM
0.01 pending order and deletes it immediately (zero market risk) to prove
end-to-end order routing. Exit 0 = order routing works.

Both sends go through `mt5desk.order_door` (2026-09-30), so the probe is on the same ledger as
every other order. The removal used `mt5.order_delete`, which the MetaTrader5 package does not
have (see `gateway.cancel_pending`): every successful probe raised AttributeError and left its
0.01 buy stop resting GTC. It now removes with TRADE_ACTION_REMOVE and confirms the ticket is
gone from `orders_get`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk import order_door
from mt5desk.config import terminal_path

import MetaTrader5 as _mt5_venue

mt5 = order_door.guard(_mt5_venue, caller="probe_terminal")

allow_send = "allow_send=1" in " ".join(sys.argv[1:])

from mt5_session import attach_or_initialize
ok = attach_or_initialize(mt5, path=terminal_path())
print("init:", ok, mt5.last_error())
if not ok:
    sys.exit(2)
ti = mt5.terminal_info()
ai = mt5.account_info()
print("terminal:", ti.name)
print("account:", ai.login, "balance:", ai.balance, "equity:", ai.equity)
print("trade_mode:", ai.trade_mode, "(0=FULL 1=READONLY 2=CLOSEONLY 3=NO_TRADES)")
print("algo_allowed:", ti.trade_allowed)
if allow_send:
    s = mt5.symbol_info("XAUUSD")
    if s is None:
        print("XAUUSD not offered")
        sys.exit(3)
    req = {"action": mt5.TRADE_ACTION_PENDING, "symbol": "XAUUSD", "volume": 0.01,
           "type": mt5.ORDER_TYPE_BUY_STOP, "price": round(s.ask + 3000, 2),
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_RETURN,
           "deviation": 20, "comment": "PROBE", "magic": 999999}
    res = mt5.order_send(req)
    print("probe retcode:", res.retcode if res else None, res.comment if res else None)
    if res and res.retcode in (10008, 10009):
        left = []
        for o in mt5.orders_get(symbol="XAUUSD") or []:
            if o.magic == 999999:
                rm = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                gone = not any(x.ticket == o.ticket
                               for x in (mt5.orders_get(symbol="XAUUSD") or []))
                print("probe removed:" if gone else "probe NOT removed:", o.ticket,
                      "retcode", getattr(rm, "retcode", None))
                if not gone:
                    left.append(o.ticket)
        sys.exit(0 if not left else 4)
    sys.exit(1)
mt5.shutdown()
