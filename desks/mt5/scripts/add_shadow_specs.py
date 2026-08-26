import json
from pathlib import Path

path = Path('/home/quant/quant-platform/desks/mt5/reports/UNIVERSAL_SURVIVORS.json')
data = json.loads(path.read_text('utf-8'))

gauntlet = json.loads(Path('/home/quant/quant-platform/desks/mt5/reports/universal_gates_external.json').read_text('utf-8'))

count = 0
for v in gauntlet['verdicts']:
    if not v['passed']:
        continue
    cell = v['cell']
    sym = v['sym']
    key = 'external.' + cell
    if key not in data['survivors']:
        continue
    spec = {
        'symbol': sym,
        'selector': 'asia',
        'family': 'session_range_breakout',
        'is_universe': True,
        'hunt': 'external_discoveries',
        'condition': None,
    }
    data['survivors'][key]['shadow_spec'] = spec
    count += 1
    print('Added shadow_spec: ' + key)

path.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
print('Updated ' + str(path) + ' - ' + str(count) + ' specs added')
