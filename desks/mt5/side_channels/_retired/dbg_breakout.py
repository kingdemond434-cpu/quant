from mt5desk.data import load_gold
from mt5desk.families import _h1

gold = load_gold()
h1 = _h1(gold.h1)
h1 = h1.assign(date=h1.index.date, hour=h1.index.hour)
print("bars:", len(h1), h1.index.min(), "->", h1.index.max())
print("hour==7 count:", int((h1["hour"] == 7).sum()))
print("hour counts top:", h1["hour"].value_counts().head(10).to_dict())

rg = (
    h1.loc[h1["hour"] < 7]
    .groupby("date")
    .agg(hi=("high", "max"), lo=("low", "min"))
)
print("range days:", len(rg))
print(rg.tail(3).to_string())

sig_rows = h1.loc[h1["hour"] == 7]
print("sig bars:", len(sig_rows))
outside = []
for ts, row in sig_rows.iterrows():
    if ts.date() in rg.index:
        hi = float(rg.at[ts.date(), "hi"])
        lo = float(rg.at[ts.date(), "lo"])
        if row["open"] > hi or row["open"] < lo:
            outside.append((ts, row["open"], hi, lo))
print("outside fires:", len(outside))
for x in outside[:10]:
    print(x)