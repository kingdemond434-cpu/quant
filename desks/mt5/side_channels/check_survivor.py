import json
d = json.load(open('/home/quant/quant-platform/desks/mt5/reports/UNIVERSAL_SURVIVORS.json'))
key = 'qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY'
surv = d.get('survivors', {}).get(key, {})
print(json.dumps(surv, indent=2))