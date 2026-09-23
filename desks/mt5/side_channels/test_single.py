import sys
sys.path.insert(0, '/home/quant/quant-platform/desks/mt5')
import json
import pandas as pd
from pathlib import Path

import research.run_hunt17 as rh17
rh17._ANC = None
import mt5desk.families as mf
if hasattr(mf, '_ANC'):
    mf._ANC = None

from research.universal_gate import Cell, gauntlet, costs_for
from research.run_hunt17 import FAMILIES, resample
from mt5desk import families

BASE = Path('/home/quant/quant-platform/desks/mt5')
UNI = BASE / 'data' / 'universe'
REPORTS = BASE / 'reports'

meta = json.loads((UNI / 'universe.json').read_text())

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
    sigs = fn(h4, d1, side, **params)
    if not sigs:
        continue
    cid = sym + '.' + fam + '.' + str(side)
    cst = costs_for(sym, meta)
    cells.append(Cell(cid, sym, h4, sigs, cst))

print('h18-004: ' + str(len(cells)) + ' cells built')
if cells:
    res = gauntlet(cells, 'hunt18_h18-004')
    nv = len(res.get('verdicts', []))
    ns = sum(1 for v in res.get('verdicts', []) if v.get('passed'))
    print('Result: n=' + str(nv) + ', survivors=' + str(ns))