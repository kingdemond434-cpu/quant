#!/usr/bin/env python3
from libs.execution import binance_spot_live as s
try:
    orders = s.open_orders()
    print('Open orders:', len(orders))
    for o in orders:
        print(f'  {o["symbol"]}: {o["side"]} {o["origQty"]} @ {o.get("price", "MARKET")} ({o["status"]})')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()