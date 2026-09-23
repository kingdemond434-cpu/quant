import sys
sys.path.insert(0, '/home/quant/quant-platform/desks/mt5')
import json
import pandas as pd
from pathlib import Path

import research.run_hunt17 as rh17
rh17._ANC = None

from research.run_hunt17 import FAMILIES, resample
from mt5desk import families
from research.universal_gate import Cell, gauntlet, costs_for

BASE = Path('/home/quant/quant-platform/desks/mt5')
UNI = BASE / 'data' / 'universe'
REPORTS = BASE / 'reports'

meta = json.loads((BASE / 'data' / 'universe' / 'universe.json').read_text())

for exp_id in ['hunt18_h18-005', 'hunt18_h18-006']:
    rp = REPORTS / f'{exp_id}.json'
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
        cells.append(Cell(cid, sym, h4, sigs, costs_for(sym, meta)))

    print(f'{exp_id}: {len(cells)} cells built')
    if cells:
        res = gauntlet(cells, exp_id)
        print(f'  Result: n={len(res.get("verdicts",[]))}, survivors={sum(1 for v in res.get("verdicts",[]) if v.get("passed"))}')