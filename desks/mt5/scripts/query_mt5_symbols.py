import MetaTrader5 as mt5
import json, time

mt5.initialize()
info = mt5.terminal_info()
print(f"Terminal: {info.name}, build={info.build}, connected={info.connected}")

syms = mt5.symbols_get()
print(f"\nTotal symbols from broker: {len(syms)}")

cats = {}
for s in syms:
    path = s.path.replace("\\", "/")
    parts = path.split("/")
    cat = parts[0] if len(parts) > 1 else "Root"
    cats.setdefault(cat, []).append(s)

for cat in sorted(cats):
    items = cats[cat]
    print(f"\n{'='*60}")
    print(f"  {cat} ({len(items)} symbols)")
    print(f"{'='*60}")
    for s in sorted(items, key=lambda x: x.name):
        vis = "V" if s.visible else "-"
        trade = "T" if s.trade_mode > 0 else " "
        cs = getattr(s, "trade_contract_size", 1)
        print(f"  {vis}{trade} {s.name:25s} point={s.point:<12} digits={s.digits} "
              f"spread={s.spread:>5} contract={cs}")

# Save full data
all_data = {}
for s in syms:
    if s.visible and s.trade_mode > 0:
        all_data[s.name] = {
            "point": s.point,
            "digits": s.digits,
            "spread": s.spread,
            "contract_size": getattr(s, "trade_contract_size", 1),
            "volume_min": s.volume_min,
            "path": s.path,
        }

with open(r"C:\Users\dell\mt5-research\data\mt5_all_symbols.json", "w") as f:
    json.dump(all_data, f, indent=2)
print(f"\nSaved {len(all_data)} visible+tradable symbols")

mt5.shutdown()
