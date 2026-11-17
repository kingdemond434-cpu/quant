import sys
sys.path.insert(0, r"C:\Users\dell\mt5-research\mt5desk")
from fetch_tff import load_year

df = load_year(2024)
names = df["Market_and_Exchange_Names"].astype(str)
for tok in ["DOLLAR", "SILVER"]:
    hits = sorted(set(n for n in names if tok in n.upper()))
    print(tok, "->", hits[:15])