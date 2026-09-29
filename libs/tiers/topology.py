"""ALPHA TOPOLOGY AND ANCESTRY (Tier S layers 9, 14, 15): how many INDEPENDENT alphas the desk
actually holds, and how much of each new discovery is really new.

EFFECTIVE INDEPENDENT ALPHA RANK. One dependence concept undercounts clones that agree only in the
tail, or share a parent and a feature but not a Pearson correlation. So the rank is measured under
several concepts and the desk reports each and the CONSERVATIVE combination:

    linear       participation ratio of the Pearson correlation spectrum
    signal_rank  eigenvalues above the Marchenko-Pastur noise edge
    rank         participation ratio of the Spearman correlation spectrum (monotone nonlinear)
    tail         participation ratio of lower-tail co-exceedance (joint worst-decile days)
    drawdown     participation ratio of drawdown-state coincidence
    ancestry     participation ratio of descriptor/lineage similarity (mechanism, features,
                 data, code, parent) -- computable before any return exists
    combined     participation ratio of the ELEMENTWISE MAX of all similarity matrices: two
                 sleeves are as dependent as their most dependent reading says

`steering()` turns the basis into a research direction: descriptor values (mechanism, asset
class, horizon, region...) are weighted by how little of the effective basis they already occupy,
so the scheduler asks for what is orthogonal to what the desk holds.

ANCESTRY. A -> mutate -> B -> crossover C -> D is not four discoveries. Each node's NOVELTY is
1 - max over its ancestors of (similarity x decay^generation); its independent credit is its
novelty, and the desk's effective discovery count is the sum of novelty, not the node count.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]


def participation_ratio(sim: F) -> float:
    if sim.size == 0:
        return 0.0
    s = (sim + sim.T) / 2
    ev = np.clip(np.linalg.eigvalsh(s), 0.0, None)
    tot = float(ev.sum())
    sq = float((ev ** 2).sum())
    return tot * tot / sq if sq > 0 else 0.0


def _corr(x: F) -> F:
    sd = x.std(axis=0)
    keep = sd > 0
    c = np.eye(x.shape[1])
    if keep.sum() >= 2:
        sub = np.corrcoef(x[:, keep], rowvar=False)
        idx = np.where(keep)[0]
        c[np.ix_(idx, idx)] = sub
    out: F = np.nan_to_num(c, nan=0.0)
    return out


def _rank(x: F) -> F:
    out: F = np.argsort(np.argsort(x, axis=0), axis=0).astype(float)
    return out


def mp_signal_rank(x: F) -> int:
    t, n = int(x.shape[0]), int(x.shape[1])
    if t < 3 or n < 2:
        return n
    q = n / t
    edge = (1 + math.sqrt(q)) ** 2
    ev = np.linalg.eigvalsh(_corr(x))
    return max(1, int((ev > edge).sum()))


def tail_similarity(x: F, q: float = 0.1) -> F:
    thr = np.quantile(x, q, axis=0)
    ex = (x <= thr).astype(float)
    p = ex.mean(axis=0)
    joint = (ex.T @ ex) / x.shape[0]
    denom = np.sqrt(np.outer(p, p))
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(denom > 0, joint / denom, 0.0)
    np.fill_diagonal(s, 1.0)
    # remove the independence baseline: two independent series co-exceed at rate q
    out: F = np.clip((s - q) / (1 - q), 0.0, 1.0)
    np.fill_diagonal(out, 1.0)
    return out


def drawdown_similarity(x: F) -> F:
    eq = np.cumsum(x, axis=0)
    dd = (np.maximum.accumulate(eq, axis=0) - eq > 0).astype(float)
    return np.abs(_corr(dd))


def descriptor_similarity(descs: Sequence[Mapping[str, Any]]) -> F:
    n = len(descs)
    s = np.eye(n)
    keys = [{f"{k}={v}" for k, v in d.items() if v not in (None, "")} for d in descs]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = keys[i], keys[j]
            u = len(a | b)
            v = len(a & b) / u if u else 0.0
            s[i, j] = s[j, i] = v
    out: F = s
    return out


def rank_report(pnl: F | None, names: Sequence[str],
                descriptors: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Effective independent alpha rank under every concept the inputs allow."""
    n = len(names)
    sims: dict[str, F] = {}
    out: dict[str, Any] = {"n_sleeves": n}
    if pnl is not None and pnl.ndim == 2 and pnl.shape[1] == n and pnl.shape[0] >= 10:
        x = np.nan_to_num(pnl.astype(float))
        sims["linear"] = np.abs(_corr(x))
        sims["rank"] = np.abs(_corr(_rank(x)))
        sims["tail"] = tail_similarity(x)
        sims["drawdown"] = drawdown_similarity(x)
        out["signal_rank"] = mp_signal_rank(x)
        out["n_obs"] = int(x.shape[0])
    if descriptors is not None and len(descriptors) == n:
        sims["ancestry"] = descriptor_similarity(descriptors)
    for k, m in sims.items():
        out[k] = round(participation_ratio(m), 4)
    if sims:
        comb = np.maximum.reduce(list(sims.values()))
        out["combined"] = round(participation_ratio(comb), 4)
        uniq = 1.0 - np.max(comb - np.eye(n), axis=1) if n > 1 else np.ones(n)
        out["uniqueness"] = {names[i]: round(float(uniq[i]), 4) for i in range(n)}
    else:
        out["combined"] = None
    return out


def steering(descriptors: Sequence[Mapping[str, Any]], uniqueness: Mapping[str, float] | None,
             names: Sequence[str], axes: Sequence[str]) -> dict[str, dict[str, float]]:
    """Per axis value: 1 / (1 + effective occupancy). Occupancy counts each sleeve by how much
    of it is NOT unique (a clone occupies its cell fully; a unique sleeve only lightly)."""
    out: dict[str, dict[str, float]] = {}
    for ax in axes:
        occ: dict[str, float] = {}
        for i, d in enumerate(descriptors):
            v = d.get(ax)
            if v in (None, ""):
                continue
            u = (uniqueness or {}).get(names[i], 0.0)
            occ[str(v)] = occ.get(str(v), 0.0) + (1.0 - 0.5 * u)
        out[ax] = {k: round(1.0 / (1.0 + v), 4) for k, v in sorted(occ.items())}
    return out


def novelty(nodes: Mapping[str, Mapping[str, Any]], decay: float = 0.8) -> dict[str, float]:
    """nodes: id -> {"parents": [...], "descriptors": {...}}. Novelty in [0, 1]."""
    cache: dict[str, float] = {}
    keysets = {nid: {f"{k}={v}" for k, v in (n.get("descriptors") or {}).items()}
               for nid, n in nodes.items()}

    def ancestors(nid: str) -> list[tuple[str, int]]:
        seen: dict[str, int] = {}
        frontier = [(p, 1) for p in (nodes.get(nid) or {}).get("parents") or []]
        while frontier:
            p, g = frontier.pop()
            if p in seen and seen[p] <= g:
                continue
            seen[p] = g
            frontier.extend((q, g + 1) for q in (nodes.get(p) or {}).get("parents") or [])
        return list(seen.items())

    seen_sets: set[frozenset[str]] = set()
    for nid in nodes:
        best = 0.0
        a = keysets.get(nid, set())
        fa = frozenset(a)
        if fa in seen_sets:
            # an exact descriptor repeat of an earlier node, parented or not, adds nothing new
            cache[nid] = 0.0
            continue
        seen_sets.add(fa)
        for anc, gen in ancestors(nid):
            b = keysets.get(anc)
            if b is None:
                sim = 1.0  # an unresolvable parent: assume inherited, the conservative side
            else:
                u = len(a | b)
                sim = len(a & b) / u if u else 1.0
            best = max(best, sim * decay ** (gen - 1))
        cache[nid] = round(1.0 - best, 4)
    return cache


def effective_discoveries(nov: Mapping[str, float]) -> dict[str, Any]:
    n = len(nov)
    s = float(sum(nov.values()))
    return {"n_nodes": n, "effective": round(s, 3), "ratio": (s / n) if n else None}
