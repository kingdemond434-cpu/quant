# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/options_desk.py', 'r') as f:
    content = f.read()

# Fix the IV unit error: Deribit mark_iv is in percentage (e.g., 80), need to convert to decimal (0.80)
# Fix in surface() function where atm_iv is extracted
old_atm_iv = '''            "atm_iv": float(atm["iv"]), "skew": skew, "term_slope": term,'''
new_atm_iv = '''            "atm_iv": float(atm["iv"]) / 100.0, "skew": skew, "term_slope": term,'''
content = content.replace(old_atm_iv, new_atm_iv)

# Also fix the term_slope calculation which uses atm_iv
old_atm_iv_func = '''        def atm_iv(e):
            sub = df[df["exp"] == e]
            return float(sub.iloc[(sub["strike"] - idx).abs().argsort()].iloc[0]["iv"])'''
new_atm_iv_func = '''        def atm_iv(e):
            sub = df[df["exp"] == e]
            return float(sub.iloc[(sub["strike"] - idx).abs().argsort()].iloc[0]["iv"]) / 100.0'''
content = content.replace(old_atm_iv_func, new_atm_iv_func)

# Also fix skew calculation which uses iv directly
old_skew = '''    skew = None
    if not calls.empty and not puts.empty:
        skew = float(calls["iv"].mean() - puts["iv"].mean())'''
new_skew = '''    skew = None
    if not calls.empty and not puts.empty:
        skew = float(calls["iv"].mean() - puts["iv"].mean()) / 100.0'''
content = content.replace(old_skew, new_skew)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/options_desk.py', 'w') as f:
    f.write(content)

print("options_desk.py IV unit fixed successfully")