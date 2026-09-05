from pathlib import Path
REPORTS = Path('/home/quant/quant-platform/desks/mt5/reports')
for rp in sorted(REPORTS.glob('hunt18_*.json')):
    marker = REPORTS / f'DONE_universal_{rp.stem}'
    print(rp.name, 'marker exists:', marker.exists())