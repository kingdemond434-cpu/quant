import pandas as pd
from research.run_hunt17 import fam_macro_gold_yield, resample, _anchors_df, families

anc = _anchors_df()
print('Anchors T10YIE:', 'T10YIE' in anc.columns)
if 'T10YIE' in anc.columns:
    t10 = anc['T10YIE'].dropna()
    print('T10YIE range:', t10.index.min(), '->', t10.index.max())

h1 = pd.read_parquet('/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet')
h4, d1 = resample(families._h1(h1))
print('h4 range:', h4.index.min(), '->', h4.index.max(), 'len:', len(h4))

sigs = fam_macro_gold_yield(h4, d1, 1, n=34, rr=2.0, ttl=12, yield_z=0.0)
print('LONG signals:', len(sigs))
if sigs:
    print('First:', sigs[0])
    print('Last:', sigs[-1])

sigs_s = fam_macro_gold_yield(h4, d1, -1, n=34, rr=2.0, ttl=12, yield_z=0.0)
print('SHORT signals:', len(sigs_s))