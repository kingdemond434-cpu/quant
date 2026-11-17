# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/macro_desk.py', 'r') as f:
    content = f.read()

# Fix the _mom function to use calendar-appropriate lookbacks
old_mom = '''def _mom(x: pd.Series, yoy: bool = False) -> float | None:
    s = x.dropna()
    if len(s) < 260:
        return None
    look = 252 if yoy else 252
    if s.iloc[-1] == 0 or np.isnan(s.iloc[-look]):
        return None
    base = s.iloc[-look]
    if base == 0:
        return None
    return float((s.iloc[-1] - base) / abs(base))'''

new_mom = '''def _mom(x: pd.Series, yoy: bool = False) -> float | None:
    s = x.dropna()
    if len(s) < 12:
        return None
    # Determine lookback based on series frequency and yoy flag
    # Monthly series: YoY = 12 months, regular momentum = 12 months
    # Daily series: YoY = 252 days, regular momentum = 63 days (~3 months)
    freq = _infer_freq(s)
    if freq == "M":
        look = 12 if yoy else 12
        min_obs = 24
    elif freq == "D":
        look = 252 if yoy else 63
        min_obs = 260 if yoy else 120
    elif freq == "W":
        look = 52 if yoy else 13
        min_obs = 104 if yoy else 26
    else:
        # Default fallback
        look = 12 if yoy else 12
        min_obs = 24
    
    if len(s) < min_obs:
        return None
    if s.iloc[-1] == 0 or np.isnan(s.iloc[-look]):
        return None
    base = s.iloc[-look]
    if base == 0:
        return None
    return float((s.iloc[-1] - base) / abs(base))


def _infer_freq(s: pd.Series) -> str:
    """Infer frequency from index spacing."""
    if len(s) < 3:
        return "M"
    idx = s.index
    diffs = [(idx[i+1] - idx[i]).days for i in range(min(10, len(idx)-1))]
    median_diff = sorted(diffs)[len(diffs)//2]
    if median_diff <= 2:
        return "D"
    elif median_diff <= 10:
        return "W"
    else:
        return "M"'''

content = content.replace(old_mom, new_mom)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/macro_desk.py', 'w') as f:
    f.write(content)

print("macro_desk.py momentum fixed successfully")