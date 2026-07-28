"""DeFi system-utilisation AXIS FEED -- turn the pool-level collector into a Stage-B clock input.

WHY THIS AXIS AND NOT TWO CHEAP ONES. Stage-B slots are scarce by arithmetic (Holm bar 2.39 at
m=3, 2.58 at m=5), so a slot spent on a badly-constructed feed taxes every other clock for nothing.
One well-built axis beats two registered-and-broken.

CONSTRUCTION, stated so it can be falsified:
  observable  aggregate DeFi utilisation = total borrow / total supply across Aave, Compound,
              Morpho and Spark on Ethereum
  mechanism   M_FORCED_DELEVERAGE -- the desk's best-supported mechanism (2/10 survival, holds
              the only confirmed edge). Utilisation climbing toward the rate kink squeezes
              marginal borrowers; forced unwind is spot selling that perps reflect later.
  transform   z20 of daily utilisation -- level is meaningless across regimes, deviation is not
  direction   -1. High utilisation = leverage crowded = FRAGILE, so the prior is that extreme
              utilisation precedes weakness, not strength. Stated in advance; the clock decides.
  falsifier   IC indistinguishable from zero, or sign opposite to the stated prior, over 40 days
              under the Holm bar.

The evaluator needs ONE row per date carrying a pre-computed z field. The collector writes ~286
pool rows per hour, so this aggregates: hour -> daily system utilisation -> rolling z20.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data/defi_lending.jsonl"
OUT = ROOT / "data/defi_util_axis.jsonl"
_Z = 20


def main() -> None:
    if not SRC.exists():
        raise SystemExit("collector has produced nothing yet")
    daily: dict[str, list[tuple[float, float]]] = {}
    with SRC.open("r", encoding="utf-8", errors="ignore") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            d = str(r.get("ts", ""))[:10]
            s, b = r.get("supply_usd"), r.get("borrow_usd")
            if d and isinstance(s, (int, float)) and isinstance(b, (int, float)) and s > 0:
                daily.setdefault(d, []).append((float(s), float(b)))

    # SYSTEM utilisation = total borrow / total supply, never a mean of per-pool ratios --
    # a mean of ratios over-weights tiny pools and would make a $2m vault move the axis.
    series = []
    for d in sorted(daily):
        sup = sum(x[0] for x in daily[d])
        bor = sum(x[1] for x in daily[d])
        if sup > 0:
            series.append((d, bor / sup))

    rows = []
    for i, (d, u) in enumerate(series):
        w = [v for _, v in series[max(0, i - _Z + 1):i + 1]]
        z = 0.0
        if len(w) >= 5:
            sd = st.pstdev(w)
            z = (u - st.fmean(w)) / sd if sd > 0 else 0.0
        rows.append({"date": d, "utilisation": round(u, 6), "z20": round(z, 4),
                     "n_pools": len(daily[d])})

    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    print("=== DEFI UTILISATION AXIS FEED ===")
    print(f"  {len(rows)} daily observations from {sum(len(v) for v in daily.values())} pool-rows")
    for r in rows[-3:]:
        print(f"    {r['date']}  util {r['utilisation']:.4f}  z20 {r['z20']:+.3f}  "
              f"pools {r['n_pools']}")
    print("\n  system utilisation = TOTAL borrow / TOTAL supply, not a mean of per-pool ratios --")
    print("  a mean over-weights tiny pools and would let a $2m vault move the axis.")
    print(f"  z20 needs 5+ days before it is meaningful; currently {len(rows)}.")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
