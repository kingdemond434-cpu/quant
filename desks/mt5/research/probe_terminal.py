import MetaTrader5 as mt5

ok = mt5.initialize(path=r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe")
print("initialize:", ok)
if not ok:
    print("err:", mt5.last_error())
    raise SystemExit

acc = mt5.account_info()
print("account:", acc.login, "| server:", acc.server, "| currency:", acc.currency)
print("balance:", acc.balance, "| equity:", acc.equity, "| leverage:", acc.leverage)
print("margin_free:", acc.margin_free)

sym = mt5.symbol_info("XAUUSD")
if sym:
    print("XAUUSD: tick_value:", sym.trade_tick_value, "tick_size:", sym.trade_tick_size,
          "contract:", sym.trade_contract_size, "digits:", sym.digits,
          "min_vol:", sym.volume_min, "step:", sym.volume_step,
          "stops_level:", sym.trade_stops_level, "freeze:", sym.trade_freeze_level,
          "trade_mode:", sym.trade_mode)
tick = mt5.symbol_info_tick("XAUUSD")
print("tick: bid", tick.bid, "ask", tick.ask, "at", tick.time)

pos = mt5.positions_get()
print("positions:", len(pos) if pos else 0)
orders = mt5.orders_get()
print("pending orders:", len(orders) if orders else 0)

mt5.shutdown()