p = r"C:\Users\dell\mt5-research\research\free_shadows.py"
s = open(p, encoding="utf-8").read()
reps = [
    ('fr["IR3TIB01JPM156N"]["value"].reindex(jpy_usd.index).ffill()',
     'ff_daily(fr["IR3TIB01JPM156N"]["value"], jidx)'),
    ('fr["DGS2"]["value"].reindex(jpy_usd.index).ffill()',
     'ff_daily(fr["DGS2"]["value"], jidx)'),
    ('fr["VIXCLS"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["VIXCLS"]["value"], xidx)'),
    ('fr["BAMLH0A0HYM2"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["BAMLH0A0HYM2"]["value"], xidx)'),
    ('fr["DFII10"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["DFII10"]["value"], xidx)'),
    ('fr["DTWEXBGS"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["DTWEXBGS"]["value"], xidx)'),
    ('fr["WALCL"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["WALCL"]["value"], xidx)'),
    ('fr["DEXUSAL"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["DEXUSAL"]["value"], xidx)'),
    ('fr["DEXCAUS"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["DEXCAUS"]["value"], xidx)'),
    ('fr["DEXUSNZ"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["DEXUSNZ"]["value"], xidx)'),
    ('fr["PCOPPUSDM"]["value"].reindex(xau.index).ffill()',
     'ff_daily(fr["PCOPPUSDM"]["value"], xidx)'),
    ('pd.read_parquet(UNI / "XAGUSD_H1.parquet").sort_index()["close"].reindex(xau.index).ffill()',
     'ff_daily(pd.read_parquet(UNI / "XAGUSD_H1.parquet").sort_index()["close"], xidx)'),
]
for old, new in reps:
    assert old in s, f"MISSING: {old}"
    s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("patched", len(reps))