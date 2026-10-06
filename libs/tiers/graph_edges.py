"""THE WORLD MODEL'S OWN EDGE LIST, CLASSIFIED (Tier S layer 3).

`world_edges.classify_all` classifies every pair of a returns panel -- edges the desk never wrote
down. The desk's world model DOES write its edges down, in two places:

    desks/mt5/data/world_causal_graph.json     `edges`: src -> dst, lag, direction, status
                                               (STRUCTURAL / RECORDED_NOT_ADMITTED / ...)
    desks/mt5/reports/CROSS_ASSET_GRAPH.json   `edges`: driver -> target, lag, direction, verdict

Those edges are claims -- some seeded from a forum story, some measured once and never again --
and nothing re-asks whether each one still holds. `classify_listed()` takes the listed edge list
ITSELF and puts every edge through the same life-cycle test (`world_edges.classify_edge`: FALSE,
STABLE, DECAYING, STATE_DEPENDENT), Bonferroni-charged over the edges examined, on the two
instruments' H1 returns joined ON TIMESTAMP (never tail-aligned: two series of equal length can
cover different hours). The graph's own claim is compared with the verdict: a listed direction the
data now contradicts is a `sign_flip`, a listed edge the data calls FALSE or DECAYING is
`contradicted`, and a STABLE listed edge whose recent residual is extreme is BROKEN -- the same
structural-residual hypothesis `world_edges.residuals` mints.

AN EDGE WITH A NON-PRICE ENDPOINT (a central bank, a positioning node, a yield curve, a flow) is
UNMEASURED here with the node's kind named: its series is the macro world's job
(`libs/tiers/world_macro.py`), and a price-only classifier has nothing honest to say about it.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.tiers import world_edges

UNMEASURED = "UNMEASURED"
#: fewer joined hourly returns than this and an edge is not classified
MIN_JOINED = 500
#: bars of H1 history read per instrument
BARS = 4000


def listed_edges(causal: Any, cross: Any) -> list[dict[str, Any]]:
    """Both documents' edges in one shape: driver, target, lag, direction, origin, listed_status,
    plus the endpoint node kinds where the causal graph declares them."""
    kinds: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    if isinstance(causal, Mapping):
        for n in causal.get("nodes") or []:
            if isinstance(n, Mapping) and n.get("id"):
                kinds[str(n["id"])] = str(n.get("kind") or "")
        for e in causal.get("edges") or []:
            if not isinstance(e, Mapping) or not e.get("src") or not e.get("dst"):
                continue
            out.append({"driver": str(e["src"]), "target": str(e["dst"]),
                        "lag": int(e.get("lag") or 0), "direction": e.get("direction"),
                        "origin": "world_causal_graph",
                        "listed_status": e.get("status") or e.get("admission")})
    if isinstance(cross, Mapping):
        for e in cross.get("edges") or []:
            if not isinstance(e, Mapping) or not e.get("driver") or not e.get("target"):
                continue
            out.append({"driver": str(e["driver"]), "target": str(e["target"]),
                        "lag": int(e.get("lag") or 0), "direction": e.get("direction"),
                        "origin": "cross_asset_graph", "listed_status": e.get("verdict")})
    seen: set[tuple[str, str, int, str]] = set()
    uniq = []
    for e in out:
        key = (e["driver"], e["target"], e["lag"], e["origin"])
        if key in seen:
            continue
        seen.add(key)
        e["driver_kind"] = kinds.get(e["driver"], "mt5_instrument" if e["origin"] ==
                                     "cross_asset_graph" else "")
        e["target_kind"] = kinds.get(e["target"], "mt5_instrument" if e["origin"] ==
                                     "cross_asset_graph" else "")
        uniq.append(e)
    return uniq


def h1_returns(universe: Path, symbols: Iterable[str], bars: int = BARS) -> dict[str, pd.Series]:
    """Timestamp-indexed H1 log returns per symbol that has a readable bar file."""
    out: dict[str, pd.Series] = {}
    for s in sorted(set(symbols)):
        p = universe / f"{s}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        c = df["close"].astype(float).iloc[-bars:]
        c = c[np.isfinite(c.to_numpy()) & (c.to_numpy() > 0)]
        if len(c) < MIN_JOINED:
            continue
        out[s] = np.log(c).diff().dropna()
    return out


def _joined(x: pd.Series, y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    j = pd.concat([x.rename("x"), y.rename("y")], axis=1, join="inner").dropna()
    return j["x"].to_numpy(dtype=float), j["y"].to_numpy(dtype=float)


def _listed_sign(direction: Any) -> int:
    d = str(direction or "").lower()
    return -1 if d in ("opposite", "negative", "-1", "inverse") else 1 if d else 0


def classify_listed(edges: list[dict[str, Any]], rets: Mapping[str, pd.Series],
                    may: Callable[[str], bool] | None = None) -> dict[str, Any]:
    """Every listed edge through the life-cycle test, or UNMEASURED with the reason."""
    measurable: list[tuple[dict[str, Any], np.ndarray, np.ndarray]] = []
    rows: list[dict[str, Any]] = []
    for e in edges:
        why = ""
        for side in ("driver", "target"):
            kind = e.get(f"{side}_kind") or ""
            if kind and kind != "mt5_instrument":
                why = why or (f"{side} {e[side]} is a {kind} node: its series is the macro "
                              "world's, not a price-only classifier's")
            elif e[side] not in rets:
                why = why or f"no H1 bars for {side} {e[side]} on this host"
        if why:
            rows.append({**e, "class": UNMEASURED, "why": why})
            continue
        x, y = _joined(rets[e["driver"]], rets[e["target"]])
        if len(x) < MIN_JOINED:
            rows.append({**e, "class": UNMEASURED,
                         "why": f"{len(x)} timestamp-joined returns < {MIN_JOINED}"})
            continue
        measurable.append((e, x, y))
    n_tests = max(1, len(measurable))
    resid: list[dict[str, Any]] = []
    for e, x, y in measurable:
        lag = max(0, int(e["lag"]))
        res = world_edges.classify_edge(x, y, lag, n_tests=n_tests)
        row = {**e, **res, "n_joined": len(x)}
        sgn = _listed_sign(e.get("direction"))
        cls = res["class"]
        row["agrees_with_listing"] = (
            False if cls in ("FALSE", "DECAYING")
            else (None if sgn == 0 else bool(np.sign(res["beta"]) == sgn)))
        row["sign_flip"] = bool(sgn and cls != "FALSE" and np.sign(res["beta"]) != sgn)
        rows.append(row)
        if cls == "STABLE" and (may is None or may(e["target"])):
            panel = {e["driver"]: x, e["target"]: y}
            for r in world_edges.residuals(panel, [{**res, "driver": e["driver"],
                                                    "target": e["target"], "lag": lag}]):
                resid.append({**r, "origin": e["origin"], "listed": True})
    census = Counter(str(r["class"]) for r in rows)
    by_origin: dict[str, Counter[str]] = {}
    for r in rows:
        by_origin.setdefault(str(r["origin"]), Counter())[str(r["class"])] += 1
    unmeasured_kinds = Counter(str(r.get("driver_kind") or r.get("target_kind"))
                               for r in rows if r["class"] == UNMEASURED
                               and "node" in str(r.get("why")))
    measured = [r for r in rows if r["class"] != UNMEASURED]
    return {"n_listed": len(rows), "n_measured": len(measured), "bonferroni_tests": n_tests,
            "census": dict(census), "by_origin": {k: dict(v) for k, v in by_origin.items()},
            "contradicted": sum(1 for r in measured if r.get("agrees_with_listing") is False),
            "sign_flips": sum(1 for r in measured if r.get("sign_flip")),
            "unmeasured_node_kinds": dict(unmeasured_kinds),
            "edges": rows, "broken": resid}
