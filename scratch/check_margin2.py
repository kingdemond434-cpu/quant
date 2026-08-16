#!/usr/bin/env python3
from libs.execution import binance_margin_live as m
print('armed:', m.is_armed())
print('margin level:', m.margin_level())
bal = m.balances()
print('non-zero balances:')
for k, v in bal.items():
    if v > 0:
        print(f'  {k}: {v}')
owed = m.liabilities()
print('liabilities:')
for k, v in owed.items():
    if v > 0:
        print(f'  {k}: {v}')