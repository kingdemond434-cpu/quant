import sys, json, glob, os
sys.path.insert(0, "research"); sys.path.insert(0, ".")
from forward_verdict import (VERDICT_MIN_DAYS, VERDICT_MIN_TRADES, SEQ_MIN_TRADES,
                             MIN_EFFECTIVE_N, effective_n, sequential_lower_bound)

_FWD = {"forward", "FORWARD"}
rows = []
for f in glob.glob(os.path.join("reports", "shadow", "ledger_*.json")):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    trades = d.get("trades") if isinstance(d, dict) else d
    rs, days = [], set()
    for t in (trades or []):
        if not isinstance(t, dict) or t.get("phase") not in _FWD:
            continue
        r = t.get("r_multiple"); et = str(t.get("entry_time") or "")
        if r is None:
            continue
        rs.append(float(r)); days.add(et[:10])
    if len(rs) >= 3:
        neff, basis = effective_n(rs, sorted(days) if days else None)
        rows.append((os.path.basename(f)[7:-5], len(rs), len(days), neff,
                     sum(rs) / len(rs), sequential_lower_bound(rs)))
rows.sort(key=lambda r: -r[1])
print(f"  sleeves with >=3 forward trades: {len(rows)}")
print(f"  gates: days>={VERDICT_MIN_DAYS}, n>={VERDICT_MIN_TRADES} or (n>={SEQ_MIN_TRADES} & lb>0), n_eff>={MIN_EFFECTIVE_N}")
for name, n, nd, neff, exp, lb in rows[:8]:
    print(f"    {name[:38]:38s} n={n:<3} days={nd:<3} n_eff={neff:<5.1f} exp={exp:+.3f}R lb={lb:+.3f}")
if rows:
    print(f"  MEDIAN n_eff/n ratio: {sorted(r[3]/r[1] for r in rows)[len(rows)//2]:.2f}")
