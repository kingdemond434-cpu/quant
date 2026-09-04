"""Every certified edge as a structural fingerprint, clustered, so disguised duplicates show.

Fifty sleeves that all monetise the same USD-London-breakout shock are one business with fifty
names. The allocator already measures that through realised correlation and through currency
factor exposure; both are STATISTICAL and both can miss a duplicate whose overlap has not yet
shown up in the sample. This is the STRUCTURAL view: what each edge IS, before it has traded.

THE GENOME. Per certified cell, from the certificate and the family registry, never from its
returns:

    instrument, asset class, currency legs
    family, mechanism class (breakout / reversion / carry / residual / trend / plumbing / ...)
    direction bias, holding period (family TTL), entry clock (session or hour)
    factor exposures the driver map implies (economic_drivers roles it would load)
    source (which miner or proposer found it)

CLUSTERING. Two edges are in the same cluster when they share mechanism class, direction bias,
entry clock AND at least one currency leg or factor role. That is deliberately coarse: the
question is not "are these identical" but "would they lose money on the same day for the same
reason". The output is N_clusters against N_sleeves, and per cluster the sleeves in it -- which
is what a research allocator should read to decide where the book is thin.

CONSUMED BY `regime_coverage` (as a second definition of "never tried here": by cluster rather
than by family name) and by the allocator artifact, where `n_clusters` is reported beside
`k_eff` so the two independence numbers can be compared.
"""
from __future__ import annotations

import argparse
import functools
import json
import operator
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
OUT = BASE / "reports" / "ALPHA_GENOME.json"

#: Family -> mechanism class. DECLARED: it is a statement about what each family's cause is, and
#: a family missing here is reported as UNCLASSIFIED rather than guessed.
MECHANISM_CLASS: dict[str, str] = {
    "session_range_breakout": "breakout", "level_breakout": "breakout",
    "failed_breakout": "reversion", "asia_momentum": "trend", "momentum_volgate": "trend",
    "london_close_momentum": "trend", "multi_speed_trend": "trend",
    "overnight_gap_decay": "reversion", "monday_gap": "reversion", "dow_effect": "calendar",
    "turn_of_month": "calendar", "calendar_month": "calendar",
    "carry": "carry", "relative_value": "residual", "cross_asset_residual": "residual",
    "pca_residual": "residual", "correlation_regime": "residual",
    "vol_transition": "volatility", "vol_mean_reversion": "volatility",
    "liquidity_regime": "microstructure", "orderflow_imbalance": "microstructure",
    "spread_state": "microstructure", "clock_transition": "plumbing",
    "cot_positioning": "positioning", "macro_conditional": "macro", "event_reaction": "event",
    "regime_transition": "regime", "drawdown_conditional": "regime", "ensemble": "ensemble",
    "discovered": "discovered", "generic": "generic", "fair_value_gap": "reversion",
    "dav_range_filter_adx": "breakout",
}

DIRECTION_BIAS = {"trend": "with", "breakout": "with", "reversion": "against",
                  "residual": "against", "volatility": "with", "carry": "neutral"}


def _legs(sym: str, meta: dict) -> tuple[str, ...]:
    row = meta.get(sym) or {}
    cls = str(row.get("asset_class") or "")
    if cls in {"Forex", "Forex Exotics"} and len(sym) == 6:
        return (sym[:3], sym[3:])
    q = str(row.get("currency_profit") or "USD")
    return (q,)


def _factor_roles(sym: str, meta: dict) -> tuple[str, ...]:
    try:
        from mt5desk.economic_drivers import driver_sets
        roles = set()
        for ds in driver_sets(sym, meta, set(meta)):
            for d in ds.drivers:
                for role, cands in __import__("mt5desk.economic_drivers",
                                              fromlist=["ROLES"]).ROLES.items():
                    if d in cands:
                        roles.add(role)
        return tuple(sorted(roles))
    except Exception:
        return ()


def _family_of(cert: dict, key: str) -> str:
    fam = (cert.get("shadow_spec") or {}).get("family") or cert.get("family")
    if fam:
        return str(fam)
    cell = str(cert.get("cell") or key)
    parts = cell.split(".")
    return parts[1] if len(parts) > 1 else cell


def _clock_of(cert: dict, key: str) -> str:
    sel = (cert.get("shadow_spec") or {}).get("selector")
    if sel:
        return str(sel)
    low = key.lower()
    for tag in ("asia", "london", "afternoon", "ny", "overnight", "morning"):
        if tag in low:
            return tag
    return "any"


def genome(meta: dict) -> dict[str, dict]:
    try:
        canon = json.loads(CANON.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for key, cert in (canon.get("survivors") or {}).items():
        if not isinstance(cert, dict):
            continue
        sym = str(cert.get("sym") or (cert.get("shadow_spec") or {}).get("symbol") or "").upper()
        fam = _family_of(cert, key)
        mech = MECHANISM_CLASS.get(fam, "UNCLASSIFIED")
        row = meta.get(sym) or {}
        out[key] = {"symbol": sym, "asset_class": str(row.get("asset_class") or ""),
                    "legs": list(_legs(sym, meta)), "family": fam, "mechanism": mech,
                    "direction_bias": DIRECTION_BIAS.get(mech, "unknown"),
                    "clock": _clock_of(cert, key), "factor_roles": list(_factor_roles(sym, meta)),
                    "source": str(cert.get("hunt") or ""),
                    "status": str(cert.get("status") or "PASS")}
    return out


def cluster(g: dict[str, dict]) -> dict[str, list[str]]:
    """Coarse structural clusters: same mechanism, bias, clock, and a shared leg or role."""
    keys = list(g)
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(keys):
        ga = g[a]
        for b in keys[i + 1:]:
            gb = g[b]
            if (ga["mechanism"], ga["direction_bias"], ga["clock"]) != \
                    (gb["mechanism"], gb["direction_bias"], gb["clock"]):
                continue
            shared = (set(ga["legs"]) & set(gb["legs"])) or \
                     (set(ga["factor_roles"]) & set(gb["factor_roles"]))
            if shared or ga["symbol"] == gb["symbol"]:
                parent[find(a)] = find(b)
    clusters: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        clusters[find(k)].append(k)
    named = {}
    for root, members in clusters.items():
        g0 = g[root]
        name = f"{g0['mechanism']}/{g0['direction_bias']}/{g0['clock']}/" \
               f"{'+'.join(sorted(set(functools.reduce(operator.iadd, (g[m]['legs'] for m in members), []))))[:40]}"
        named[name] = sorted(members)
    return named


def run() -> dict:
    from research import proposer_common as pc
    meta = pc.universe_meta()
    g = genome(meta)
    active = {k: v for k, v in g.items() if v["status"] in ("PASS", "")}
    cl = cluster(active)
    by_mech: dict[str, int] = defaultdict(int)
    for v in active.values():
        by_mech[v["mechanism"]] += 1
    biggest = sorted(cl.items(), key=lambda kv: -len(kv[1]))[:8]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_sleeves": len(active),
           "n_clusters": len(cl),
           "structural_breadth": round(len(cl) / max(1, len(active)), 3),
           "by_mechanism": dict(by_mech),
           "unclassified_families": sorted({v["family"] for v in active.values()
                                            if v["mechanism"] == "UNCLASSIFIED"}),
           "largest_clusters": [{"cluster": k, "n": len(v), "members": v[:10]} for k, v in biggest],
           "clusters": cl, "genome": active}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"ALPHA GENOME  {d['n_sleeves']} sleeves -> {d['n_clusters']} structural clusters "
          f"(breadth {d['structural_breadth']:.2f})")
    print(f"  by mechanism: {d['by_mechanism']}")
    for c in d["largest_clusters"]:
        print(f"  {c['n']:3d}  {c['cluster']}")
    if d["unclassified_families"]:
        print(f"  UNCLASSIFIED families: {d['unclassified_families']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
