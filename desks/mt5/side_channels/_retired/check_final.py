import pandas as pd
anc = pd.read_pickle('data/cross_asset_anchors.pkl')
print('T10YIE in cols:', 'T10YIE' in anc.columns)
if 'T10YIE' in anc.columns:
    print('T10YIE non-null:', anc['T10YIE'].dropna().shape[0])