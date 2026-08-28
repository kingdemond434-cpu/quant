import subprocess, json

# 1. Get current universe
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cat /home/quant/quant-platform/desks/mt5/data/universe/universe.json"],
    capture_output=True, text=True, timeout=15
)
uni = json.loads(r.stdout)
print(f"=== Current universe: {len(uni)} symbols ===")
for k in sorted(uni.keys()):
    m = uni[k]
    print(f"  {k:12s} tick={m.get('tick_size','?')} contract={m.get('contract_size','?')} spread_pts={m.get('median_spread_pts','?')}")

# 2. Get parquet files
r2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "ls /home/quant/quant-platform/desks/mt5/data/universe/*_H1.parquet 2>/dev/null | xargs -I{} basename {} _H1.parquet | sort"],
    capture_output=True, text=True, timeout=15
)
pqlist = r2.stdout.strip().split("\n") if r2.stdout.strip() else []
print(f"\n=== Parquet files: {len(pqlist)} ===")
missing = [p for p in pqlist if p not in uni]
for p in sorted(missing):
    print(f"  {p:12s} NO META")
if not missing:
    print("  All have meta")
