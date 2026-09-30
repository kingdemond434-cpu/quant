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


# ------------------------------------------------------------------------------------------------
# TRADE-OVERLAP AND EXPOSURE SIMULATIONS (layer 15's remaining half, 2026-09-30)
#
# The descriptor rank is computable before a return exists and the live-P&L rank waits on fills.
# Between them sit two readings the desk can take NOW from what it already holds:
#
#   trade_overlap   the recorded trades (shadow excursions + live fills joined to the order that
#                   opened them) as signed exposure on CURRENCY LEGS per UTC hour. Two sleeves
#                   are as dependent as the exposure they held at the same time on the same legs:
#                   |sum over shared hours of side_i * side_j * cos(legs_i, legs_j)| / sqrt(|A||B|)
#                   -- long EURUSD and short USDCHF in the same hour are ONE bet on the dollar.
#   exposure_sim    every registered sleeve replayed on the desk's own H1 bars as the exposure its
#                   identity declares (symbol, direction, the UTC hours of its window); the
#                   simulated hourly P&L panel is ranked under every concept rank_report knows
#                   (linear, rank, tail, drawdown). It needs no fill and no forward clock.
# ------------------------------------------------------------------------------------------------

#: codes read as currency legs; anything else is its own leg (an index, a share, an energy CFD)
LEG_CODES: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "ZAR", "NOK", "SEK", "DKK", "MXN",
    "SGD", "HKD", "TRY", "PLN", "HUF", "CZK", "CNH", "ILS", "THB", "XAU", "XAG", "XPT", "XPD",
    "BTC", "ETH", "LTC", "XRP", "SOL", "ADA", "DOT", "BCH"})


def legs(symbol: str) -> dict[str, float]:
    """Signed unit exposure per leg of one long unit of `symbol`: EURUSD -> {EUR: +1, USD: -1}."""
    s = "".join(ch for ch in str(symbol).upper().split(".")[0] if ch.isalnum())
    if len(s) >= 6 and s[:3] in LEG_CODES and s[3:6] in LEG_CODES and s[:3] != s[3:6]:
        return {s[:3]: 1.0, s[3:6]: -1.0}
    return {s or "?": 1.0}


def leg_cosine(a: str, b: str) -> float:
    la, lb = legs(a), legs(b)
    dot = sum(v * lb.get(k, 0.0) for k, v in la.items())
    na = math.sqrt(sum(v * v for v in la.values()))
    nb = math.sqrt(sum(v * v for v in lb.values()))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


#: (start epoch s, end epoch s, side +-1, symbol)
Trade = tuple[float, float, float, str]

#: one trade occupies at most this many hours (a stuck record must not own the whole clock)
MAX_TRADE_HOURS = 24 * 14


def _hour_side(trades: Sequence[Trade]) -> dict[int, list[tuple[float, str]]]:
    out: dict[int, list[tuple[float, str]]] = {}
    for start, end, side, sym in trades:
        if not (math.isfinite(start) and math.isfinite(end)) or end < start or side == 0:
            continue
        h0, h1 = int(start // 3600), int(end // 3600)
        for h in range(h0, min(h1, h0 + MAX_TRADE_HOURS) + 1):
            out.setdefault(h, []).append((float(np.sign(side)), str(sym)))
    return out


def trade_overlap(trades_by: Mapping[str, Sequence[Trade]], min_trades: int = 3
                  ) -> dict[str, Any]:
    """Signed leg co-exposure and plain co-occupancy of recorded trades, with their ranks.
    `names` / `similarity` are returned for the caller to combine; they are not JSON."""
    names = sorted(k for k, v in trades_by.items() if len(v) >= min_trades)
    n = len(names)
    if n < 2:
        return {"status": "UNMEASURED", "n_sleeves": n,
                "why": f"{n} sleeve(s) with >= {min_trades} recorded trades"}
    hs = [_hour_side(trades_by[k]) for k in names]
    exp = np.eye(n)
    occ = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            shared = set(hs[i]) & set(hs[j])
            den = math.sqrt(len(hs[i]) * len(hs[j]))
            if not shared or den <= 0:
                continue
            tot = 0.0
            for h in shared:
                for si, ai in hs[i][h]:
                    for sj, aj in hs[j][h]:
                        tot += si * sj * leg_cosine(ai, aj)
            exp[i, j] = exp[j, i] = min(1.0, abs(tot) / den)
            occ[i, j] = occ[j, i] = min(1.0, len(shared) / den)
    uniq = 1.0 - np.max(exp - np.eye(n), axis=1)
    pairs = sorted(({"a": names[i], "b": names[j], "overlap": round(float(exp[i, j]), 4)}
                    for i in range(n) for j in range(i + 1, n) if exp[i, j] > 0),
                   key=lambda r: -float(r["overlap"]))  # type: ignore[arg-type]
    return {"status": "MEASURED", "n_sleeves": n,
            "n_trades": int(sum(len(trades_by[k]) for k in names)),
            "trade_overlap": round(participation_ratio(exp), 4),
            "co_occupancy": round(participation_ratio(occ), 4),
            "uniqueness": {names[i]: round(float(uniq[i]), 4) for i in range(n)},
            "most_overlapped": pairs[:10], "names": names, "similarity": exp}


def simulate_exposure(sleeves: Sequence[Mapping[str, Any]], returns: Mapping[str, Any],
                      session_hours: Mapping[str, Sequence[int]]) -> tuple[list[str], F]:
    """(names, T x N simulated hourly P&L). `sleeves`: {name, symbol, direction, selector};
    `returns`: symbol -> pandas Series of H1 log returns on a UTC DatetimeIndex. A sleeve is
    exposed at its direction's sign in its window's UTC hours ('continuous'/'all': every hour);
    a window the desk cannot place in hours is LEFT OUT, never guessed as always-on."""
    import pandas as pd
    cols: dict[str, Any] = {}
    for s in sleeves:
        r = returns.get(str(s.get("symbol")))
        if r is None or len(r) == 0:
            continue
        sel = str(s.get("selector") or "").lower()
        hours: list[int] | None
        if sel in ("continuous", "all"):
            hours = None
        elif sel in session_hours:
            hours = sorted({int(h) for h in session_hours[sel]})
        else:
            continue
        sign = -1.0 if str(s.get("direction") or "").upper() in ("SHORT", "SELL", "-1") else 1.0
        mask = (np.ones(len(r), dtype=bool) if hours is None
                else np.isin(np.asarray(r.index.hour), hours))
        cols[str(s["name"])] = pd.Series(np.where(mask, sign * r.to_numpy(dtype=float), 0.0),
                                         index=r.index)
    if len(cols) < 2:
        return list(cols), np.zeros((0, len(cols)))
    df = pd.DataFrame(cols).fillna(0.0)
    df = df.loc[(df != 0.0).any(axis=1)]
    return [str(c) for c in df.columns], df.to_numpy(dtype=float)


def pnl_similarity(pnl: F) -> F:
    """The elementwise max of the four return-based similarities rank_report reads."""
    x = np.nan_to_num(pnl.astype(float))
    out: F = np.maximum.reduce([np.abs(_corr(x)), np.abs(_corr(_rank(x))), tail_similarity(x),
                                drawdown_similarity(x)])
    return out


def combined_with(rank: Mapping[str, Any], names: Sequence[str],
                  descriptors: Sequence[Mapping[str, Any]] | None,
                  extra: Mapping[str, tuple[Sequence[str], F]]) -> dict[str, Any]:
    """The conservative combination over the registry's sleeves once the simulated readings
    are added: each extra similarity (on its own subset of names) is lifted onto the full name
    list -- a sleeve it could not read keeps the identity row there, i.e. contributes no
    dependence it did not measure -- and the elementwise max is taken with the descriptor
    similarity. `rank` is the descriptor/P&L report this refines; it is not modified."""
    n = len(names)
    idx = {k: i for i, k in enumerate(names)}
    mats: list[F] = []
    if descriptors is not None and len(descriptors) == n:
        mats.append(descriptor_similarity(descriptors))
    used: dict[str, int] = {}
    for label, (sub, sim) in extra.items():
        full = np.eye(n)
        pos = [(a, idx[k]) for a, k in enumerate(sub) if k in idx]
        for a, i in pos:
            for b, j in pos:
                if i != j:
                    full[i, j] = max(full[i, j], float(sim[a, b]))
        used[label] = len(pos)
        mats.append(full)
    if not mats:
        return {"combined": None, "why": "no similarity to combine"}
    comb = np.maximum.reduce(mats)
    return {"combined": round(participation_ratio(comb), 4),
            "descriptor_only": rank.get("combined"), "readings": used, "n_sleeves": n}
