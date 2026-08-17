"""Probe the configured MT5 terminal (path from mt5desk.config).
Prints account, trade mode, algo toggle. If allow_send=1, sends a far-OTM
0.01 pending order and deletes it immediately (zero market risk) to prove
end-to-end order routing. Exit 0 = order routing works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import terminal_path

import MetaTrader5 as mt5

allow_send = "allow_send=1" in " ".join(sys.argv[1:])

ok = mt5.initialize(path=terminal_path())
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
    if res and res.retcode == 10009:
        for o in mt5.orders_get(symbol="XAUUSD") or []:
            if o.magic == 999999:
                mt5.order_delete(o.ticket)
                print("probe deleted:", o.ticket)
        sys.exit(0)
    sys.exit(1)
mt5.shutdown()