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
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import mechanism_genome as mg  # noqa: E402
from libs.research.strategy_artifact import feature_ids_of  # noqa: E402

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
        spec = cert.get("shadow_spec") or {}
        sym = str(cert.get("sym") or spec.get("symbol") or "").upper()
        fam = _family_of(cert, key)
        mech = MECHANISM_CLASS.get(fam, "UNCLASSIFIED")
        row = meta.get(sym) or {}
        params = spec.get("params") if isinstance(spec.get("params"), dict) else \
            (cert.get("params") if isinstance(cert.get("params"), dict) else {})
        out[key] = {"symbol": sym, "asset_class": str(row.get("asset_class") or ""),
                    "legs": list(_legs(sym, meta)), "family": fam, "mechanism": mech,
                    "direction_bias": DIRECTION_BIAS.get(mech, "unknown"),
                    "clock": _clock_of(cert, key), "factor_roles": list(_factor_roles(sym, meta)),
                    "source": str(cert.get("hunt") or ""),
                    "status": str(cert.get("status") or "PASS"),
                    # VARIABLE-LEVEL DESCENT: the same ids `strategy_artifact.from_certificate`
                    # stamps, so the genome and the artifact registry name one vocabulary.
                    "feature_ids": feature_ids_of(params),
                    # THE ECONOMIC CLAIM, ELEVEN SLOTS WIDE (C5). Everything above is STRUCTURE
                    # -- what the cell is made of. This is what it CLAIMS: an actor under a
                    # constraint, the observable that reveals it, the trigger, the catalyst, the
                    # transmission channel, entry, exit, holding, capacity and decay risk.
                    # Declared per family in libs/research/mechanism_genome.py, never inferred
                    # from the family's name, so an undeclared family reads UNDECLARED here
                    # rather than being given an actor it was never measured against.
                    "mechanism_genome": mg.from_family(fam, params).as_dict()}
    return out


def recombinations(active: dict[str, dict[str, Any]], *,
                   limit: int = 60) -> list[dict[str, Any]]:
    """Slot-level crosses of the canon's declared genomes that are internally coherent. C5.

    RECOMBINATION AT THE LEVEL OF THE ECONOMICS, which is the half of C5 the grammar search
    cannot reach: `alpha_evolution` crosses operators and parameters, and two alphas with
    identical grammar can make opposite claims about who is on the other side. Each child here
    differs from its parent in ONE slot, so a verdict on it is attributable to that slot.

    INCOHERENT CHILDREN ARE NOT MINTED. The compatibility tables refuse a transmission that
    cannot carry its trigger and a holding period that cannot admit its exit -- not to gate
    research, but because the trial budget is SHARED: a cell that cannot be true still charges
    the deflated-Sharpe and SPA budget every other cell must clear.
    """
    seen: dict[str, mg.Genome] = {}
    for row in active.values():
        fam = str(row.get("family") or "")
        if fam and fam not in seen:
            g = mg.from_family(fam)
            if g.declared:
                seen[fam] = g
    out: list[dict[str, Any]] = []
    fams = sorted(seen)
    for i, a in enumerate(fams):
        for b in fams[i + 1:]:
            out.extend(mg.recombine(seen[a], seen[b]))
            if len(out) >= limit:
                return out[:limit]
    return out[:limit]


def feature_genealogy(g: dict[str, dict]) -> dict[str, dict]:
    """Per feature id, the sleeves that descend from it -- the fake-breadth reading at the
    VARIABLE level. Family and cluster breadth both miss twelve sleeves that are all the same
    20-day range wearing different family names; this does not. Sorted by fan-out, and a
    feature carried by one sleeve is listed too, because "unique" is a reading as well."""
    members: dict[str, list[str]] = defaultdict(list)
    for key in sorted(g):
        for fid in g[key].get("feature_ids") or []:
            members[str(fid)].append(key)
    ordered = sorted(members.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return {fid: {"n": len(ms), "share": round(len(ms) / max(1, len(g)), 3), "members": ms}
            for fid, ms in ordered}


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
        legs = functools.reduce(operator.iadd, (g[m]["legs"] for m in members), [])
        name = (f"{g0['mechanism']}/{g0['direction_bias']}/{g0['clock']}/"
                f"{'+'.join(sorted(set(legs)))[:40]}")
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
    fg = feature_genealogy(active)
    shared = {fid: row for fid, row in fg.items() if row["n"] >= 2}
    without = sorted(k for k, v in active.items() if not v.get("feature_ids"))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "n_sleeves": len(active),
           "n_clusters": len(cl),
           "structural_breadth": round(len(cl) / max(1, len(active)), 3),
           "by_mechanism": dict(by_mech),
           "unclassified_families": sorted({v["family"] for v in active.values()
                                            if v["mechanism"] == "UNCLASSIFIED"}),
           "largest_clusters": [{"cluster": k, "n": len(v), "members": v[:10]} for k, v in biggest],
           # THE VARIABLE-LEVEL VIEW. `max_feature_fanout` is the largest number of sleeves that
           # read one variable; `sleeves_without_feature_ids` names the certificates whose
           # params carry nothing to descend from (a legacy cell with no exact params), so the
           # denominator of this reading is visible beside it.
           "feature_genealogy": fg,
           "n_feature_ids": len(fg), "n_shared_feature_ids": len(shared),
           "max_feature_fanout": max((r["n"] for r in fg.values()), default=0),
           "largest_feature_lineages": [{"feature_id": fid, "n": r["n"],
                                         "members": r["members"][:10]}
                                        for fid, r in list(fg.items())[:8]],
           "sleeves_without_feature_ids": without,
           "clusters": cl, "genome": active}
    # ---------------------------------------------------------------- C5: the mechanism genome
    try:
        from mt5desk.families import FAMILY_REGISTRY
        fam_names = list(FAMILY_REGISTRY)
    except Exception:                                       # pragma: no cover - import env
        fam_names = sorted({str(v.get("family") or "") for v in active.values()} - {""})
    crosses = recombinations(active)
    mg_block: dict[str, Any] = {
        "slots": list(mg.SLOTS),
        "census": mg.census(fam_names),
        "n_recombinations": len(crosses),
        "recombinations": crosses,
        "rule": ("one slot crossed per child, so a verdict is attributable to that slot; "
                 "incoherent children are not minted, because the trial budget is shared"),
        "authority": ("PUBLISHES AND DONATES. It refuses no existing alpha, caps nothing and "
                      "shrinks nothing; the sealed gauntlet judges every child it mints like "
                      "any other candidate"),
    }
    doc["mechanism_genome"] = mg_block
    # DONATED THROUGH THE ONE INTAKE, so a slot-level child is judged by the same ten gates as
    # every other candidate. A child carries its parents and the crossed slot in `evidence`, so
    # `mutation_yield` can join the verdict back to the slot that produced it.
    try:
        from research import proposer_common as pc
        cands = [pc.candidate(
            "mechanism_genome", str(v.get("symbol") or ""), str(v.get("family") or ""),
            {"mechanism_genome": c["genome"], "crossed_slot": c["slot"]},
            mechanism=(f"{c['from_family']} with {c['slot']}={c['took']} taken from "
                       f"{c['to_family']}"),
            title=f"{c['from_family']}+{c['to_family']} :: {c['slot']}",
            evidence={"crossed_slot": c["slot"], "took": c["took"], "replaced": c["replaced"],
                      "parents": [c["from_family"], c["to_family"]],
                      "coherence": c["coherence"], "generator": "mechanism_genome"})
            for c in crosses
            for v in [next((r for r in active.values()
                            if str(r.get("family")) == c["from_family"]), None)] if v]
        if cands:
            mg_block["donated"] = str(pc.donate("mechanism_genome", cands, len(crosses)))
            mg_block["donation_counts"] = pc.donation_counts()
    except Exception as exc:                                # a donation never costs the report
        mg_block["donated"] = f"UNMEASURED: {type(exc).__name__}: {str(exc)[:120]}"
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
