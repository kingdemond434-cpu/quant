#!/usr/bin/env python3
from libs.execution import binance_spot_live as s
try:
    bal = s.balances()
    print('Spot balances (non-zero):')
    for k, v in bal.items():
        if v > 0:
            print(f'  {k}: {v}')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()