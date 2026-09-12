"""F16 -- WHERE THE DATA CHOOSES BETWEEN TWO CAUSAL STORIES, and where it admits it cannot.

THE PRINCIPAL, 2026-09-12:

    Causal-DAG discovery, conditional independence tests, natural experiments, event
    discontinuities, instrumental variables where defensible, automated distinguishing
    experiments -- the system CHOOSES between two causal explanations rather than describing both.

THE GAP, AS THE LEDGER STATES IT: mechanisms already require a forced participant and alternative
explanations are already enforced. So the desk ENUMERATES rival stories well and has no way to
DECIDE between them -- every candidate arrives with four alternative explanations and nothing ever
rules one out.

WHERE OBSERVATIONAL DATA CAN DECIDE, AND IT IS A NARROW PLACE. For three series the four causal
structures behind a correlation are not equally testable:

    X -> Z -> Y      chain        X and Y become independent GIVEN Z
    X <- Z -> Y      confounder   X and Y become independent GIVEN Z
    X -> Z <- Y      collider     X and Y are independent MARGINALLY and DEPENDENT given Z

The first two are indistinguishable from data alone -- that is a fact about the world, not a
shortcoming of the method, and this organ says so rather than picking one. The COLLIDER is
different: its signature is the reverse of the others and it can be read straight off the
conditional independence pattern. Every v-structure found here is a causal claim the data CHOSE.

WHAT IS BUILT. The PC algorithm's constraint phase: a complete graph over the live book's returns,
edges removed where a conditional independence test says the dependence vanishes given a
separating set, then v-structures oriented from those separating sets. Partial correlation with a
Fisher z-test is the independence oracle.

THE ASSUMPTIONS ARE STATED BECAUSE VIOLATING THEM VOIDS THE DAG, and on financial series they are
strong: causal sufficiency (no unmeasured common cause -- false here, the dollar and the risk
cycle are not in the panel), faithfulness (no exact cancellation), and linearity plus joint
normality for partial correlation to be the right oracle. Every edge is therefore reported as a
CONDITIONAL claim, and the unmeasured-confounder caveat is attached to the verdict rather than
buried at the bottom.

AND FOR EVERY EDGE IT CANNOT ORIENT, IT NAMES THE EXPERIMENT THAT WOULD. That is the "automated
distinguishing experiments" clause: a lead-lag asymmetry at the bar scale, a session-boundary
discontinuity, or an instrument -- named per edge, so an undirected edge is a research task rather
than a shrug.

    python desks/mt5/research/causal_discovery.py [--apply]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "CAUSAL_DISCOVERY.json"

BARS = 6000
MAX_NODES = 10

#: Significance for the Fisher z conditional-independence test. 0.01 rather than 0.05 because the
#: number of tests is quadratic in the node count and every spurious edge kept becomes a causal
#: claim -- the asymmetry of the two errors is not symmetric here.
ALPHA = 0.01

#: Largest conditioning set. Stage 0 and 1 of PC: marginal independence, then independence given
#: ONE other node. Higher orders need more data than 6,000 hourly bars can support for a
#: ten-node graph, and running them anyway is how a DAG becomes decoration.
MAX_COND = 1


def _live_symbols(limit: int = MAX_NODES) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _panel(symbols: list[str]) -> Any:
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return None
    series: dict[str, Any] = {}
    for s in symbols:
        p = UNI / f"{s}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p).tail(BARS)
        except (OSError, ValueError):
            continue
        if "close" not in df.columns or len(df) < 1000:
            continue
        series[s] = np.log(df["close"].astype(float)).diff()
    if len(series) < 3:
        return None
    return pd.DataFrame(series).dropna()


def _pcorr(c: Any, i: int, j: int, k: int | None) -> float:
    """Partial correlation of i and j given k (or marginal when k is None), from the corr matrix."""
    import numpy as np
    if k is None:
        return float(c[i, j])
    rij, rik, rjk = float(c[i, j]), float(c[i, k]), float(c[j, k])
    den = math.sqrt(max(1e-12, (1 - rik ** 2) * (1 - rjk ** 2)))
    return float(np.clip((rij - rik * rjk) / den, -0.999999, 0.999999))


def _fisher_p(r: float, n: int, n_cond: int) -> float:
    """Two-sided p for a (partial) correlation via Fisher's z. The independence oracle."""
    dof = n - n_cond - 3
    if dof <= 0 or abs(r) >= 0.999999:
        return 0.0
    z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(dof)
    # Two-sided normal tail without scipy: erfc is in the standard library.
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy unavailable ({exc})"}

    syms = _live_symbols()
    panel = _panel(syms)
    if panel is None:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("fewer than three live symbols have a usable aligned return history; a "
                        "conditional independence test needs a third variable to condition on")}
    nodes = list(panel.columns)
    n = len(panel)
    c = np.corrcoef(panel.to_numpy().T)

    # PC STAGE 0 AND 1. Start complete, remove an edge the moment any conditioning set makes the
    # dependence vanish, and REMEMBER THE SET -- the separating set is what orients v-structures
    # later, and a skeleton without it is a picture rather than a discovery.
    edges: set[tuple[int, int]] = {(i, j) for i, j in itertools.combinations(range(len(nodes)), 2)}
    sepset: dict[tuple[int, int], list[int]] = {}
    removed: list[dict[str, Any]] = []
    for i, j in list(edges):
        p0 = _fisher_p(_pcorr(c, i, j, None), n, 0)
        if p0 > ALPHA:
            edges.discard((i, j))
            sepset[(i, j)] = []
            removed.append({"pair": [nodes[i], nodes[j]], "given": [],
                            "r": round(_pcorr(c, i, j, None), 5), "p": round(p0, 6)})
    if MAX_COND >= 1:
        for i, j in list(edges):
            for k in range(len(nodes)):
                if k in (i, j):
                    continue
                r = _pcorr(c, i, j, k)
                p = _fisher_p(r, n, 1)
                if p > ALPHA:
                    edges.discard((i, j))
                    sepset[(i, j)] = [k]
                    removed.append({"pair": [nodes[i], nodes[j]], "given": [nodes[k]],
                                    "r": round(r, 5), "p": round(p, 6),
                                    "reads": (f"{nodes[i]} and {nodes[j]} are dependent, and that "
                                              f"dependence VANISHES given {nodes[k]}. Consistent "
                                              f"with a chain through {nodes[k]} or a common "
                                              f"cause {nodes[k]} -- and the data cannot separate "
                                              f"those two.")})
                    break

    # V-STRUCTURES: the one orientation observational data can make. X - Z - Y with X and Y NOT
    # adjacent and Z NOT in their separating set means both arrows point INTO Z.
    def adj(a: int, b: int) -> bool:
        return (min(a, b), max(a, b)) in edges

    colliders: list[dict[str, Any]] = []
    for z in range(len(nodes)):
        for x, y in itertools.combinations([v for v in range(len(nodes)) if v != z], 2):
            if not adj(x, z) or not adj(y, z) or adj(x, y):
                continue
            key = (min(x, y), max(x, y))
            sep = sepset.get(key)
            if sep is None or z in sep:
                continue
            colliders.append({
                "collider": nodes[z], "parents": [nodes[x], nodes[y]],
                "separating_set": [nodes[i] for i in sep],
                "claim": f"{nodes[x]} -> {nodes[z]} <- {nodes[y]}",
                "why_the_data_chose_it": (
                    f"{nodes[x]} and {nodes[y]} are independent given "
                    f"{[nodes[i] for i in sep] or 'nothing'}, and BOTH depend on {nodes[z]}. A "
                    f"chain or a common cause would have made them independent GIVEN "
                    f"{nodes[z]}; a collider makes them dependent given it. That reversal is the "
                    f"only causal direction observational data can settle, and it settled this "
                    f"one."),
            })

    # CONFLICT DETECTION, AND IT IS A MEASUREMENT RATHER THAN A CLEANUP.
    #
    # The first run produced 49 v-structures on a 29-edge graph, and among them
    # "AUDCAD -> XAUUSD <- CHFDKK" and "XAUUSD -> AUDCAD <- EURNOK" -- the same edge claimed in
    # both directions. Both cannot be true. Reporting all of them would have been a causal DAG
    # that contradicts itself, presented as discovery.
    #
    # A conflicted orientation is exactly what a FAITHFULNESS or CAUSAL SUFFICIENCY violation
    # looks like from inside the PC algorithm, and causal sufficiency is already known false here:
    # the dollar and the risk cycle are common causes of nearly every pair on this panel and
    # neither is a node. So the conflict count is a diagnostic on the assumptions, not noise to
    # be swept -- and only the edges oriented CONSISTENTLY are reported as claims.
    directed: dict[tuple[str, str], list[str]] = {}
    for cl in colliders:
        # `zname` rather than `z`: the v-structure loop above binds `z` to a node INDEX, and
        # reusing the letter for its name made the checker read an int where a str belongs.
        zname = str(cl["collider"])
        for parent in cl["parents"]:
            directed.setdefault((str(parent), zname), []).append(str(cl["claim"]))
    conflicted: list[dict[str, Any]] = []
    consistent: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[str]] = set()
    for (a, b), claims in sorted(directed.items()):
        pair = frozenset({a, b})
        if (b, a) in directed:
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            conflicted.append({
                "edge": sorted(pair),
                "claimed_both_ways": [f"{a} -> {b}", f"{b} -> {a}"],
                "n_v_structures": len(claims) + len(directed[(b, a)]),
                "reads": (f"v-structures orient {a} -> {b} AND {b} -> {a}. Both cannot hold. "
                          f"Inside the PC algorithm this is the signature of a violated "
                          f"assumption, and the one known false on this panel is causal "
                          f"sufficiency: an unmeasured common cause shared by {a} and {b} "
                          f"produces exactly this."),
            })
        else:
            consistent.append({"edge": f"{a} -> {b}", "from": a, "to": b,
                               "n_v_structures": len(claims)})
    consistent.sort(key=lambda r: -int(r["n_v_structures"]))

    undirected = [{"pair": [nodes[i], nodes[j]],
                   "r": round(float(c[i, j]), 5),
                   "rival_explanations": [
                       f"{nodes[i]} -> {nodes[j]}", f"{nodes[j]} -> {nodes[i]}",
                       "a common cause outside this panel"],
                   "distinguishing_experiment": (
                       "the data cannot orient this edge. Three things would: (1) a LEAD-LAG "
                       "asymmetry at a finer bar -- if one series' move systematically precedes "
                       "the other's by a bar the tape is not symmetric, and orthogonality.py "
                       "already measures exactly this; (2) a SESSION DISCONTINUITY -- one "
                       "instrument's home session opening is an exogenous timing shock to it and "
                       "not to the other, which is a natural experiment the desk's own hour "
                       "stamps supply; (3) an INSTRUMENT -- a variable that moves one and reaches "
                       "the other only through it, which for FX crosses is the third leg of the "
                       "triangle."),
                   }
                  for i, j in sorted(edges)]

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "nodes": nodes, "n_bars": n, "alpha": ALPHA, "max_conditioning_set": MAX_COND,
        "skeleton": {
            "n_possible_edges": len(nodes) * (len(nodes) - 1) // 2,
            "n_edges_kept": len(edges),
            "n_edges_removed": len(removed),
            "removed": removed[:30],
        },
        "oriented_by_the_data": consistent,
        "n_oriented": len(consistent),
        "v_structures_found": len(colliders),
        "conflicting_orientations": {
            "n": len(conflicted), "rows": conflicted[:12],
            "why": ("an edge oriented BOTH ways by different v-structures. Both cannot hold, so "
                    "neither is reported as a claim. Inside the PC algorithm this is what a "
                    "violated assumption looks like, and causal sufficiency is already known "
                    "false on this panel -- the dollar cycle and the risk cycle are common causes "
                    "of nearly every pair here and neither is a node. The COUNT is the useful "
                    "output: a run with many conflicts is a run whose DAG should not be read."),
        },
        "v_structure_detail": colliders[:12],
        "undirected": undirected[:20],
        "what_the_data_cannot_settle": (
            "a chain X->Z->Y and a common cause X<-Z->Y leave the SAME footprint -- X and Y "
            "independent given Z -- so observational data cannot separate them. That is a fact "
            "about the world, not a shortcoming of the method, and this organ reports both "
            "rather than picking the one that sounds better."),
        "assumptions": {
            "causal_sufficiency": (
                "FALSE ON THIS PANEL and stated first because it is the one that bites: the "
                "dollar cycle, the risk cycle and rates are common causes of nearly every pair "
                "here and none of them is a node. An edge that survives may be their shadow."),
            "faithfulness": ("no two causal paths cancel exactly. Usually harmless, and violated "
                             "precisely where a hedge is working"),
            "linear_gaussian": ("partial correlation is the right independence oracle only for "
                                "linear, jointly normal variables. Hourly FX returns are neither, "
                                "so a non-linear dependence reads here as independence"),
            "consequence": ("every edge is a CONDITIONAL claim, true if the three above hold. "
                            "They are reported with the verdict rather than buried, because a "
                            "DAG quoted without its assumptions is a causal story with a "
                            "diagram."),
        },
        "boundary": (
            "NOTHING HERE TRADES OR CERTIFIES. An oriented edge is a hypothesis about structure; "
            "it reaches the book the same way everything else does."),
        "why": (
            "the desk already enumerates rival explanations well and has no way to decide between "
            "them, so every candidate arrives with four alternatives and none is ever ruled out."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"causal discovery: {doc.get('status')} -- {doc.get('why')}")
        return 0
    sk = doc["skeleton"]
    print(f"causal discovery: OK   {len(doc['nodes'])} node(s), {doc['n_bars']} shared bar(s), "
          f"alpha {doc['alpha']}")
    print(f"  skeleton: {sk['n_edges_kept']} of {sk['n_possible_edges']} edge(s) survive; "
          f"{sk['n_edges_removed']} removed by a conditional independence test")
    for r in sk["removed"][:6]:
        given = ", ".join(r["given"]) or "nothing"
        print(f"    {r['pair'][0]:<9} -- {r['pair'][1]:<9} independent given {given:<10} "
              f"r={r['r']:+.4f} p={r['p']:.4f}")
    print(f"  {doc['v_structures_found']} v-structure(s) found -> "
          f"{doc['n_oriented']} edge(s) oriented CONSISTENTLY")
    for cl in doc["oriented_by_the_data"][:8]:
        print(f"    {cl['edge']}   (from {cl['n_v_structures']} v-structure(s))")
    cf = doc["conflicting_orientations"]
    if cf["n"]:
        print(f"  {cf['n']} edge(s) oriented BOTH WAYS -- neither reported as a claim:")
        for r in cf["rows"][:4]:
            print(f"    {r['edge'][0]} <-> {r['edge'][1]}  {r['claimed_both_ways']}")
        print("    a conflicted orientation is the signature of a violated assumption, and "
              "causal sufficiency is known false here")
    print(f"  {len(doc['undirected'])} edge(s) the data cannot orient; each carries the "
          f"experiment that would")
    print(f"  ASSUMPTION THAT BITES: {doc['assumptions']['causal_sufficiency'][:140]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
