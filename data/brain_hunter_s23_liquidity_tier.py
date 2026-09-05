"""BRAIN HUNTER s23 -- s22 NEXT-GROUND item 2.

BRAIN stratifies its universe as {REGION}_{DELAY}_{LIQUIDITY-TIER}. The desk's own
251-symbol MT5 registry declares NEITHER a delay dimension nor a liquidity tier, so
every screen runs one undifferentiated pool. This probe measures what a tiering would
separate, using ONLY registry fields + on-disk H1 closes. Research-frozen: reads only.
"""
from __future__ import annotations
import json, statistics
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "desks/mt5/data/universe/universe.json"
BARS = ROOT / "desks/mt5/data/universe"

reg = json.loads(REG.read_text())
rows = []
for sym, r in reg.items():
    digits = r.get("digits")
    spread = r.get("median_spread_pts")
    px = None
    f = BARS / f"{sym}_H1.parquet"
    if f.exists():
        try:
            df = pd.read_parquet(f, columns=["close"])
            if len(df):
                px = float(df["close"].tail(500).median())
        except Exception:
            px = None
    cost_bps = None
    if px and digits is not None and spread is not None and px > 0:
        cost_bps = (spread * (10.0 ** -digits)) / px * 1e4
    rows.append(
        dict(symbol=sym, asset_class=r.get("asset_class"), bars=r.get("bars"),
             digits=digits, median_spread_pts=spread, price=px,
             one_way_cost_bps=cost_bps)
    )

have = [r for r in rows if r["one_way_cost_bps"] is not None]
zero = [r for r in have if r["one_way_cost_bps"] == 0.0]
priced = [r for r in have if r["one_way_cost_bps"] > 0]
priced.sort(key=lambda r: r["one_way_cost_bps"])

def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]

costs = [r["one_way_cost_bps"] for r in priced]
n_t = max(1, len(priced) // 4)
tiers = {f"T{i+1}": priced[i * n_t:(i + 1) * n_t] if i < 3 else priced[3 * n_t:]
         for i in range(4)}

out = dict(
    n_symbols=len(rows),
    n_costable=len(have),
    n_zero_spread=len(zero),
    zero_spread_symbols=[r["symbol"] for r in zero],
    n_no_bars=sum(1 for r in rows if r["price"] is None),
    n_no_spread=sum(1 for r in rows if r["median_spread_pts"] is None),
    n_no_asset_class=sum(1 for r in rows if not r["asset_class"]),
    cost_bps=dict(min=min(costs), p25=q(costs, .25), median=q(costs, .5),
                  p75=q(costs, .75), p90=q(costs, .90), max=max(costs),
                  ratio_max_over_median=max(costs) / q(costs, .5)),
    tiers={k: dict(n=len(v),
                   cost_bps_range=[v[0]["one_way_cost_bps"], v[-1]["one_way_cost_bps"]],
                   asset_class_mix={c: sum(1 for r in v if (r["asset_class"] or "UNCLASSIFIED") == c)
                                    for c in sorted({(r["asset_class"] or "UNCLASSIFIED") for r in v})},
                   examples=[r["symbol"] for r in v[:6]])
           for k, v in tiers.items()},
    by_asset_class={
        c: dict(n=sum(1 for r in priced if (r["asset_class"] or "UNCLASSIFIED") == c),
                median_cost_bps=statistics.median(
                    [r["one_way_cost_bps"] for r in priced if (r["asset_class"] or "UNCLASSIFIED") == c]))
        for c in sorted({(r["asset_class"] or "UNCLASSIFIED") for r in priced})},
)
print(json.dumps(out, indent=1))
(ROOT / "data/brain_hunter_s23_liquidity_tier.json").write_text(json.dumps(out, indent=1))
