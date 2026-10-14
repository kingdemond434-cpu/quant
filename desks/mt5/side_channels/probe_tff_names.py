import sys
from pathlib import Path

# The desk's one TFF loader (the stale desks/mt5/fetch_tff.py duplicate was deleted 2026-10-14).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mt5desk.fetch_tff import load_year

df = load_year(2024)
names = df["Market_and_Exchange_Names"].astype(str)
for tok in ["DOLLAR", "SILVER"]:
    hits = sorted({n for n in names if tok in n.upper()})
    print(tok, "->", hits[:15])
