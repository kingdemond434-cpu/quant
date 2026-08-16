import json
from pathlib import Path
d = json.loads(Path("reports/hunt6_partial.json").read_text(encoding="utf-8"))
print("done:", d["done"])
print("test syms:", sorted({r["sym"] for r in d["all"]}))
trues = [r for r in d["all"] if r.get("gate") is True]
print("gate=True count:", len(trues))
if trues:
    for r in trues: print("  PASS", r["sym"], r["window"], r["variant"], round(r["expectancy_r"],3), round(r["t_stat"],2))
