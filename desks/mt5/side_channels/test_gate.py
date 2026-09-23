import sys
import importlib
sys.path.insert(0, '.')
import pandas as pd
import json
from pathlib import Path

# Force reload anchors directly - bypass run_hunt17 cache
ANC_PATH = Path('data/cross_asset_anchors.pkl')
anc = pd.read_pickle(ANC_PATH)
print('Direct load T10YIE:', 'T10YIE' in anc.columns)
if 'T10YIE' in anc.columns:
    t10 = anc['T10YIE'].dropna()
    print('T10YIE range:', t10.index.min(), '->', t10.index.max(), 'non-null:', len(t10))

# Clear cached modules
for mod in list(sys.modules.keys()):
    if 'run_hunt17' in mod or 'mt5desk.families' in mod:
        del sys.modules[mod]

from research.run_hunt17 import FAMILIES, resample
import mt5desk.families
importlib.reload(mt5desk.families)
from mt5desk import families

from research.universal_gate import Cell, gauntlet, costs_for

BASE = Path('.').resolve()
UNI = BASE / 'data' / 'universe'
REPORTS = BASE / 'reports'

rp = REPORTS / 'hunt18_h18-004.json'
rpt = json.loads(rp.read_text())
fam = rpt['family']
params = rpt['params']
side = 1 if rpt['side'] == 'LONG' else -1
fn = FAMILIES[fam]

cells = []
for c in rpt.get('all', []):
    sym = c['sym']
    if not (UNI / f'{sym}_H1.parquet').exists():
        continue
    h1 = families._h1(pd.read_parquet(UNI / f'{sym}_H1.parquet'))
    h4, d1 = resample(h1)
    sigs = fn(h4, d1, side, **params)
    if not sigs:
        continue
    meta = json.loads((UNI / 'universe.json').read_text())
    cells.append(Cell(f'{sym}.{fam}.{side}', sym, h4, sigs, costs_for(sym, meta)))

print(f'h18-004: {len(cells)} cells built')
if cells:
    res = gauntlet(cells, 'hunt18_h18-004')
    print(f'Result: n={len(res.get("verdicts",[]))}, survivors={sum(1 for v in res.get("verdicts",[]) if v.get("passed"))}')