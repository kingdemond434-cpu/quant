import re

with open("/home/quant/quant-platform/desks/mt5/mt5desk/families.py", "r") as f:
    content = f.read()

# Find _h1 function start
start = content.find("def _h1(df: pd.DataFrame) -> pd.DataFrame:")
if start == -1:
    print("Function not found")
    exit(1)

# Find the end of function (next def or class at same indent)
end = content.find("\ndef ", start + 1)
if end == -1:
    end = len(content)

old_func = content[start:end]
print(f"Found function ({len(old_func)} chars)")

new_func = '''def _h1(df: pd.DataFrame) -> pd.DataFrame:
    """Resample to H1 if not already. The index leaves here tz-aware UTC, always.

    A producer rewrote the universe parquets with a tz-NAIVE datetime64[ms] index (caught
    2026-08-27: every comparison against an aware stamp -- lookahead guards, forward boundaries,
    session windows -- raised or, worse, silently disagreed about which hour a bar is). Bars on
    this desk are broker-UTC by contract, so naive input is localized, aware input is converted,
    and no caller ever has to guess again.
    """
    if len(df) == 0:
        return df
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = (df.index.tz_localize("UTC") if df.index.tz is None
                    else df.index.tz_convert("UTC"))
    if hasattr(df.index, "freq") and df.index.freq is not None:
        return df
    freq = pd.infer_freq(df.index)
    if freq and freq.upper().startswith("1H"):
        df.index = df.index.as_unit("ns")
        return df
    vol_col = "volume" if "volume" in df.columns else "tick_volume"
    agg = {
        "open": "first", "high": "max", "low": "min", "close": "last",
    }
    if vol_col in df.columns:
        agg[vol_col] = "sum"
    resampled = df.resample("1h").agg(agg).dropna()
    resampled.index = resampled.index.as_unit("ns")
    return resampled
'''

content = content[:start] + new_func + content[end:]

with open("/home/quant/quant-platform/desks/mt5/mt5desk/families.py", "w") as f:
    f.write(content)

print("Done")