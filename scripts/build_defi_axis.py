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
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.axis_integrity import check_coverage, coverage_bar  # noqa: E402

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
            series.append((d, bor / sup, len(daily[d])))

    # THE SECOND WAY AN AGGREGATE STOPS BEING COMPARABLE TO ITSELF (R0390). A ratio of two
    # collapsed sums stays perfectly in range, so a census failure is INVISIBLE on the value
    # axis: live on this series, n_pools ran 6691 -> 2511 -> 566 -> 6538 while every day still
    # wrote a z20 that run_axis_shadows booked as a position. 566 of ~6800 pools is 92% of the
    # aggregate missing. An unmeasurable day booked as evidence is worse than a missing one.
    #
    # A short-coverage day is kept with z20=null and its reason, NOT dropped: _evaluate counts a
    # null-z row `unusable` and structurally cannot take a position on it, so the refusal is
    # enforced and stays visible on disk (L1.60 -- a skip nobody counted is indistinguishable
    # from a scope filter). It is also excluded from every later z-window, because a
    # non-comparable level poisons the next _Z days as well as its own row.
    #
    # The floor is derived from STRICTLY PRIOR counts, so a collapse can never lower the floor
    # it is judged against, and no day is scored using a census that had not happened yet.
    rows = []
    clean: list[float] = []
    for i, (d, u, n_pools) in enumerate(series):
        cov = check_coverage(n_pools, coverage_bar([c for _, _, c in series[:i]]))
        if not cov.ok:
            rows.append({"date": d, "utilisation": round(u, 6), "z20": None,
                         "n_pools": n_pools, "refused": cov.reason})
            continue
        w = [*clean[-(_Z - 1):], u]
        z = 0.0
        if len(w) >= 5:
            sd = st.pstdev(w)
            z = (u - st.fmean(w)) / sd if sd > 0 else 0.0
        clean.append(u)
        rows.append({"date": d, "utilisation": round(u, 6), "z20": round(z, 4),
                     "n_pools": n_pools})

    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    print("=== DEFI UTILISATION AXIS FEED ===")
    print(f"  {len(rows)} daily observations from {sum(len(v) for v in daily.values())} pool-rows")
    refused = [r for r in rows if r.get("z20") is None]
    for r in rows[-3:]:
        z = "REFUSED (null)" if r["z20"] is None else f"{r['z20']:+.3f}"
        print(f"    {r['date']}  util {r['utilisation']:.4f}  z20 {z}  pools {r['n_pools']}")
    if refused:
        print(f"\n  COVERAGE REFUSALS: {len(refused)}/{len(rows)} days written with z20=null "
              f"(kept visible, un-bookable by the evaluator):")
        for r in refused:
            print(f"    {r['date']}  {r['refused']}")
    print("\n  system utilisation = TOTAL borrow / TOTAL supply, not a mean of per-pool ratios --")
    print("  a mean over-weights tiny pools and would let a $2m vault move the axis.")
    print(f"  z20 needs 5+ days before it is meaningful; currently {len(rows)}.")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
