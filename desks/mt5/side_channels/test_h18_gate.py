import sys
sys.path.insert(0, '/home/quant/quant-platform/desks/mt5')
import json
import pandas as pd
from pathlib import Path
from research.universal_gate import Cell, gauntlet, costs_for
from research.run_hunt17 import FAMILIES, resample
from mt5desk import families

BASE = Path('/home/quant/quant-platform/desks/mt5')
UNI = BASE / 'data' / 'universe'
REPORTS = BASE / 'reports'

meta = json.loads((UNI / 'universe.json').read_text())

for rp in sorted(REPORTS.glob('hunt18_*.json')):
    marker = REPORTS / f'DONE_universal_{rp.stem}'
    if marker.exists():
        print(f'{rp.stem}: marker exists, skipping')
        continue
    report = json.loads(rp.read_text('utf-8'))
    fam = report.get('family')
    if not fam:
        print(f'{rp.stem}: no family key')
        continue
    fn = FAMILIES.get(fam)
    if not fn:
        print(f'{rp.stem}: family {fam} not in FAMILIES')
        continue
    side = 1 if (report.get('side') or 'LONG') == 'LONG' else -1
    params = report.get('params') or {}
    print(f'{rp.stem}: fam={fam}, side={side}, params={params}')
    
    cells = []
    for c in report.get('all', []):
        sym = c.get('sym')
        if not (UNI / f'{sym}_H1.parquet').exists():
            continue
        h1 = families._h1(pd.read_parquet(UNI / f'{sym}_H1.parquet'))
        h4, d1 = resample(h1)
        try:
            sigs = fn(h4, d1, side, **params)
        except Exception as e:
            print(f'  {sym}: signal error: {e}')
            continue
        if not sigs:
            print(f'  {sym}: NO SIGNALS')
            continue
        cells.append(Cell(f'{sym}.{fam}.{side}', sym, h4, sigs, costs_for(sym, meta)))
    
    print(f'{rp.stem}: {len(cells)} cells built')
    if cells:
        res = gauntlet(cells, rp.stem)
        print(f'  Result: n={len(res.get("verdicts",[]))}, survivors={sum(1 for v in res.get("verdicts",[]) if v.get("passed"))}')