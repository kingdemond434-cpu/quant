#!/usr/bin/env python3
from pathlib import Path

from libs.research.paper_sleeves import parse_screen_verdicts

r = parse_screen_verdicts(Path('/home/quant/quant-platform/reports/axis_screens'))
print('Status:', r['status'])
perpdex = [c for c in r['candidates'] if 'perpdex' in c.name.lower() or c.mechanism == 'perpdex_funding']
print(f'Perpdex candidates: {len(perpdex)}')
for c in perpdex:
    print(f'  {c.name}: {c.verdict} ({c.mechanism}) ic_t={c.ic_t} ic={c.ic} sharpe={c.sharpe_corrected}')
