import subprocess

# Write a query script to VPS and run it
query = r"""
import MetaTrader5 as mt5
import json

mt5.initialize()
syms = mt5.symbols_get()
print(f"TOTAL: {len(syms)}")

# Group by category
cats = {}
for s in syms:
    # s.path looks like "Forex\EURUSD" or "Indices\US500" etc
    parts = s.path.replace("\\", "/").split("/")
    cat = parts[0] if len(parts) > 1 else "Root"
    cats.setdefault(cat, []).append({
        "name": s.name,
        "visible": s.visible,
        "trade_mode": s.trade_mode,
        "point": s.point,
        "volume_min": s.volume_min,
        "contract_size": getattr(s, "trade_contract_size", 1),
        "spread": getattr(s, "spread", 0),
        "digits": s.digits,
    })

for cat in sorted(cats):
    items = cats[cat]
    print(f"\n=== {cat} ({len(items)}) ===")
    for s in sorted(items, key=lambda x: x["name"]):
        vis = "V" if s["visible"] else "-"
        trade = "T" if s["trade_mode"] > 0 else "-"
        print(f"  {vis}{trade} {s['name']:20s} point={s['point']} digits={s['digits']} "
              f"spread={s['spread']} contract={s['contract_size']}")

mt5.shutdown()
"""

r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cat > /tmp/list_symbols.py << 'PYEOF'\n" + query + "\nPYEOF"],
    capture_output=True, text=True, timeout=10
)
print("Written to VPS:", r.returncode)

r2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "/home/quant/quant-platform/.venv/bin/python /tmp/list_symbols.py 2>&1"],
    capture_output=True, text=True, timeout=60
)
print(r2.stdout)
if r2.stderr:
    print("ERR:", r2.stderr[:1000])
