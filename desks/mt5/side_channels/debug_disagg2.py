import sys
sys.path.insert(0, r"C:\Users\dell\mt5-research\mt5desk")
from fetch_cot_disagg import fetch_contract

df = fetch_contract("GOLD")
print("returned:", "None" if df is None else len(df))
if df is not None:
    print(df[["report_date", "contract_market_name", "futonly_or_combined"]].head(2).to_string())
    print(df["futonly_or_combined"].value_counts().to_string()[:200])