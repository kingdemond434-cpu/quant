import pandas as pd
anc = pd.read_pickle('data/cross_asset_anchors.pkl')
print('T10YIE non-null:', anc['T10YIE'].dropna().shape[0] if 'T10YIE' in anc.columns else 0)
print('freq:', anc.index.freq)
print('range:', anc.index.min(), '->', anc.index.max())