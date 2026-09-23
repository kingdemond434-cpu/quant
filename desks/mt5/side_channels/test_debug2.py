import sys
sys.path.insert(0, '/home/quant/quant-platform/desks/mt5')
import json
import pandas as pd
from pathlib import Path

import research.run_hunt17 as rh17
rh17._ANC = None

orig_anchors = rh17._anchors_df
def debug_anchors():
    result = orig_anchors()
    print('DEBUG _anchors_df: T10YIE=' + str('T10YIE' in result.columns) + ', non-null=' + str(result['T10YIE'].dropna().shape[0] if 'T10YIE' in result.columns else 0))
    return result
rh17._anchors_df = debug_anchors

from research.run_hunt17 import FAMILIES, resample
from mt5desk import families
from research.universal_gate import Cell, gauntlet, costs_for

BASE = Path('/home/quant/quant-platform/desks/mt5')
UNI = BASE / 'data' / 'universe'
REPORTS = BASE / 'reports'

meta = json.loads((BASE / 'data' / 'universe' / 'universe.json').read_text())

rp = REPORTS / 'hunt18_h18-004.json'
rpt = json.loads(rp.read_text())
fam = rpt['family']
params = rpt['params']
side = 1 if rpt['side'] == 'LONG' else -1
fn = FAMILIES[fam]

cells = []
for c in rpt.get('all', []):
    sym = c['sym']
    p = UNI / (sym + '_H1.parquet')
    if not p.exists():
        continue
    h1 = families._h1(pd.read_parquet(p))
    h4, d1 = resample(h1)
    if sym == 'XAUUSD':
        print('XAUUSD h4 range: ' + str(h4.index.min()) + ' -> ' + str(h4.index.max()) + ' len=' + str(len(h4)))
        print('XAUUSD h4 tz: ' + str(h4.index.tz))
    sigs = fn(h4, d1, 1, n=34, rr=2.0, ttl=12, yield_z=0.0)
    if not sigs:
        print('  XAUUSD: NO SIGNALS')
        continue
    print('  XAUUSD: ' + str(len(sigs)) + ' signals')
    cid = 'XAUUSD.macro_gold_yield.1'
    cells.append(Cell(cid, 'XAUUSD', h4, sigs, costs_for('XAUUSD', meta)))

print('h18-004: ' + str(len(cells)) + ' cells built')
if cells:
    res = gauntlet(cells, 'hunt18_h18-004')
    print('Result: n=' + str(len(res.get('verdicts',[]))) + ', survivors=' + str(sum(1 for v in res.get('verdicts',[]) if v.get('passed'))))