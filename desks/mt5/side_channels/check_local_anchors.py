import pandas as pd
anc = pd.read_pickle('data/cross_asset_anchors.pkl')
print('columns:', list(anc.columns))
print('rows:', len(anc), 'range:', anc.index.min(), '->', anc.index.max())
if 'T10YIE' in anc.columns:
    t = anc['T10YIE'].dropna()
    print('T10YIE non-null:', len(t), 'last:', t.iloc[-1])