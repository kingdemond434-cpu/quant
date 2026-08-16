#!/usr/bin/env python3
from libs.execution import binance_spot_live as s
try:
    acct = s.account()
    print('Spot account:')
    for a in acct.get('balances', [])[:20]:
        free = float(a.get('free') or 0)
        locked = float(a.get('locked') or 0)
        if free > 0 or locked > 0:
            print(f'  {a["asset"]}: free={free}, locked={locked}')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()