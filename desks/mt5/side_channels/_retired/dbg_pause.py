import pandas as pd

m5 = pd.read_parquet(r"C:\Users\dell\gold-desk\data\bars_vantage\XAUUSD_M5.parquet")
m5.index = pd.to_datetime(m5.index, utc=True)
m5 = m5.sort_index()

h = m5.index.hour
print("M5 hours present:", sorted(h.unique()))
print("M5 hour counts:")
print(h.value_counts().sort_index().to_string())

m15 = pd.read_parquet(r"C:\Users\dell\gold-desk\data\bars_vantage\XAUUSD_M15.parquet")
m15.index = pd.to_datetime(m15.index, utc=True)
m15 = m15.sort_index()
print("M15 hours present:", sorted(m15.index.hour.unique()))

h1 = pd.read_parquet(r"C:\Users\dell\gold-desk\data\bars_vantage\XAUUSD_H1.parquet")
h1.index = pd.to_datetime(h1.index, utc=True)
h1 = h1.sort_index()
# is 21:00 missing every year?
print("H1 hour-21 bars per year:", h1[h1.index.hour == 21].groupby(h1[h1.index.hour == 21].index.year).size().to_dict())

# 22:00 bars per year (does 22 exist consistently?)
print("H1 hour-22 bars per year:", h1[h1.index.hour == 22].groupby(h1[h1.index.hour == 22].index.year).size().to_dict())

# daily pause check: for a sample week in 2026, list M5 gaps around 20:50-22:10
wk = m5.loc["2026-08-10":"2026-08-14"]
gaps = wk.index[wk.index.hour.isin([20, 21, 22])]
print("2026-08-10..14 M5 bars at 20/21/22h:")
print(gaps.to_series().dt.strftime("%m-%d %H:%M").tolist())