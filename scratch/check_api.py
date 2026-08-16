#!/usr/bin/env python3
from libs.execution import binance_margin_live as m
try:
    acct = m.account()
    print('SUCCESS!')
    print('marginLevel:', acct.get('marginLevel'))
    print('totalNetAssetOfBtc:', acct.get('totalNetAssetOfBtc'))
    print('totalAssetOfBtc:', acct.get('totalAssetOfBtc'))
    print('totalLiabilityOfBtc:', acct.get('totalLiabilityOfBtc'))
    print('userAssets count:', len(acct.get('userAssets', [])))
    for a in acct.get('userAssets', [])[:5]:
        print(f"  {a.get('asset')}: free={a.get('free')}, borrowed={a.get('borrowed')}, interest={a.get('interest')}")
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()