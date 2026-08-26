import subprocess, json

# Get universe symbols
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cat /home/quant/quant-platform/desks/mt5/data/universe/universe.json"],
    capture_output=True, text=True, timeout=15
)
uni = json.loads(r.stdout)
print(f"Current universe: {len(uni)} symbols")
for k in sorted(uni.keys()):
    m = uni[k]
    print(f"  {k:12s} tick={m.get('tick_size','?')} contract={m.get('contract_size','?')} spread={m.get('median_spread_pts','?')}")

# Get parquet files
r2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "ls /home/quant/quant-platform/desks/mt5/data/universe/*_H1.parquet 2>/dev/null | xargs -I{} basename {} _H1.parquet | sort"],
    capture_output=True, text=True, timeout=15
)
pqlist = r2.stdout.strip().split("\n") if r2.stdout.strip() else []
print(f"\nParquet files: {len(pqlist)}")
for p in pqlist:
    tag = "MISSING" if p not in uni else "ok"
    print(f"  {p:12s} {tag}")

# Check what MT5 can offer
r3 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && PYTHONPATH=desks/mt5 .venv/bin/python -c '"
     "from mt5desk.engine import mt5; "
     "mt5.initialize(); "
     "syms = mt5.symbols_get(); "
     "print(len(syms), \"total_symbols\"); "
     "cats = {}; "
     "for s in syms: "
     "    cat = s.path.split(chr(92))[0] if chr(92) in s.path else s.path.split(chr(47))[0]; "
     "    cats.setdefault(cat, []).append(s.name); "
     "for c in sorted(cats): print(c, len(cats[c])); "
     "mt5.shutdown(); "
     "'"],
    capture_output=True, text=True, timeout=30
)
print(f"\nMT5 broker symbols:\n{r3.stdout[:3000]}")
if r3.stderr:
    print(f"ERR: {r3.stderr[:500]}")
