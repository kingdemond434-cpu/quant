# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/meta_desk.py', 'r') as f:
    content = f.read()

# Fix the dead feature in drawdown forecaster
old_feats = '''        f = [float(corr21),
             float(np.mean(m.iloc[i - 21:i].std())),
             float(w.std() / (w.std() + 1e-12)),
             float((w.cumsum().max() - w.cumsum().iloc[-1]) / (w.std() + 1e-12))]'''
new_feats = '''        f = [float(corr21),
             float(np.mean(m.iloc[i - 21:i].std())),
             float(w.skew() / (w.std() + 1e-12)),  # skewness - more informative than dead 1.0
             float((w.cumsum().max() - w.cumsum().iloc[-1]) / (w.std() + 1e-12))]'''
content = content.replace(old_feats, new_feats)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/meta_desk.py', 'w') as f:
    f.write(content)

print("meta_desk.py drawdown forecaster fixed successfully")