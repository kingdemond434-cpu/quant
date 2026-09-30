"""MAP-ELITES' CAPACITY AND CORRELATION-CLUSTER AXES (Tier S layer 6).

The archive's behaviour space was the ten `axis_registry` axes plus direction and complexity.
Two descriptors the principal named were missing, and both change which niches count as distinct:

  * CORRELATION CLUSTER. Two elites on EURCHF and EURUSD are not two bets if the pairs co-move;
    two elites on uncorrelated instruments are, whatever their mechanism. The cluster of a symbol
    is its AVERAGE-linkage cluster of timestamp-aligned H1 log-return correlations cut at
    `threshold` (pairwise-complete hours, at least `min_overlap` shared bars). The label is the
    cluster's lexicographically first member, so it is stable across hours while membership
    holds. A symbol with no bars is "?" -- unmeasured, never a cluster of
    its own.

  * CAPACITY. What the edge is worth AT THIS ACCOUNT'S SIZE (`research/capacity.py`): the
    measured floor-binding verdict and headroom multiple from `reports/CAPACITY.json`, banded.
    Where CAPACITY.json has no row for a symbol, the secondary source is the symbol's traded
    activity (median tick volume tercile across the panel), labelled as a liquidity band so the
    two sources are never confused. Neither available: "?".
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def correlation_clusters(rets: Any, *, threshold: float = 0.5, min_overlap: int = 200
                         ) -> dict[str, Any]:
    """rets: DataFrame of aligned log returns. -> {labels: {sym: 'cc:<first>'}, clusters, ...}"""
    syms = [str(c) for c in getattr(rets, "columns", [])]
    if len(syms) < 2:
        return {"status": "UNMEASURED", "why": f"{len(syms)} symbol(s) with bars", "labels": {}}
    corr = rets.corr(min_periods=min_overlap).to_numpy(dtype=float)
    # AVERAGE linkage on distance 1 - corr, cut at 1 - threshold: a cluster's members correlate
    # at `threshold` ON AVERAGE, so USD pairs do not chain every FX cross into one component the
    # way single linkage does. Pairs without `min_overlap` shared hours count as uncorrelated.
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    d = 1.0 - np.where(np.isfinite(corr), corr, 0.0)
    np.fill_diagonal(d, 0.0)
    d = np.clip((d + d.T) / 2.0, 0.0, 2.0)
    ids = fcluster(linkage(squareform(d, checks=False), method="average"),
                   t=1.0 - threshold, criterion="distance")
    groups: dict[int, list[str]] = {}
    for i, s in enumerate(syms):
        groups.setdefault(int(ids[i]), []).append(s)
    labels: dict[str, str] = {}
    clusters: dict[str, list[str]] = {}
    for members in groups.values():
        lab = "cc:" + sorted(members)[0]
        clusters[lab] = sorted(members)
        for s in members:
            labels[s] = lab
    return {"status": "MEASURED", "threshold": threshold, "min_overlap": min_overlap,
            "n_symbols": len(syms), "n_clusters": len(clusters), "labels": labels,
            "clusters": dict(sorted(clusters.items(), key=lambda kv: -len(kv[1])))}


def capacity_band(row: Mapping[str, Any]) -> str | None:
    """headroom_multiple = (equity below which the min-lot floor binds) / (equity now): >= 1 the
    venue's floor overrides the policy now; below 1 its inverse is how far the account sits
    clear of the floor."""
    h = row.get("headroom_multiple")
    if row.get("binding_now") is True or (isinstance(h, (int, float)) and h >= 1.0):
        return "floor_binding"
    if not isinstance(h, (int, float)) or h <= 0:
        return None
    clear = 1.0 / float(h)
    return "clear<3x" if clear < 3.0 else "clear3-10x" if clear < 10.0 else "clear>10x"


def capacity_bands(capacity_doc: Any, frames: Mapping[str, Any] | None = None
                   ) -> dict[str, Any]:
    """{labels: {sym: band}, source: {sym: 'capacity_json'|'liquidity_proxy'}, counts}."""
    labels: dict[str, str] = {}
    source: dict[str, str] = {}
    rows = (capacity_doc or {}).get("rows") if isinstance(capacity_doc, dict) else None
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        sym, band = str(r.get("symbol") or ""), capacity_band(r)
        if sym and band and sym not in labels:
            labels[sym], source[sym] = band, "capacity_json"
    med: dict[str, float] = {}
    for sym, f in (frames or {}).items():
        if sym in labels or "tick_volume" not in getattr(f, "columns", []):
            continue
        v = float(np.nanmedian(f["tick_volume"].astype(float).to_numpy()))
        if np.isfinite(v) and v > 0:
            med[sym] = v
    if len(med) >= 3:
        lo, hi = np.quantile(list(med.values()), [1 / 3, 2 / 3])
        for sym, v in med.items():
            labels[sym] = ("liq_low" if v <= lo else "liq_high" if v > hi else "liq_mid")
            source[sym] = "liquidity_proxy"
    counts: dict[str, int] = {}
    for s in source.values():
        counts[s] = counts.get(s, 0) + 1
    return {"labels": labels, "source": source, "counts": counts,
            "status": "MEASURED" if labels else "UNMEASURED",
            "why": None if labels else "no CAPACITY.json rows and no tick volumes in the panel"}
