"""THE PHYSICS WING, second cohort: nine more traditions -- the cross-asset graph as a physical
network, information as a physical flow, dimensionless groups, symmetry, conservation, first
passage and Kramers escape, an agent-based simulator, inverse problems, and random matrices.

Each is a different search distribution over the same panel, numpy only, bounded, and honest
about what it could not measure. A physicist's habit these nine share: before asking WHAT
predicts the residual they ask what the residual is ALLOWED to depend on -- which combinations
are dimensionless, which symmetries the law must respect, which quantities are conserved, which
eigenmodes are signal and which are the Marchenko-Pastur bulk -- so the search space is cut by
physics before any statistics is spent on it.
"""
from __future__ import annotations

import math
from itertools import combinations
from typing import Any

import numpy as np

from . import grammar as G
from .base import UNMEASURED, Scientist, _corr, _finite, _nearest_window, _quiet, _z
from .objects import MathObject, Panel
from .physics import (
    _acf,
    _era_values,
    _fluct,
    _fluct_kind,
    _kurtosis,
    _loglog_fit,
    _realised,
    _side,
    _train_corr,
)
from .scientists_ext import _mint, _quantile_bins, _transfer_entropy


# ------------------------------------------------------------------------------- helpers
def _node_matrix(panel: Panel, rows: np.ndarray | None = None
                 ) -> tuple[np.ndarray, list[str], str]:
    """(n x k) z-scored node matrix: the peers when there are at least three, else the bars."""
    if len(panel.peers) >= 3:
        names = sorted(panel.peers)
        cols = [np.nan_to_num(_finite(panel.peers[k])) for k in names]
        source = "peers"
    else:
        names = [c for c in G.BAR_VARIABLES if c in panel.columns
                 and c not in ("open", "high", "low")]
        cols = [np.nan_to_num(_finite(panel.columns[c])) for c in names]
        source = "columns"
    if not cols:
        return np.empty((panel.n, 0)), [], source
    matrix = np.column_stack([_z(c) for c in cols])
    return (matrix if rows is None else matrix[rows]), names, source


def _components(adjacency: np.ndarray) -> int:
    """Size of the largest connected component of a boolean adjacency matrix."""
    k = adjacency.shape[0]
    seen = np.zeros(k, dtype=bool)
    best = 0
    for start in range(k):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for nxt in np.flatnonzero(adjacency[node] & ~seen):
                seen[nxt] = True
                stack.append(int(nxt))
        best = max(best, size)
    return best


# ==================================================================== 11. network physics
class NetworkPhysics(Scientist):
    """The cross-asset correlation graph as a physical network: Laplacian spectrum, percolation
    threshold, and centrality-weighted peer field.

    The algebraic connectivity (second Laplacian eigenvalue) says how hard the market is to cut
    in two; the percolation threshold is the correlation at which the giant component breaks
    -- a market that stays connected down to a low threshold is one shock away from moving as
    one. The peer field is the centrality-weighted mean of the peers' recent moves, minted as a
    column the target's residual can be read against.
    """

    tradition = "network_physics"
    searches_for = ("representation", "law", "relationship", "mechanism")

    THRESHOLDS = tuple(round(0.05 * i, 2) for i in range(1, 20))

    @classmethod
    def percolation(cls, corr: np.ndarray) -> tuple[float | None, list[float]]:
        k = corr.shape[0]
        weight = np.abs(corr)
        np.fill_diagonal(weight, 0.0)
        curve = [_components(weight > th) / k for th in cls.THRESHOLDS]
        threshold = next((th for th, frac in zip(cls.THRESHOLDS, curve, strict=False)
                          if frac < 0.5), None)
        return threshold, curve

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        train, _ = panel.split()
        matrix, names, source = _node_matrix(panel)
        if len(names) < 3:
            self.note("graph", "fewer than three nodes (no peers and too few bar columns)")
            return []
        if source == "columns":
            self.note("peers", "the panel carries fewer than three peers; the graph is over the "
                               "panel's own bar columns")
        corr = np.corrcoef(matrix[train].T)
        corr = np.nan_to_num(corr)
        weight = np.abs(corr)
        np.fill_diagonal(weight, 0.0)
        laplacian = np.diag(weight.sum(1)) - weight
        eig = np.sort(np.linalg.eigvalsh(laplacian))
        connectivity = float(eig[1]) if eig.size > 1 else 0.0
        threshold, curve = self.percolation(corr)
        vec = np.ones(len(names)) / math.sqrt(len(names))
        for _ in range(60):
            nxt = weight @ vec
            norm = float(np.linalg.norm(nxt))
            if norm < 1e-12:
                break
            vec = nxt / norm
        centrality = np.abs(vec) / max(1e-12, float(np.abs(vec).sum()))
        field = matrix @ centrality
        name = _mint(self, panel, "peer_field" if source == "peers" else "column_field", field,
                     "mathlab:network_physics", "z units")
        per_era = _era_values(panel, lambda rows: self.percolation(
            np.nan_to_num(np.corrcoef(matrix[rows].T)))[0])
        top = names[int(np.argmax(centrality))]
        diagnostics = {"nodes": len(names), "source": source,
                       "algebraic_connectivity": round(connectivity, 5),
                       "spectral_gap": round(float(eig[-1] - eig[-2]), 5) if eig.size > 2 else None,
                       "percolation_threshold": threshold, "giant_component_curve":
                       [round(v, 3) for v in curve], "per_era_threshold": per_era,
                       "centrality": {n: round(float(c), 4) for n, c in
                                      zip(names, centrality, strict=False)},
                       "most_central": top,
                       "method": "|corr| graph on the training slice; Laplacian eigenvalues; "
                                 "giant component under a threshold sweep; power-iteration "
                                 "eigenvector centrality"}
        corr_field = _train_corr(panel, field)
        out = [self.emit(panel, "representation", ["z", name, 48],
                         f"PEER FIELD: centrality-weighted mean of {len(names)} {source} "
                         f"(most central {top})", diagnostics=diagnostics),
               self.emit(panel, "relationship", ["z", name, 48],
                         f"the peer field reads the residual with training IC {corr_field:+.4f}",
                         side_mode=_side(corr_field), diagnostics=diagnostics),
               self.emit(panel, "law", ["rstd", name, 48],
                         f"PERCOLATION: the giant component breaks at |corr| = {threshold}; "
                         f"algebraic connectivity {connectivity:.4f}; per era {per_era}",
                         diagnostics=diagnostics)]
        if threshold is not None and threshold >= 0.5:
            out.append(self.emit(panel, "mechanism", ["mul", ["z", name, 48], ["rstd", name, 48]],
                                 f"ONE SHOCK FROM MOVING AS ONE: the market stays connected down "
                                 f"to |corr| {threshold}; the residual is the part of the target "
                                 f"the giant component does not explain", diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


# ==================================================================== 12. information physics
class InformationPhysics(Scientist):
    """Mutual information and NET transfer entropy: which variable carries information about the
    residual, at which lag, and in which direction it flows.

    Net transfer entropy TE(x -> eps) - TE(eps -> x) is the direction of the arrow; a driver
    that receives as much as it sends is a shared shock, not a cause. The information rate per
    unit of dissipation (MI over the residual's variance) is the Landauer-flavoured question of
    how much of the residual's energy is information at all.
    """

    tradition = "information_physics"
    searches_for = ("relationship", "law", "search_method")

    LAGS = (2, 3, 5, 8)
    BINS = 6

    @classmethod
    def mutual_information(cls, a: np.ndarray, b: np.ndarray) -> float:
        mask = np.isfinite(a) & np.isfinite(b)
        if int(mask.sum()) < 100:
            return 0.0
        ba, bb = _quantile_bins(a[mask], cls.BINS), _quantile_bins(b[mask], cls.BINS)
        joint = np.zeros((cls.BINS, cls.BINS))
        np.add.at(joint, (ba, bb), 1.0)
        joint /= max(1.0, joint.sum())
        pa, pb = joint.sum(1, keepdims=True), joint.sum(0, keepdims=True)
        with _quiet():
            ratio = np.where(joint > 0, joint / np.maximum(pa * pb, 1e-15), 1.0)
            term = np.where(joint > 0, joint * np.log(ratio), 0.0)
        return float(term.sum())

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, _x = _realised(self, panel)
        train, _ = panel.split()
        eps = panel.epsilon
        candidates = [c for c in self.top_columns(panel, 8) if c != state][:6]
        if not candidates:
            self.note("columns", "no column to measure information against")
            return []
        table: dict[str, Any] = {}
        best: tuple[float, str, int] | None = None
        for c in candidates:
            series = np.nan_to_num(_finite(panel.columns[c]))
            null = self.mutual_information(eps[train], rng.permutation(series[train]))
            for k in self.LAGS:
                rows = train[train >= k]
                mi = self.mutual_information(eps[rows], series[rows - k])
                self.evaluated += 1
                table[f"{c}@{k}"] = {"mi": round(mi, 5), "null": round(null, 5),
                                     "excess": round(mi - null, 5)}
                if best is None or mi - null > best[0]:
                    best = (mi - null, c, k)
        if best is None:
            self.note("mutual_information", "no (column, lag) pair carried 100 usable rows")
            return []
        excess, column, lag = best
        driver = np.nan_to_num(_finite(panel.columns[column]))
        te_in = _transfer_entropy(driver[train], np.nan_to_num(eps)[train], lag)
        te_out = _transfer_entropy(np.nan_to_num(eps)[train], driver[train], lag)
        net = (te_in - te_out) if te_in is not None and te_out is not None else None
        per_era_net = _era_values(panel, lambda rows: (
            (_transfer_entropy(driver[rows], np.nan_to_num(eps)[rows], lag) or 0.0)
            - (_transfer_entropy(np.nan_to_num(eps)[rows], driver[rows], lag) or 0.0)))
        variance = float(np.var(eps[train]))
        rate = excess / variance if variance > 1e-15 else None
        rows = train[train >= lag]
        corr = _corr(eps[rows], driver[rows - lag])
        diagnostics = {"best": {"column": column, "lag": lag, "excess_mi": round(excess, 5)},
                       "table": table, "transfer_entropy_in": te_in, "transfer_entropy_out": te_out,
                       "net_flow": round(net, 5) if net is not None else None,
                       "per_era_net_flow": per_era_net,
                       "information_per_unit_variance": round(rate, 4) if rate else None,
                       "bins": self.BINS,
                       "method": "quantile-binned MI against a shuffled null; TE in both "
                                 "directions at the best lag; net flow per era"}
        if net is None:
            self.note("transfer_entropy", "fewer than 200 aligned rows at the best lag")
        tree: Any = (["lag", column, _nearest_window(lag)] if abs(corr) > 0.02
                     else ["abs", ["z", column, 24]])
        out = [self.emit(panel, "relationship", tree,
                         f"INFORMATION: {column} at lag {lag} carries {excess:.4f} nats above its "
                         f"shuffled null (linear IC {corr:+.4f}; the "
                         f"{'signed' if abs(corr) > 0.02 else 'magnitude'} form is traded)",
                         side_mode=_side(corr), diagnostics=diagnostics),
               self.emit(panel, "law", ["lag", column, _nearest_window(lag)],
                         f"NET FLOW {column} -> residual: {diagnostics['net_flow']} nats "
                         f"(in {te_in}, out {te_out}); per era {per_era_net}",
                         diagnostics=diagnostics),
               self.emit(panel, "search_method", column,
                         f"MI-RANKED VARIABLE ORDER: search {column} first -- it carries "
                         f"{excess:.4f} excess nats, the most of {len(candidates)} columns; a "
                         f"variable order is a search operator", diagnostics=diagnostics)]
        _ = deadline
        return out


# ==================================================================== 13. dimensional analysis
#: (price, ticks) exponents of every bar terminal, from `alpha_grammar.terminal_frames`.
UNITS: dict[str, tuple[int, int]] = {
    "close": (1, 0), "open": (1, 0), "high": (1, 0), "low": (1, 0), "atr": (1, 0),
    "spread": (1, 0), "ret": (0, 0), "range": (0, 0), "body": (0, 0), "vol": (0, 0),
    "activity": (0, 1), "flow": (0, 1),
}


class DimensionalAnalysis(Scientist):
    """Buckingham pi: only dimensionless groups may enter a law.

    Every bar terminal carries a (price, ticks) dimension vector. The lattice null space of the
    dimension matrix -- monomials with exponents in {-1, 0, 1} over up to three terminals whose
    net dimension is zero -- is the set of pi groups; each is evaluated and scored against the
    residual, and the law object records whether the best dimensionless group beats the best
    dimensioned raw terminal, which is what "the law is dimensionally consistent" measures.
    """

    tradition = "dimensional_analysis"
    searches_for = ("representation", "law", "relationship")

    MAX_GROUPS = 24

    @staticmethod
    def groups(available: list[str]) -> list[tuple[Any, dict[str, int]]]:
        out: list[tuple[Any, dict[str, int]]] = []
        seen: set[str] = set()
        dimensioned = [c for c in available if UNITS.get(c, (0, 0)) != (0, 0)]
        dimensionless = [c for c in available if UNITS.get(c) == (0, 0)]
        for a, b in combinations(dimensioned, 2):
            if UNITS[a] == UNITS[b]:
                for num, den in ((a, b), (b, a)):
                    tree = ["div", num, den]
                    key = G.to_str(tree)
                    if key not in seen:
                        seen.add(key)
                        out.append((tree, {num: 1, den: -1}))
        for tree, powers in list(out):
            for c in dimensionless[:3]:
                mixed = ["mul", tree, c]
                key = G.to_str(mixed)
                if key not in seen:
                    seen.add(key)
                    out.append((mixed, {**powers, c: 1}))
        return out

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        available = [c for c in G.BAR_VARIABLES if c in panel.columns]
        groups = self.groups(available)[:self.MAX_GROUPS]
        if not groups:
            self.note("pi_groups", "fewer than two bar terminals share a dimension")
            return []
        scored: list[tuple[float, Any, dict[str, int]]] = []
        for tree, powers in groups:
            with _quiet():
                values = G.evaluate(["z", tree, 48], panel.columns, panel.n)
            ic = _train_corr(panel, np.nan_to_num(values))
            self.charge(tree)
            scored.append((ic, tree, powers))
        scored.sort(key=lambda r: -abs(r[0]))
        raw: list[tuple[float, str]] = []
        for c in available:
            if UNITS.get(c, (0, 0)) != (0, 0):
                with _quiet():
                    values = G.evaluate(["z", c, 48], panel.columns, panel.n)
                raw.append((_train_corr(panel, np.nan_to_num(values)), c))
        raw.sort(key=lambda r: -abs(r[0]))
        best_ic, best_tree, best_powers = scored[0]
        best_raw = raw[0] if raw else (0.0, "")
        per_era = _era_values(panel, lambda rows: _corr(
            np.nan_to_num(G.evaluate(["z", best_tree, 48], panel.columns, panel.n))[rows],
            panel.epsilon[rows]))
        diagnostics = {"pi_groups_scored": len(scored),
                       "best_group": {"expression": G.to_str(best_tree), "powers": best_powers,
                                      "ic_train": round(best_ic, 4)},
                       "best_dimensioned_terminal": {"name": best_raw[1],
                                                     "ic_train": round(best_raw[0], 4)},
                       "top": [{"expression": G.to_str(t), "ic": round(ic, 4)}
                               for ic, t, _p in scored[:5]],
                       "per_era_ic": per_era, "units": {c: UNITS[c] for c in available},
                       "method": "lattice null space of the (price, ticks) dimension matrix over "
                                 "pairs and pair x dimensionless products; IC on the training "
                                 "slice"}
        consistent = abs(best_ic) >= abs(best_raw[0])
        out = [self.emit(panel, "representation", best_tree,
                         f"PI GROUP {G.to_str(best_tree)}: dimensionless by construction "
                         f"(powers {best_powers})", diagnostics=diagnostics),
               self.emit(panel, "relationship", ["z", best_tree, 48],
                         f"the best pi group reads the residual with training IC {best_ic:+.4f}",
                         side_mode=_side(best_ic), diagnostics=diagnostics),
               self.emit(panel, "law", ["z", best_tree, 48],
                         f"DIMENSIONAL CONSISTENCY {'HOLDS' if consistent else 'FAILS'}: the best "
                         f"dimensionless group scores {best_ic:+.4f} against {best_raw[0]:+.4f} "
                         f"for the best dimensioned terminal ({best_raw[1]}); per era {per_era}",
                         diagnostics=diagnostics)]
        _ = (deadline, rng)
        return out


# ==================================================================== 14. symmetry / invariance
class SymmetryInvariance(Scientist):
    """Which symmetries does the residual's law respect, and which does it break?

    Sign symmetry: the response to a return is odd (f(-r) = -f(r)) or has an even part.
    Time translation: the residual's distribution is the same in every era (a two-sample
    Kolmogorov-Smirnov distance). Scale invariance: the volatility-normalised return carries the
    relation as well as the raw one. Session symmetry: the residual's mean is the same clock
    to clock. A broken symmetry is a mechanism; the unbroken ones cut the search space.
    """

    tradition = "symmetry_invariance"
    searches_for = ("law", "relationship", "mechanism")

    EDGES = (-1.5, -0.75, -0.25, 0.0, 0.25, 0.75, 1.5)

    @staticmethod
    def ks_distance(a: np.ndarray, b: np.ndarray) -> float:
        a, b = np.sort(a[np.isfinite(a)]), np.sort(b[np.isfinite(b)])
        if a.size < 30 or b.size < 30:
            return 0.0
        grid = np.concatenate([a, b])
        fa = np.searchsorted(a, grid, side="right") / a.size
        fb = np.searchsorted(b, grid, side="right") / b.size
        return float(np.max(np.abs(fa - fb)))

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("ret", "the panel carries no return column")
            return []
        train, _ = panel.split()
        eps = panel.epsilon
        y = np.nan_to_num(G.evaluate(["z", "ret", 24], panel.columns, panel.n))
        bins = np.digitize(y[train], self.EDGES)
        means = np.full(len(self.EDGES) + 1, np.nan)
        for b in range(len(self.EDGES) + 1):
            rows = train[bins == b]
            if rows.size >= 20:
                means[b] = float(np.mean(eps[rows]))
        mirrored = means[::-1]
        both = np.isfinite(means) & np.isfinite(mirrored)
        odd = 0.5 * (means[both] - mirrored[both])
        even = 0.5 * (means[both] + mirrored[both])
        odd_norm, even_norm = float(np.sqrt(np.mean(odd ** 2))), float(np.sqrt(np.mean(even ** 2)))
        even_share = even_norm / max(1e-12, odd_norm + even_norm)
        eras = panel.eras(4)
        ks = [self.ks_distance(eps[eras == e], eps[eras == e + 1]) for e in range(3)]
        ic_scaled = _train_corr(panel, y)
        ic_raw = _train_corr(panel, np.nan_to_num(_finite(panel.columns["ret"])))
        sessions: dict[str, float] = {}
        if panel.session is not None:
            for s in sorted(set(panel.session[train].tolist())):
                rows = train[panel.session[train] == s]
                if rows.size >= 40:
                    sessions[str(s)] = float(np.mean(eps[rows]))
        pooled = float(np.std(eps[train]) / math.sqrt(max(1, train.size / max(1, len(sessions)))))
        session_break = (max(sessions.values()) - min(sessions.values())) / max(1e-12, pooled) \
            if len(sessions) >= 2 else 0.0
        diagnostics = {"conditional_means_by_return_bin": [round(v, 6) if math.isfinite(v)
                                                           else None for v in means],
                       "odd_norm": round(odd_norm, 6), "even_norm": round(even_norm, 6),
                       "even_share": round(even_share, 4), "ks_between_eras":
                       [round(v, 4) for v in ks], "ic_scaled": round(ic_scaled, 4),
                       "ic_raw": round(ic_raw, 4), "session_means": {k: round(v, 6)
                                                                     for k, v in sessions.items()},
                       "session_break_t": round(session_break, 3),
                       "method": "odd/even decomposition of the binned response; KS between "
                                 "consecutive eras; scaled vs raw IC; session means in t units"}
        odd_tree = ["z", "ret", 24]
        even_tree = ["abs", ["z", "ret", 24]]
        out = [self.emit(panel, "law", odd_tree,
                         f"SIGN SYMMETRY: the response to a return is {even_share:.0%} even "
                         f"({'broken' if even_share > 0.4 else 'odd, symmetric'}); time "
                         f"translation KS {ks} between eras; scale invariance IC scaled "
                         f"{ic_scaled:+.4f} vs raw {ic_raw:+.4f}", diagnostics=diagnostics)]
        if even_share > 0.4:
            corr = _train_corr(panel, np.nan_to_num(G.evaluate(even_tree, panel.columns, panel.n)))
            out.append(self.emit(panel, "relationship", even_tree,
                                 f"the EVEN part of the response is traded: |z(ret)| reads the "
                                 f"residual with training IC {corr:+.4f}", side_mode=_side(corr),
                                 diagnostics=diagnostics))
        else:
            out.append(self.emit(panel, "relationship", odd_tree,
                                 f"the ODD response is traded: z(ret) reads the residual with "
                                 f"training IC {ic_scaled:+.4f}", side_mode=_side(ic_scaled),
                                 diagnostics=diagnostics))
        if abs(session_break) > 2.5:
            hot = max(sessions, key=lambda k: abs(sessions[k]))
            out.append(self.emit(panel, "mechanism", ["mul", ["sign", "ret"], ["rstd", "ret", 24]],
                                 f"SESSION SYMMETRY BROKEN (t {session_break:.2f}): the residual's "
                                 f"mean differs by clock, largest in {hot} -- the law has a "
                                 f"time-of-day term", diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


# ==================================================================== 15. conservation laws
class ConservationLaws(Scientist):
    """Approximately conserved quantities: the linear combination of state variables whose
    increments are smallest relative to its level -- a first integral of the dynamics.

    With S the matrix of standardised state variables and dS its increments, the generalised
    eigenvector w minimising var(w dS) / var(w S) is the direction along which the system does
    not move: a Noether-style invariant fitted from data. An excursion of a conserved quantity
    is, by construction, undone, so the invariant's deviation is the relationship traded.
    """

    tradition = "conservation_laws"
    searches_for = ("law", "representation", "relationship")

    FEATURES = (("ret", ["z", "ret", 24]), ("range", ["z", "range", 24]),
                ("body", ["z", "body", 24]), ("activity", ["z", "activity", 24]),
                ("flow", ["z", "flow", 24]))

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        feats = [(n, t) for n, t in self.FEATURES if n in panel.columns]
        if len(feats) < 3:
            self.note("state", "fewer than three state variables on the panel")
            return []
        with _quiet():
            S = np.column_stack([np.nan_to_num(G.evaluate(t, panel.columns, panel.n))
                                 for _n, t in feats])
        train, _ = panel.split()
        dS = np.diff(S, axis=0, prepend=S[:1])
        cs = np.cov(S[train].T) + 1e-6 * np.eye(S.shape[1])
        cd = np.cov(dS[train].T) + 1e-6 * np.eye(S.shape[1])
        vals, vecs = np.linalg.eigh(cs)
        inv_sqrt = vecs @ np.diag(1.0 / np.sqrt(np.maximum(vals, 1e-12))) @ vecs.T
        whitened = inv_sqrt @ cd @ inv_sqrt
        ratios, directions = np.linalg.eigh(whitened)
        chosen = 0
        for chosen in range(ratios.size):
            w = inv_sqrt @ directions[:, chosen]
            w = w / max(1e-12, float(np.abs(w).max()))
            quantity = S @ w
            if float(np.var(quantity[train])) > 1e-8:
                break
            # An EXACTLY conserved direction is a linear identity between columns (two
            # terminals that are the same series), not a dynamical invariant; name it and move on.
            self.note("trivial_invariant", "direction " + ", ".join(
                f"{feats[i][0]}:{w[i]:+.2f}" for i in range(len(feats)) if abs(w[i]) > 0.05)
                + " is an exact linear identity between columns")
        else:
            self.note("invariant", "every direction is an exact linear identity")
            return []
        ratio = float(ratios[chosen])
        worst = float(ratios[-1])
        name = _mint(self, panel, "conserved_quantity", quantity, "mathlab:conservation_laws",
                     "z units")
        per_era = _era_values(panel, lambda rows: float(np.var(np.diff(quantity[rows]))
                                                        / max(1e-12, np.var(quantity[rows]))))
        order = np.argsort(-np.abs(w))[:2]
        terms = [(feats[i][0], feats[i][1], round(float(w[i]), 2)) for i in order]
        expr: Any = ["mul", terms[0][1], terms[0][2]]
        if len(terms) > 1 and abs(terms[1][2]) >= 0.05:
            expr = ["add", expr, ["mul", terms[1][1], terms[1][2]]]
        diagnostics = {"weights": {n: round(float(w[i]), 4) for i, (n, _t) in enumerate(feats)},
                       "conservation_ratio": round(ratio, 5),
                       "least_conserved_ratio": round(worst, 5), "per_era_ratio": per_era,
                       "method": "generalised eigenproblem var(w dS) / var(w S); the smallest "
                                 "ratio is the most conserved direction"}
        corr = _train_corr(panel, np.nan_to_num(G.evaluate(["z", expr, 48], panel.columns,
                                                           panel.n)))
        out = [self.emit(panel, "law", expr,
                         "CONSERVED QUANTITY: "
                         + " + ".join(f"{c:+.2f}*z({n},24)" for n, _t, c in terms)
                         + f" moves with increment/level variance ratio {ratio:.4f} against "
                         f"{worst:.4f} for the least conserved direction; per era {per_era}",
                         diagnostics=diagnostics),
               self.emit(panel, "representation", ["z", name, 48],
                         "the conserved quantity's deviation from its 48-bar mean",
                         diagnostics=diagnostics),
               self.emit(panel, "relationship", ["z", expr, 48],
                         f"an excursion of the invariant reads the residual with training IC "
                         f"{corr:+.4f}", side_mode=_side(corr), diagnostics=diagnostics)]
        _ = (deadline, rng)
        return out


# ==================================================================== 16. stochastic physics
class StochasticPhysics(Scientist):
    """First-passage statistics and Kramers escape from a fitted potential.

    The first-passage time of the standardised residual walk to a barrier L has, for a
    Brownian walk, a survival tail proportional to t^(-1/2) and a mean that scales as L^2. The
    potential U(x) = -ln p(x) fitted to the residual's histogram either has one well (a
    single equilibrium) or two (metastable states); the barrier height sets the Kramers escape
    rate exp(-dU), which is compared with the crossing rate actually observed.
    """

    tradition = "stochastic_physics"
    searches_for = ("law", "mechanism", "relationship")

    BARRIERS = (1.0, 2.0)

    @staticmethod
    def first_passage(z: np.ndarray, barrier: float, stride: int = 8, max_t: int = 240
                      ) -> np.ndarray:
        times: list[int] = []
        for start in range(0, z.size - max_t, stride):
            path = np.cumsum(z[start:start + max_t])
            hit = np.flatnonzero(np.abs(path) >= barrier)
            times.append(int(hit[0]) + 1 if hit.size else max_t)
        return np.asarray(times, dtype=float)

    @staticmethod
    def tail_exponent(times: np.ndarray) -> float | None:
        if times.size < 40:
            return None
        grid = np.unique(times)
        grid = grid[(grid >= np.median(times)) & (grid < times.max())]
        if grid.size < 3:
            return None
        survival = np.asarray([float(np.mean(times > t)) for t in grid])
        fit = _loglog_fit(grid, survival)
        return fit[0] if fit else None

    @staticmethod
    def potential(z: np.ndarray, bins: int = 30) -> dict[str, Any]:
        hist, edges = np.histogram(np.clip(z, -3.5, 3.5), bins=bins, range=(-3.5, 3.5))
        p = np.convolve(hist / max(1.0, hist.sum()), np.ones(3) / 3.0, mode="same")
        with _quiet():
            u = -np.log(np.maximum(p, 1e-9))
        centres = 0.5 * (edges[1:] + edges[:-1])
        wells = [i for i in range(1, bins - 1) if u[i] < u[i - 1] and u[i] <= u[i + 1]
                 and p[i] > 0.01]
        barrier = None
        if len(wells) >= 2:
            lo, hi = wells[0], wells[-1]
            barrier = float(u[lo:hi + 1].max() - max(u[lo], u[hi]))
        return {"wells": [round(float(centres[i]), 3) for i in wells],
                "barrier": round(barrier, 4) if barrier is not None else None}

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, x = _realised(self, panel)
        with _quiet():
            sigma = G.evaluate(["rstd", state, 48], panel.columns, panel.n)
            z = np.where(np.isfinite(sigma) & (sigma > 1e-12), x / sigma, 0.0)
        train, _ = panel.split()
        fpt = {L: self.first_passage(z[train], L) for L in self.BARRIERS}
        if any(v.size < 40 for v in fpt.values()):
            self.note("first_passage", "fewer than 40 passages on the training slice")
            return []
        tails = {L: self.tail_exponent(v) for L, v in fpt.items()}
        means = {L: float(np.mean(v)) for L, v in fpt.items()}
        scaling = means[2.0] / max(1e-9, means[1.0])
        pot = self.potential(_z(x[train]))
        crossings = float(np.mean(np.abs(np.diff(np.sign(_z(x[train])))) > 0))
        kramers = math.exp(-pot["barrier"]) if pot["barrier"] is not None else None
        per_era = _era_values(panel, lambda rows: self.tail_exponent(
            self.first_passage(z[rows], 1.0)))
        diagnostics = {"fpt_tail_exponent": {str(L): (round(v, 4) if v is not None else None)
                                             for L, v in tails.items()},
                       "fpt_mean": {str(L): round(v, 3) for L, v in means.items()},
                       "mean_scaling_L2_over_L1": round(scaling, 3),
                       "brownian_prediction": {"tail": -0.5, "mean_scaling": 4.0},
                       "potential": pot, "kramers_rate": round(kramers, 5) if kramers else None,
                       "observed_crossing_rate": round(crossings, 5), "per_era_tail": per_era,
                       "method": "first passage of the sigma-scaled residual walk to +/-L from "
                                 "strided starts; U = -ln p from a 30-bin histogram; Kramers "
                                 "rate exp(-dU) at unit temperature"}
        gate = ["gt", ["abs", ["z", "ret", 24]], 2.0]
        tail1 = tails.get(1.0)
        out = [self.emit(panel, "law", gate,
                         f"FIRST PASSAGE: survival tail exponent {tail1} at L=1 (Brownian -0.5); "
                         f"mean FPT scales {scaling:.2f}x from L=1 to L=2 (Brownian 4); per era "
                         f"{per_era}", diagnostics=diagnostics)]
        if pot["barrier"] is not None and pot["barrier"] > 0.3:
            out.append(self.emit(panel, "mechanism", ["z", state, 48],
                                 f"METASTABLE STATES: two wells at {pot['wells']} with barrier "
                                 f"{pot['barrier']:.3f}; Kramers escape rate {kramers:.4f} "
                                 f"against an observed crossing rate {crossings:.4f}",
                                 diagnostics=diagnostics))
        after = np.nan_to_num(G.evaluate(gate, panel.columns, panel.n))
        hits = train[after[train] > 0.5]
        if hits.size >= 20:
            mean_after = float(np.mean(panel.epsilon[hits]))
            out.append(self.emit(panel, "relationship", ["mul", ["sign", "ret"], gate],
                                 f"after a barrier crossing (|z| > 2, {hits.size} events) the "
                                 f"residual averages {mean_after:+.6f}",
                                 side_mode=_side(mean_after), diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


# ==================================================================== 17. Monte Carlo / ABM
class MonteCarloABM(Scientist):
    """A minimal agent-based market (fundamentalists vs chartists with fitness switching),
    simulated on a small parameter grid and matched to the tape by the method of simulated
    moments.

    The simulator is not a forecast; it is a MECHANISM GENERATOR. The chartist gain and the
    switching intensity that reproduce the tape's kurtosis, magnitude autocorrelation and
    return autocorrelation are the mechanism proposed, the moment distance is the law, and the
    simulator itself is a search method: a null-generator with a mechanism inside it, which is
    what a shuffled series never is.
    """

    tradition = "monte_carlo_abm"
    searches_for = ("mechanism", "law", "search_method", "relationship")

    STEPS = 1200
    GAINS = (0.0, 0.4, 0.8)
    BETAS = (1.0, 4.0)

    @staticmethod
    def moments(r: np.ndarray) -> dict[str, float]:
        mag = np.abs(r)
        return {"kurtosis": _kurtosis(r), "acf_abs_1": _acf(mag, 1), "acf_abs_5": _acf(mag, 5),
                "acf_abs_12": _acf(mag, 12), "acf_1": _acf(r, 1)}

    @classmethod
    def simulate(cls, gain: float, beta: float, rng: np.random.Generator, steps: int
                 ) -> np.ndarray:
        p = np.zeros(steps + 2)
        share = 0.5
        out = np.zeros(steps)
        noise = rng.normal(0.0, 0.01, steps)
        for t in range(2, steps + 2):
            fund = -0.2 * p[t - 1]
            chart = gain * (p[t - 1] - p[t - 2])
            profit_f = fund * (p[t - 1] - p[t - 2])
            profit_c = chart * (p[t - 1] - p[t - 2])
            share = 1.0 / (1.0 + math.exp(-beta * (profit_c - profit_f) * 100.0))
            share = min(0.95, max(0.05, share))
            r = 0.5 * ((1 - share) * fund + share * chart) + noise[t - 2]
            p[t] = p[t - 1] + r
            out[t - 2] = r
        return out

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("ret", "the panel carries no return column")
            return []
        r = np.nan_to_num(_finite(panel.columns["ret"]))
        train, _ = panel.split()
        target = self.moments(r[train])
        scale = {"kurtosis": max(1.0, abs(target["kurtosis"])), "acf_abs_1": 0.1,
                 "acf_abs_5": 0.1, "acf_abs_12": 0.1, "acf_1": 0.1}
        table: list[dict[str, Any]] = []
        for gain in self.GAINS:
            for beta in self.BETAS:
                sim = self.simulate(gain, beta, rng, self.STEPS)
                mom = self.moments(sim)
                distance = math.sqrt(sum(((mom[k] - target[k]) / scale[k]) ** 2 for k in target))
                table.append({"gain": gain, "beta": beta, "distance": round(distance, 4),
                              "moments": {k: round(v, 4) for k, v in mom.items()}})
                self.evaluated += 1
        best = min(table, key=lambda row: row["distance"])
        diagnostics = {"target_moments": {k: round(v, 4) for k, v in target.items()},
                       "grid": table, "best": best, "steps": self.STEPS,
                       "method": "Brock-Hommes-style two-type market with logistic fitness "
                                 "switching; method of simulated moments over a 3 x 2 grid"}
        chartist = best["gain"] >= 0.4
        out = [self.emit(panel, "mechanism", ["diff", "close", 5],
                         f"AGENT MIX: the tape's moments are closest (distance {best['distance']}) "
                         f"to a market with chartist gain {best['gain']} and switching intensity "
                         f"{best['beta']} -- "
                         f"{'trend-followers' if chartist else 'fundamentalists'} dominate",
                         side_mode="follow" if chartist else "fade", diagnostics=diagnostics),
               self.emit(panel, "law", ["div", ["rstd", "ret", 5], ["rstd", "ret", 48]],
                         f"MOMENT SIGNATURE: kurtosis {target['kurtosis']:.2f}, |r| "
                         f"autocorrelation {target['acf_abs_1']:+.3f}/{target['acf_abs_5']:+.3f}/"
                         f"{target['acf_abs_12']:+.3f}, "
                         f"r autocorrelation {target['acf_1']:+.3f}; best simulated distance "
                         f"{best['distance']}", diagnostics=diagnostics),
               self.emit(panel, "search_method", ["z", "ret", 24],
                         "SIMULATOR AS NULL: an agent-based market with a mechanism inside it is "
                         "the null a discovered relationship must beat, not a shuffled series",
                         diagnostics=diagnostics)]
        corr = _train_corr(panel, np.nan_to_num(G.evaluate(["diff", "close", 5], panel.columns,
                                                           panel.n)))
        out.append(self.emit(panel, "relationship", ["diff", "close", 5],
                             f"5-bar momentum under the fitted agent mix reads the residual with "
                             f"training IC {corr:+.4f}", side_mode=_side(corr),
                             diagnostics=diagnostics))
        _ = deadline
        return out


# ==================================================================== 18. inverse problems
class InverseProblems(Scientist):
    """Tikhonov deconvolution of the kernel through which a driver reaches the residual.

    y_t = sum_k h_k d_{t-k} + noise over 24 lags is ill-posed on a noisy tape; the ridge
    parameter is chosen on a validation slice inside the training window (never on the test
    rows), and the recovered kernel's sign, effective length and decay rate are the object.
    The kernel-weighted driver is approximated for the trade grammar by a moving mean over the
    kernel's effective length, and the approximation is named in the notes.
    """

    tradition = "inverse_problems"
    searches_for = ("representation", "relationship", "law")

    K = 24
    LAMBDAS = (0.01, 0.1, 1.0, 10.0, 100.0)

    def kernel(self, driver: np.ndarray, y: np.ndarray, rows: np.ndarray, lam: float
               ) -> np.ndarray:
        design = np.column_stack([driver[rows - k] for k in range(1, self.K + 1)])
        gram = design.T @ design + lam * rows.size * np.eye(self.K)
        return np.linalg.solve(gram, design.T @ y[rows])

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, _x = _realised(self, panel)
        candidates = [c for c in self.top_columns(panel, 10)
                      if c != state and panel.meta.get(c) is not None
                      and panel.meta[c].source in ("bars", "axis")][:6]
        if not candidates:
            self.note("driver", "no bar or axis column to deconvolve")
            return []
        y = np.nan_to_num(panel.epsilon)
        train, _ = panel.split()
        usable = train[train >= self.K]
        cut = int(usable.size * 0.7)
        fit_rows, val_rows = usable[:cut], usable[cut:]
        if val_rows.size < 60:
            self.note("validation", "fewer than 60 validation rows inside the training slice")
            return []
        # WHICH driver is chosen by the SAME out-of-sample error that chooses the ridge, never
        # by a contemporaneous correlation: a kernel spread over 24 lags can carry the residual
        # while the driver's same-bar correlation with it is nothing, and the driver is taken as
        # a stationary fluctuation so a price level cannot win the scan spuriously.
        baseline = float(np.mean(y[val_rows] ** 2))
        best: tuple[float, float, np.ndarray, str] | None = None
        per_driver: dict[str, dict[str, Any]] = {}
        for name in candidates:
            d = _fluct(panel.columns[name])
            design = np.column_stack([d[val_rows - k] for k in range(1, self.K + 1)])
            for lam in self.LAMBDAS:
                h_try = self.kernel(d, y, fit_rows, lam)
                err_try = float(np.mean((y[val_rows] - design @ h_try) ** 2))
                self.evaluated += 1
                row = per_driver.setdefault(name, {"validation_mse": err_try, "lambda": lam})
                if err_try < float(row["validation_mse"]):
                    row["validation_mse"], row["lambda"] = err_try, lam
                if best is None or err_try < best[0]:
                    best = (err_try, lam, h_try, name)
        assert best is not None
        err, lam, _h0, driver_name = best
        driver = _fluct(panel.columns[driver_name])
        h = self.kernel(driver, y, usable, lam)
        skill = 1.0 - err / max(1e-18, baseline)
        weight = np.abs(h) / max(1e-12, float(np.abs(h).sum()))
        effective = float((np.arange(1, self.K + 1) * weight).sum())
        decay = _loglog_fit(np.arange(1, self.K + 1), np.abs(h))
        total = float(h.sum())
        per_era = _era_values(panel, lambda rows: _corr(
            self.kernel(driver, y, rows[rows >= self.K], lam), h)
            if rows[rows >= self.K].size > 2 * self.K else None)
        window = _nearest_window(effective)
        diagnostics = {"driver": driver_name, "lambda": lam, "validation_mse": round(err, 8),
                       "driver_transform": _fluct_kind(panel.columns[driver_name]),
                       "validation_skill": round(skill, 6),
                       "drivers_scanned": {
                           k: {"validation_mse": round(float(v["validation_mse"]), 8),
                               "lambda": v["lambda"]} for k, v in sorted(per_driver.items())},
                       "kernel": [round(float(v), 6) for v in h], "kernel_sum": round(total, 6),
                       "effective_length": round(effective, 3), "decay_exponent":
                       round(decay[0], 4) if decay else None, "per_era_kernel_corr": per_era,
                       "method": "Tikhonov-regularised 24-lag deconvolution over the stationary "
                                 "fluctuation of each candidate driver; BOTH the driver and the "
                                 "ridge chosen by the same validation slice inside the training "
                                 "window, never by a contemporaneous correlation"}
        tree = ["rmean", driver_name, window]
        notes = [f"approximation: the fitted kernel over {driver_name} is replaced by a "
                 f"{window}-bar moving mean (effective length {effective:.1f}) because the trade "
                 f"grammar has no free-weight convolution"]
        corr = _train_corr(panel, np.nan_to_num(G.evaluate(tree, panel.columns, panel.n)))
        out = [self.emit(panel, "representation", tree,
                         f"KERNEL-WEIGHTED {driver_name}: effective length {effective:.1f} bars, "
                         f"sum {total:+.5f}", diagnostics=diagnostics, notes=notes),
               self.emit(panel, "relationship", tree,
                         f"the deconvolved driver reads the residual with training IC {corr:+.4f} "
                         f"(kernel sum {total:+.5f})", side_mode=_side(corr if abs(corr) > 1e-9
                                                                        else total),
                         diagnostics=diagnostics, notes=notes),
               self.emit(panel, "law", ["lag", driver_name, window],
                         f"KERNEL STABILITY: per-era correlation with the full kernel {per_era}; "
                         f"decay exponent {diagnostics['decay_exponent']}",
                         diagnostics=diagnostics)]
        _ = (deadline, rng)
        return out


# ==================================================================== 19. random matrix
class RandomMatrix(Scientist):
    """Marchenko-Pastur cleaning of the panel's correlation matrix and its leading eigenmode.

    With k variables over n rows the bulk of a pure-noise correlation spectrum lies inside
    (1 +/- sqrt(k/n))^2; eigenvalues above the upper edge are signal. The bulk is replaced by
    its mean (cleaning), the leading eigenvector is the market mode, and the target's projection
    on it is minted as a column. The nearest-neighbour spacing ratio says whether the spectrum
    is Wigner-Dyson (level repulsion, correlated system) or Poisson (independent).
    """

    tradition = "random_matrix"
    searches_for = ("representation", "law", "relationship")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        train, _ = panel.split()
        matrix, names, source = _node_matrix(panel)
        extra = [c for c in panel.names if panel.meta.get(c) is not None
                 and panel.meta[c].source == "axis"][:6]
        if extra:
            matrix = np.column_stack([matrix] + [_z(np.nan_to_num(_finite(panel.columns[c])))
                                                 for c in extra])
            names = names + extra
        k = len(names)
        if k < 3:
            self.note("variables", "fewer than three variables to form a spectrum")
            return []
        n = int(train.size)
        corr = np.nan_to_num(np.corrcoef(matrix[train].T))
        vals, vecs = np.linalg.eigh(corr)
        q = k / max(1, n)
        upper = (1.0 + math.sqrt(q)) ** 2
        lower = (1.0 - math.sqrt(q)) ** 2
        signal = int((vals > upper).sum())
        bulk = vals <= upper
        cleaned = vals.copy()
        if bulk.any():
            cleaned[bulk] = float(vals[bulk].mean())
        spacings = np.diff(np.sort(vals))
        with _quiet():
            ratios = np.minimum(spacings[1:], spacings[:-1]) / np.maximum(
                np.maximum(spacings[1:], spacings[:-1]), 1e-12)
        r_tilde = float(np.mean(ratios)) if ratios.size else None
        leading = vecs[:, -1]
        leading = leading * np.sign(leading.sum() or 1.0)
        mode = matrix @ leading
        name = _mint(self, panel, "eigenmode_1", mode, "mathlab:random_matrix", "z units")
        per_era = _era_values(panel, lambda rows: float((np.linalg.eigvalsh(
            np.nan_to_num(np.corrcoef(matrix[rows].T))) > (1.0 + math.sqrt(k / rows.size)) ** 2)
            .sum()))
        diagnostics = {"variables": k, "rows": n, "source": source, "mp_edges":
                       {"lower": round(lower, 4), "upper": round(upper, 4)},
                       "eigenvalues": [round(float(v), 4) for v in vals[::-1][:8]],
                       "signal_eigenvalues": signal, "cleaned_bulk_mean":
                       round(float(vals[bulk].mean()), 4) if bulk.any() else None,
                       "spacing_ratio": round(r_tilde, 4) if r_tilde is not None else None,
                       "spacing_reference": {"poisson": 0.386, "goe": 0.536},
                       "leading_vector": {nm: round(float(v), 4) for nm, v in
                                          zip(names, leading, strict=False)},
                       "per_era_signal_count": per_era,
                       "method": "Marchenko-Pastur edges at k/n; bulk replaced by its mean; "
                                 "leading eigenvector projection minted; nearest-neighbour "
                                 "spacing ratio"}
        corr_mode = _train_corr(panel, mode)
        out = [self.emit(panel, "representation", ["z", name, 48],
                         f"EIGENMODE 1: the leading eigenvector of the {k}-variable correlation "
                         f"matrix (eigenvalue {vals[-1]:.3f} against an MP edge of {upper:.3f})",
                         diagnostics=diagnostics),
               self.emit(panel, "relationship", ["z", name, 48],
                         f"the leading eigenmode reads the residual with training IC "
                         f"{corr_mode:+.4f}", side_mode=_side(corr_mode), diagnostics=diagnostics),
               self.emit(panel, "law", ["rstd", name, 48],
                         f"SPECTRUM: {signal} eigenvalue(s) above the Marchenko-Pastur edge; "
                         f"spacing ratio {diagnostics['spacing_ratio']} (Poisson 0.386, GOE "
                         f"0.536); per era {per_era}", diagnostics=diagnostics)]
        _ = (deadline, rng)
        return out


PHYSICS_EXT_REGISTRY: dict[str, type[Scientist]] = {
    "network_physics": NetworkPhysics,
    "information_physics": InformationPhysics,
    "dimensional_analysis": DimensionalAnalysis,
    "symmetry_invariance": SymmetryInvariance,
    "conservation_laws": ConservationLaws,
    "stochastic_physics": StochasticPhysics,
    "monte_carlo_abm": MonteCarloABM,
    "inverse_problems": InverseProblems,
    "random_matrix": RandomMatrix,
}
_ = UNMEASURED
