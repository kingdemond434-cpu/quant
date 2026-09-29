"""THE INDEPENDENCE GRAPH OVER CERTIFIED EDGES -- and the one number it exists to publish.

    "North-star metric = effective independent alpha rank."        -- the principal, 2026-09-29

Every breadth reading the desk already has measures the LIVE BOOK: `alpha_breadth` from the
sleeves' exposures and realised returns, `mt5desk.independence` for the heat budget,
`exposure_decomposition` for factor loadings. None of them measures the thing research
produces, which is CERTIFICATES. A certificate that never reaches a clock is still either a new
independent source of return or a re-finding of one the desk already owns, and the only way to
tell is to put it in a graph with every other certificate and ask how many independent bets the
whole certified set is.

EIGHT CHANNELS, each a dependence in [0, 1] per pair, each MEASURED or NaN (UNMEASURED):

    pnl_corr            |corr| of daily P&L -- realised ledger P&L where both edges have
                        `min_overlap` shared days, else the INSTRUMENT PROXY (signed daily
                        instrument return), and the basis is recorded per pair
    tail_corr           excess lower-tail co-exceedance (lambda - q) / (1 - q): how much more often
                        than chance both lose their worst `q` days together
    regime_corr         |corr| inside a high prior-volatility regime whose label is LAGGED
                        (`effective_breadth.lagged_vol_regime`), so it is a regime and not a
                        collider
    factor_exposure     |cosine| of the signed currency/asset factor vectors
    feature_ancestry    Jaccard of the variable-level feature ids the two edges descend from
    timestamp_overlap   Jaccard of the UTC hours the two edges' declared sessions occupy
    same_mechanism      1 same family, 0.5 same mechanism class, 0 otherwise (NaN when either
                        mechanism is UNCLASSIFIED -- an unknown mechanism is not a different one)
    execution_exposure  1 same instrument, 0.25 same asset class in overlapping hours, else 0

THE COMBINATION IS CONSERVATIVE BY CONSTRUCTION, and it has to be, because every error in the
other direction buys leverage the evidence does not support:

    statistical = max over measured statistical channels   (the most dependent reading wins)
    structural  = mean over measured structural channels   (one shared attribute is not a clone)
    D_ij        = max(statistical, structural)
    a pair with NOTHING measured is D = 1 (assumed the same bet) and counted by name

    effective independent alpha rank = n^2 / sum_ij D_ij^2

which is the participation ratio of a correlation-like matrix: n independent edges give n, n
copies of one edge give 1. A certificate's MARGINAL contribution is the rank with it minus the
rank without it, and that is the number a producer is credited with (`producer_yield`).

PURE. No file is read here; `desks/mt5/research/alpha_rank.py` does the reading. Nothing here
sizes, gates or promotes -- it measures.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "CHANNELS",
    "CURRENCIES",
    "SCHEMA_VERSION",
    "SESSION_HOURS",
    "STATISTICAL",
    "STRUCTURAL",
    "Edge",
    "Graph",
    "build_graph",
    "effective_rank",
    "factor_vector",
    "producer_yield",
]

SCHEMA_VERSION = "independence_graph/1"

STATISTICAL: tuple[str, ...] = ("pnl_corr", "tail_corr", "regime_corr")
STRUCTURAL: tuple[str, ...] = ("factor_exposure", "feature_ancestry", "timestamp_overlap",
                               "same_mechanism", "execution_exposure")
CHANNELS: tuple[str, ...] = STATISTICAL + STRUCTURAL

#: The worst `TAIL_Q` of days is the tail. A tail estimate needs enough joint tail days to mean
#: anything, so the tail channel asks for `TAIL_MIN_OBS` overlapping observations.
TAIL_Q = 0.10
TAIL_MIN_OBS = 60
#: Two edges this dependent are ONE BET for the cluster listing (never for the rank, which uses
#: the continuous matrix).
SAME_BET = 0.70

#: DECLARED session hours in UTC. A selector the table does not know occupies the whole day,
#: which is the conservative direction: an unknown clock is assumed to overlap everything.
SESSION_HOURS: dict[str, frozenset[int]] = {
    "asia": frozenset(range(0, 7)),
    "tokyo": frozenset(range(0, 7)),
    "morning": frozenset(range(6, 10)),
    "london": frozenset(range(7, 12)),
    "london_am": frozenset(range(7, 11)),
    "afternoon": frozenset(range(12, 16)),
    "ny": frozenset(range(13, 21)),
    "newyork": frozenset(range(13, 21)),
    "overnight": frozenset((21, 22, 23, 0)),
}
ALL_DAY: frozenset[int] = frozenset(range(24))

CURRENCIES: frozenset[str] = frozenset((
    "USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK", "DKK", "ZAR", "MXN",
    "TRY", "PLN", "HUF", "CZK", "SGD", "HKD", "CNH", "ILS", "THB", "XAU", "XAG", "XPT", "XPD"))


@dataclass(frozen=True)
class Edge:
    """One certified edge, reduced to what independence is measured on."""

    key: str
    symbol: str
    family: str
    mechanism: str
    side: int = 0                                  # +1 long, -1 short, 0 undeclared
    session: str = "any"
    asset_class: str = ""
    feature_ids: frozenset[str] = field(default_factory=frozenset)
    producer: str | None = None


def factor_vector(symbol: str, side: int) -> dict[str, float]:
    """Signed factor exposure: a currency pair loads +side on its base and -side on its quote;
    anything else loads on itself. An undeclared side is +1 -- the cosine is taken in absolute
    value, so the sign convention cannot flatter a pair."""
    s = str(symbol).upper()
    sign = float(side) if side in (-1, 1) else 1.0
    if len(s) == 6 and s[:3] in CURRENCIES and s[3:] in CURRENCIES:
        return {s[:3]: sign, s[3:]: -sign}
    return {s: sign}


def _cos(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    num = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return abs(num) / (na * nb) if na > 0 and nb > 0 else 0.0


def _jaccard(a: frozenset[Any], b: frozenset[Any]) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def _hours(session: str) -> frozenset[int]:
    return SESSION_HOURS.get(str(session or "").lower().strip(), ALL_DAY)


def effective_rank(d: np.ndarray) -> float | None:
    """n^2 / ||D||_F^2 for a dependence matrix with unit diagonal; None when empty."""
    n = int(d.shape[0]) if d.ndim == 2 else 0
    if n == 0:
        return None
    denom = float(np.sum(d * d))
    return float(n * n / denom) if denom > 0 else None


def _pair_series(x: Mapping[str, float], y: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    common = sorted(set(x) & set(y))
    return (np.asarray([x[k] for k in common], dtype="float64"),
            np.asarray([y[k] for k in common], dtype="float64"))


def _abs_corr(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 3 or float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    c = float(np.corrcoef(a, b)[0, 1])
    return abs(c) if math.isfinite(c) else None


def _tail(a: np.ndarray, b: np.ndarray, two_sided: bool, q: float = TAIL_Q) -> float | None:
    """Excess co-exceedance, symmetrised. Lower tail of signed P&L; when either side is
    undeclared the P&L sign is unknown, so the tail is the largest |move| instead."""
    if a.size < TAIL_MIN_OBS:
        return None
    if two_sided:
        a, b = -np.abs(a), -np.abs(b)
    qa, qb = float(np.quantile(a, q)), float(np.quantile(b, q))
    ia, ib = a <= qa, b <= qb
    if not ia.any() or not ib.any():
        return None
    lam = 0.5 * (float(np.mean(ib[ia])) + float(np.mean(ia[ib])))
    return float(min(1.0, max(0.0, (lam - q) / (1.0 - q))))


@dataclass
class Graph:
    keys: list[str]
    channels: dict[str, np.ndarray]
    combined: np.ndarray
    pnl_basis: dict[str, int]
    n_pairs_unmeasured: int

    def rank(self) -> float | None:
        return effective_rank(self.combined)

    def channel_rank(self, name: str) -> dict[str, Any]:
        """The rank on one channel alone, over the pairs it measured. Below half coverage it is
        UNMEASURED: a rank read off a matrix that is mostly assumed is an assumption."""
        m = self.channels[name]
        n = len(self.keys)
        off = n * (n - 1)
        measured = int(np.sum(np.isfinite(m))) - n if n else 0
        cov = (measured / off) if off else 0.0
        if n < 2 or cov < 0.5:
            return {"rank": None, "coverage": round(cov, 4), "status": "UNMEASURED",
                    "why": (f"{name} measured {measured} of {off} ordered pairs; below half "
                            "coverage a single-channel rank is an assumption, not a reading")}
        filled = np.where(np.isfinite(m), m, 0.0)
        np.fill_diagonal(filled, 1.0)
        r = effective_rank(filled)
        return {"rank": round(r, 4) if r is not None else None, "coverage": round(cov, 4),
                "status": "MEASURED"}

    def marginal(self) -> dict[str, float]:
        """Leave-one-out: how much independent rank each edge adds to the rest."""
        n = len(self.keys)
        full = self.rank() or 0.0
        out: dict[str, float] = {}
        for i, k in enumerate(self.keys):
            if n == 1:
                out[k] = round(full, 6)
                continue
            idx = [j for j in range(n) if j != i]
            sub = self.combined[np.ix_(idx, idx)]
            out[k] = round(full - (effective_rank(sub) or 0.0), 6)
        return out

    def clusters(self, threshold: float = SAME_BET) -> list[list[str]]:
        """Connected components at D >= threshold: edges that are one bet under several names."""
        n = len(self.keys)
        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(n):
            for j in range(i + 1, n):
                if self.combined[i, j] >= threshold:
                    parent[find(i)] = find(j)
        groups: dict[int, list[str]] = {}
        for i, k in enumerate(self.keys):
            groups.setdefault(find(i), []).append(k)
        return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def build_graph(edges: Sequence[Edge],
                realised: Mapping[str, Mapping[str, float]] | None = None,
                proxy: Mapping[str, Sequence[float]] | None = None,
                regime: Sequence[float] | None = None,
                *, min_overlap: int = 20, regime_quantile: float = 0.20) -> Graph:
    """The eight channel matrices and their conservative combination.

    `realised` maps an edge KEY to its dated daily P&L; `proxy` maps a SYMBOL to an aligned daily
    return list (every list the same length and date order); `regime` is the lagged regime series
    on that same index (NaN where unavailable). Any of the three may be absent, and the channels
    that need it read NaN rather than a guess.
    """
    keys = [e.key for e in edges]
    n = len(keys)
    ch = {c: np.full((n, n), np.nan) for c in CHANNELS}
    basis = {"realised": 0, "instrument_proxy": 0, "unmeasured": 0}
    realised = realised or {}
    proxy = proxy or {}
    reg = np.asarray(regime, dtype="float64") if regime is not None else None
    hi_mask: np.ndarray | None = None
    if reg is not None and reg.size and np.isfinite(reg).sum() >= 2 * min_overlap:
        cut = float(np.nanquantile(reg, 1.0 - regime_quantile))
        hi_mask = np.isfinite(reg) & (reg >= cut)

    def signed(e: Edge) -> np.ndarray | None:
        r = proxy.get(e.symbol)
        if r is None:
            return None
        a = np.asarray(r, dtype="float64")
        return a * (e.side if e.side in (-1, 1) else 1.0)

    vecs = [factor_vector(e.symbol, e.side) for e in edges]
    for i in range(n):
        for c in CHANNELS:
            ch[c][i, i] = 1.0
    for i in range(n):
        ei = edges[i]
        for j in range(i + 1, n):
            ej = edges[j]
            v: dict[str, float | None] = dict.fromkeys(CHANNELS)
            two_sided = not (ei.side in (-1, 1) and ej.side in (-1, 1))
            # --- statistical: realised first, the instrument proxy only where realised is short
            ri, rj = realised.get(ei.key), realised.get(ej.key)
            used = None
            if ri and rj:
                a, b = _pair_series(ri, rj)
                if a.size >= min_overlap:
                    v["pnl_corr"] = _abs_corr(a, b)
                    v["tail_corr"] = _tail(a, b, two_sided)
                    used = "realised" if v["pnl_corr"] is not None else None
            si, sj = signed(ei), signed(ej)
            if si is not None and sj is not None and si.size == sj.size:
                if used is None:
                    v["pnl_corr"] = _abs_corr(si, sj)
                    used = "instrument_proxy" if v["pnl_corr"] is not None else None
                if v["tail_corr"] is None:
                    v["tail_corr"] = _tail(si, sj, two_sided)
                if hi_mask is not None and hi_mask.size == si.size \
                        and int(hi_mask.sum()) >= min_overlap:
                    v["regime_corr"] = _abs_corr(si[hi_mask], sj[hi_mask])
            basis[used or "unmeasured"] += 1
            # --- structural: declared attributes, never inferred from a name
            v["factor_exposure"] = _cos(vecs[i], vecs[j])
            if ei.feature_ids and ej.feature_ids:
                v["feature_ancestry"] = _jaccard(ei.feature_ids, ej.feature_ids)
            v["timestamp_overlap"] = _jaccard(_hours(ei.session), _hours(ej.session))
            if "UNCLASSIFIED" not in (ei.mechanism, ej.mechanism):
                v["same_mechanism"] = (1.0 if ei.family == ej.family else
                                       0.5 if ei.mechanism == ej.mechanism else 0.0)
            overlap = bool(_hours(ei.session) & _hours(ej.session))
            v["execution_exposure"] = (1.0 if ei.symbol == ej.symbol else
                                       0.25 if (ei.asset_class and ei.asset_class == ej.asset_class
                                                and overlap) else 0.0)
            for c, x in v.items():
                if x is not None:
                    ch[c][i, j] = ch[c][j, i] = float(x)
    comb = np.ones((n, n))
    unmeasured = 0
    for i in range(n):
        for j in range(i + 1, n):
            st = [ch[c][i, j] for c in STATISTICAL if np.isfinite(ch[c][i, j])]
            sr = [ch[c][i, j] for c in STRUCTURAL if np.isfinite(ch[c][i, j])]
            parts = ([max(st)] if st else []) + ([float(np.mean(sr))] if sr else [])
            if parts:
                d = max(parts)
            else:
                d = 1.0
                unmeasured += 1
            comb[i, j] = comb[j, i] = d
    return Graph(keys=keys, channels=ch, combined=comb, pnl_basis=basis,
                 n_pairs_unmeasured=unmeasured)


def producer_yield(edges: Iterable[Edge], marginal: Mapping[str, float]) -> dict[str, float]:
    """Sum of marginal independent rank per producer. An edge with no producer is credited to
    nobody (`None` is dropped), never spread by guesswork."""
    out: dict[str, float] = {}
    for e in edges:
        if e.producer:
            out[e.producer] = round(out.get(e.producer, 0.0) + float(marginal.get(e.key, 0.0)), 6)
    return out
