import pandas as pd
df = pd.read_parquet('data/universe/AUDNZD_H1.parquet')
print('AUDNZD bars:', len(df), 'last:', df.index.max())