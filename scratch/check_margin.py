#!/usr/bin/env python3
from libs.execution import binance_margin_live as m
try:
    print('armed:', m.is_armed())
    acct = m.account()
    print('account keys:', list(acct.keys()))
    print('marginLevel:', acct.get('marginLevel'))
    print('totalNetAssetOfBtc:', acct.get('totalNetAssetOfBtc'))
    print('userAssets:', acct.get('userAssets', [])[:3])
except Exception as e:
    print('Error:', e)