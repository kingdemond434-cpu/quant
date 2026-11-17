import pandas as pd

raw = pd.read_parquet(r"C:\Users\dell\gold-desk\data\bars_vantage\XAUUSD_H1.parquet")
raw.index = pd.to_datetime(raw.index, utc=True)
raw = raw.sort_index()
print("H1 raw: hours present:", sorted(raw.index.hour.unique()))
print("last H1 raw bars (5):")
print(raw.tail(5).to_string())
print()
for tf in ["M5", "M15", "H4", "D1"]:
    d = pd.read_parquet(rf"C:\Users\dell\gold-desk\data\bars_vantage\XAUUSD_{tf}.parquet")
    d.index = pd.to_datetime(d.index, utc=True)
    d = d.sort_index()
    print(f"{tf}: min={d.index.min()} max={d.index.max()} last_hour={d.index[-1].hour}:{d.index[-1].minute}")
print()
# Friday close check: last H1 bar of the final Friday
fri = raw[raw.index.dayofweek == 4]
print("last Friday H1 bar:", fri.index[-1])
# weekday range check: is the last bar a weekend? (market closed -> if tz wrong, Friday appears as Sat/Sun)
print("last D1:", raw.index[-1], "dow=", raw.index[-1].dayofweek)