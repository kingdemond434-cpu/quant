"""FIVE GENERATED FAMILIES for the methods GENERATOR_COVERAGE listed MISSING (2026-11-24/25):

    analog_knn      analog / nearest-neighbour pattern matching: the k past states most like now,
                    and what followed them.
    ranked_linear   time-series learning-to-rank: a linear score fitted by a pairwise (RankNet)
                    loss to ORDER bars by their forward return, refitted on a rolling window.
    gbm_classifier  gradient-boosted shallow trees (numpy, no sklearn) classifying the sign of the
                    next-h-bar return, refitted walk-forward on a trailing window.
    neural_policy   a NEAT-evolved network (topology + weights) mapping causal features to a side.
    ge_strategy     a strategy decoded by grammatical evolution from a BNF: AND / OR / NOT over the
                    rule-builder blocks, filters, and an exit including a partial take and a trail.

THE CELL IS THE SPEC, NOT A FITTED BLOB, WHERE A FIT EXISTS. `analog_knn`, `ranked_linear` and
`gbm_classifier` carry hyperparameters only; every bar's decision is computed from a library /
fit that uses labels whose window CLOSED before that bar (`t' + h + 1 <= t`; the boosted model
is stricter, `t' + h + 1 <= t - 1`, so its fit never reads the decision bar at all). So the
gauntlet's walk-forward and lockbox read genuinely out-of-sample decisions, refit by the cell
itself. `neural_policy` and
`ge_strategy` are fixed rules (like a formula): the generator chose them on the visible window
only, and the gauntlet judges them over the full history like any other fixed-parameter cell.

All five read closed bars only and fill on the next open (wait_bars=1); `test_hypgen_models`
pins no look-ahead by truncation. Nothing here has authority: proposed by
`research/hypgen_engine.py`, charged, judged.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from mt5desk import hypgen_features as hf
from mt5desk.exit_operators import apply_exit_operators
from mt5desk.families import _h1, register_family
from mt5desk.family_rule_builder import BLOCKS, FILTERS

MIN_BARS = 600


def _edge(side: np.ndarray) -> np.ndarray:
    """Fire only where the side becomes non-zero or flips: a persistent state is one trade."""
    prev = np.concatenate([[0], side[:-1]])
    return np.where((side != 0) & (side != prev), side, 0).astype(np.int8)


def _feat(d: pd.DataFrame, features: Any) -> tuple[list[str], np.ndarray] | None:
    names = [str(f) for f in (features or []) if str(f) in hf.FEATURES]
    if not names:
        return None
    return names, hf.matrix(d, names)


# --------------------------------------------------------------------------- analog / kNN
def knn_sides(d: pd.DataFrame, features, k: int, h: int, library: int, thr: float,
              stride: int) -> np.ndarray:
    got = _feat(d, features)
    n = len(d)
    side = np.zeros(n, dtype=np.int8)
    if got is None:
        return side
    _, x = got
    y = hf.forward_log_return(d, int(h))
    ok = np.isfinite(x).all(axis=1)
    k, h = max(3, int(k)), max(1, int(h))
    library, stride = max(50, int(library)), max(1, int(stride))
    for t in range(library + h + 1, n, stride):
        if not ok[t]:
            continue
        hi = t - h - 1                       # last bar whose label window has closed by t
        lo = max(0, hi - library)
        lib_x, lib_y = x[lo:hi + 1], y[lo:hi + 1]
        m = ok[lo:hi + 1] & np.isfinite(lib_y)
        if m.sum() < k * 3:
            continue
        dist = np.sum((lib_x[m] - x[t]) ** 2, axis=1)
        nn = np.argpartition(dist, k - 1)[:k]
        ys = lib_y[m][nn]
        sd = ys.std(ddof=1)
        if sd <= 0:
            continue
        tstat = ys.mean() / sd * np.sqrt(k)
        if abs(tstat) >= thr:
            side[t] = 1 if tstat > 0 else -1
    return side


@register_family(param_grid={"k": [10, 20, 40], "h": [4, 12, 24], "thr": [1.0, 1.5, 2.0]},
                 tags=["analog", "knn", "generated", "model"])
def family_analog_knn(df: pd.DataFrame, *, features: list | None = None, k: int = 20,
                      h: int = 12, library: int = 3000, thr: float = 1.5, stride: int = 1,
                      stop_atr: float = 2.0, rr: float = 1.5, atr_n: int = 14) -> list:
    d = _h1(df)
    if len(d) < MIN_BARS:
        return []
    side = _edge(knn_sides(d, features or ["ret_1", "ret_4", "ret_24", "z_50"], k, h, library,
                           thr, stride))
    return hf.emit(d, side, stop_atr=stop_atr, rr=rr, hold=int(h), atr_n=atr_n,
                   tag="analog_knn")


# --------------------------------------------------------------------------- learning to rank
def _rank_fit(x: np.ndarray, y: np.ndarray, seed: int, pairs: int = 3000, iters: int = 60,
              lr: float = 0.1, l2: float = 1e-2) -> np.ndarray:
    """Linear RankNet: minimise log(1 + exp(-s_ij w.(x_i - x_j))) over sampled pairs,
    s_ij = sign(y_i - y_j)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    i = rng.integers(0, n, pairs)
    j = rng.integers(0, n, pairs)
    s = np.sign(y[i] - y[j])
    keep = s != 0
    dx, s = x[i[keep]] - x[j[keep]], s[keep]
    w = np.zeros(x.shape[1])
    if len(s) < 50:
        return w
    for _ in range(iters):
        z = s * (dx @ w)
        g = -(dx * (s / (1.0 + np.exp(np.clip(z, -30, 30))))[:, None]).mean(axis=0) + l2 * w
        w -= lr * g
    return w


def rank_sides(d: pd.DataFrame, features, h: int, window: int, refit: int, q: float
               ) -> np.ndarray:
    got = _feat(d, features)
    n = len(d)
    side = np.zeros(n, dtype=np.int8)
    if got is None:
        return side
    _, x = got
    y = hf.forward_log_return(d, int(h))
    ok = np.isfinite(x).all(axis=1)
    h, window, refit = max(1, int(h)), max(200, int(window)), max(10, int(refit))
    q = min(max(float(q), 0.55), 0.98)
    w = None
    hi_cut = lo_cut = None
    for t in range(window + h + 1, n):
        if w is None or (t - window - h - 1) % refit == 0:
            hi = t - h - 1                   # labels closed by t only
            lo = hi - window
            m = ok[lo:hi + 1] & np.isfinite(y[lo:hi + 1])
            if m.sum() < 100:
                w = None
                continue
            xs, ys = x[lo:hi + 1][m], y[lo:hi + 1][m]
            w = _rank_fit(xs, ys, seed=t)
            sc = xs @ w
            hi_cut, lo_cut = np.quantile(sc, q), np.quantile(sc, 1 - q)
        if w is None or not ok[t]:
            continue
        s = float(x[t] @ w)
        if s >= hi_cut:
            side[t] = 1
        elif s <= lo_cut:
            side[t] = -1
    return side


@register_family(param_grid={"h": [4, 12, 24], "q": [0.8, 0.9, 0.95]},
                 tags=["learning_to_rank", "generated", "model"])
def family_ranked_linear(df: pd.DataFrame, *, features: list | None = None, h: int = 12,
                         window: int = 2000, refit: int = 250, q: float = 0.9,
                         stop_atr: float = 2.0, rr: float = 1.5, atr_n: int = 14) -> list:
    d = _h1(df)
    if len(d) < MIN_BARS:
        return []
    side = _edge(rank_sides(d, features or ["ret_1", "ret_8", "z_20", "rsi_14"], h, window,
                            refit, q))
    return hf.emit(d, side, stop_atr=stop_atr, rr=rr, hold=int(h), atr_n=atr_n,
                   tag="ranked_linear")


# --------------------------------------------------------------------------- gradient boosting
def _gbm_bins(x: np.ndarray, bins: int) -> list[np.ndarray]:
    """Per-feature split edges: the TRAINING window's interior quantiles (never the bar's own)."""
    qs = np.linspace(0.0, 1.0, int(bins) + 1)[1:-1]
    return [np.unique(np.quantile(x[:, j], qs)) for j in range(x.shape[1])]


def _gbm_bin(x: np.ndarray, edges: list[np.ndarray]) -> np.ndarray:
    return np.column_stack([np.searchsorted(e, x[:, j], side="right")
                            for j, e in enumerate(edges)]).astype(np.int32)


def _gbm_tree(xb: np.ndarray, g: np.ndarray, hs: np.ndarray, rows: np.ndarray, depth: int,
              nb: int, min_leaf: int, l2: float) -> Any:
    """One regression tree on the logistic gradient by histogram split search (XGBoost's gain,
    Newton leaf). A node is a float (leaf value) or (feature, bin_threshold, left, right)."""
    gs, hsum = float(g[rows].sum()), float(hs[rows].sum())
    leaf = gs / (hsum + l2)
    if depth <= 0 or rows.size < 2 * min_leaf:
        return leaf
    parent = gs * gs / (hsum + l2)
    best = (0.0, -1, -1)
    for j in range(xb.shape[1]):
        col = xb[rows, j]
        gl = np.cumsum(np.bincount(col, weights=g[rows], minlength=nb))[:-1]
        hl = np.cumsum(np.bincount(col, weights=hs[rows], minlength=nb))[:-1]
        cl = np.cumsum(np.bincount(col, minlength=nb))[:-1]
        okc = (cl >= min_leaf) & (rows.size - cl >= min_leaf)
        if not okc.any():
            continue
        gain = gl * gl / (hl + l2) + (gs - gl) ** 2 / (hsum - hl + l2) - parent
        gain = np.where(okc, gain, -np.inf)
        k = int(np.argmax(gain))
        if gain[k] > best[0]:
            best = (float(gain[k]), j, k)
    if best[1] < 0:
        return leaf
    _, j, k = best
    left = rows[xb[rows, j] <= k]
    right = rows[xb[rows, j] > k]
    return (j, k, _gbm_tree(xb, g, hs, left, depth - 1, nb, min_leaf, l2),
            _gbm_tree(xb, g, hs, right, depth - 1, nb, min_leaf, l2))


def _gbm_tree_predict(node: Any, xb: np.ndarray) -> np.ndarray:
    if not isinstance(node, tuple):
        return np.full(len(xb), float(node))
    j, k, left, right = node
    go_left = xb[:, j] <= k
    out = np.empty(len(xb))
    if go_left.any():
        out[go_left] = _gbm_tree_predict(left, xb[go_left])
    if (~go_left).any():
        out[~go_left] = _gbm_tree_predict(right, xb[~go_left])
    return out


def gbm_fit(x: np.ndarray, yb: np.ndarray, n_trees: int = 50, depth: int = 2, lr: float = 0.1,
            bins: int = 16, min_leaf: int = 30, l2: float = 1.0) -> dict:
    """Gradient-boosted shallow trees (depth 1 = stumps) for a binary label, logistic loss,
    numpy only. Returns {"edges", "base", "trees", "lr"}: everything `gbm_predict` needs."""
    edges = _gbm_bins(x, bins)
    xb = _gbm_bin(x, edges)
    nb = int(bins) + 1
    p0 = float(np.clip(yb.mean(), 1e-3, 1 - 1e-3))
    base = float(np.log(p0 / (1 - p0)))
    f = np.full(len(yb), base)
    rows = np.arange(len(yb))
    trees = []
    for _ in range(max(1, int(n_trees))):
        p = 1.0 / (1.0 + np.exp(-np.clip(f, -30, 30)))
        g, hs = yb - p, p * (1 - p)
        tree = _gbm_tree(xb, g, hs, rows, max(1, int(depth)), nb, int(min_leaf), float(l2))
        trees.append(tree)
        f = f + lr * _gbm_tree_predict(tree, xb)
    return {"edges": edges, "base": base, "trees": trees, "lr": float(lr)}


def gbm_predict(model: dict, x: np.ndarray) -> np.ndarray:
    """P(label = 1) for every row of x (rows must be finite)."""
    xb = _gbm_bin(x, model["edges"])
    f = np.full(len(x), model["base"])
    for tree in model["trees"]:
        f = f + model["lr"] * _gbm_tree_predict(tree, xb)
    return 1.0 / (1.0 + np.exp(-np.clip(f, -30, 30)))


def gbm_sides(d: pd.DataFrame, features, h: int, window: int, refit: int, thr: float,
              n_trees: int = 50, depth: int = 2, lr: float = 0.1) -> np.ndarray:
    """Walk-forward boosted classifier of the sign of the next-h-bar return.

    Refit every `refit` bars on a trailing `window`. The model that decides bars [t0, t0+refit)
    is fitted at t0 on rows whose LABEL WINDOW ENDS AT OR BEFORE BAR t0-1 (label at t' reads opens
    t'+1 .. t'+h+1, so t' <= t0-h-2): no fit ever reads the decision bar or anything after it.
    The refit grid is anchored at a fixed bar, so it does not move when history grows."""
    got = _feat(d, features)
    n = len(d)
    side = np.zeros(n, dtype=np.int8)
    if got is None:
        return side
    _, x = got
    h, window, refit = max(1, int(h)), max(200, int(window)), max(10, int(refit))
    thr = min(max(float(thr), 0.5), 0.95)
    y = hf.forward_log_return(d, h)
    ok = np.isfinite(x).all(axis=1)
    start = window + h + 2
    for t0 in range(start, n, refit):
        hi = t0 - h - 2                      # last row whose label closed by bar t0-1
        lo = max(0, hi - window + 1)
        m = ok[lo:hi + 1] & np.isfinite(y[lo:hi + 1]) & (y[lo:hi + 1] != 0)
        if m.sum() < 100:
            continue
        xs = x[lo:hi + 1][m]
        ys = (y[lo:hi + 1][m] > 0).astype(float)
        if ys.min() == ys.max():
            continue
        model = gbm_fit(xs, ys, n_trees=n_trees, depth=depth, lr=lr)
        t1 = min(n, t0 + refit)
        blk = np.arange(t0, t1)[ok[t0:t1]]
        if not blk.size:
            continue
        p = gbm_predict(model, x[blk])
        side[blk] = np.where(p > thr, 1, np.where(p < 1 - thr, -1, 0))
    return side


@register_family(param_grid={"h": [4, 12, 24], "thr": [0.55, 0.6, 0.65]},
                 tags=["gradient_boosting", "tree_ensemble", "generated", "model"])
def family_gbm_classifier(df: pd.DataFrame, *, features: list | None = None, h: int = 12,
                          window: int = 2000, refit: int = 250, thr: float = 0.6,
                          n_trees: int = 50, depth: int = 2, lr: float = 0.1,
                          stop_atr: float = 2.0, rr: float = 1.5, atr_n: int = 14) -> list:
    d = _h1(df)
    if len(d) < MIN_BARS:
        return []
    side = _edge(gbm_sides(d, features or ["ret_1", "ret_8", "z_20", "rsi_14", "atr_rank"],
                           h, window, refit, thr, n_trees, depth, lr))
    return hf.emit(d, side, stop_atr=stop_atr, rr=rr, hold=int(h), atr_n=atr_n,
                   tag="gbm_classifier")


# --------------------------------------------------------------------------- NEAT network
ACTS = {"tanh": np.tanh, "relu": lambda v: np.maximum(v, 0.0),
        "sig": lambda v: 1 / (1 + np.exp(-v)), "id": lambda v: v}


def net_forward(net: dict, x: np.ndarray) -> np.ndarray | None:
    """Evaluate a feed-forward NEAT genome over every row of x. None if the graph has a cycle.

    net = {"inputs": [feature names], "hidden": {id: act}, "conns": [[src, dst, w, enabled]]};
    inputs are "i0".."iN-1", the output node is "out" (tanh)."""
    n_in = x.shape[1]
    vals: dict[str, np.ndarray] = {f"i{k}": np.nan_to_num(x[:, k]) for k in range(n_in)}
    hidden = {str(k): str(v) for k, v in (net.get("hidden") or {}).items()}
    conns = [c for c in (net.get("conns") or []) if len(c) == 4 and c[3]]
    incoming: dict[str, list] = {}
    for src, dst, w, _ in conns:
        incoming.setdefault(str(dst), []).append((str(src), float(w)))
    order, temp, perm = [], set(), set()

    def visit(node: str) -> bool:
        if node in perm or node in vals:
            return True
        if node in temp:
            return False
        temp.add(node)
        for src, _ in incoming.get(node, []):
            if not visit(src):
                return False
        temp.discard(node)
        perm.add(node)
        order.append(node)
        return True

    if not visit("out"):
        return None
    zero = np.zeros(len(x))
    for node in order:
        s = zero.copy()
        for src, w in incoming.get(node, []):
            s = s + w * vals.get(src, zero)
        act = "tanh" if node == "out" else hidden.get(node, "tanh")
        with np.errstate(all="ignore"):
            vals[node] = np.nan_to_num(ACTS.get(act, np.tanh)(s))
    return vals["out"]


@register_family(param_grid={"thr": [0.3, 0.5, 0.7], "hold": [6, 12, 24]},
                 tags=["neuroevolution", "neat", "generated", "model"])
def family_neural_policy(df: pd.DataFrame, *, net: dict | None = None, thr: float = 0.5,
                         stop_atr: float = 2.0, rr: float = 1.5, hold: int = 12,
                         atr_n: int = 14) -> list:
    d = _h1(df)
    if len(d) < MIN_BARS or not net:
        return []
    got = _feat(d, net.get("inputs"))
    if got is None:
        return []
    _, x = got
    out = net_forward(net, x)
    if out is None:
        return []
    ok = np.isfinite(x).all(axis=1)
    raw = np.where(ok & (out > thr), 1, np.where(ok & (out < -thr), -1, 0)).astype(np.int8)
    return hf.emit(d, _edge(raw), stop_atr=stop_atr, rr=rr, hold=int(hold), atr_n=atr_n,
                   tag="neural_policy")


# --------------------------------------------------------------------------- GE strategy
def _apply_filters(d: pd.DataFrame, side: np.ndarray, filters) -> np.ndarray | None:
    """The rule builder's gates (session, vol regime, trend, weekday) as permissions on `side`."""
    for flt in filters or []:
        fn = FILTERS.get(str(flt.get("f")), (None,))[0]
        if fn is None:
            return None
        mask, directional = fn(d, **{k: v for k, v in flt.items() if k != "f"})
        if mask is not None:
            side = np.where(mask, side, 0).astype(np.int8)
        if directional is not None:
            tside, mode = directional
            want = tside if mode == "with" else -tside
            side = np.where(side == want, side, 0).astype(np.int8)
    return side


def rule_sides(d: pd.DataFrame, rule: dict, depth: int = 0) -> np.ndarray:
    """Directional value (-1/0/+1) per bar of a decoded BNF rule tree."""
    n = len(d)
    if not isinstance(rule, dict) or depth > 6:
        return np.zeros(n, dtype=np.int8)
    op = rule.get("op")
    if op == "block":
        fn = BLOCKS.get(str(rule.get("b")), (None,))[0]
        if fn is None:
            return np.zeros(n, dtype=np.int8)
        return np.asarray(fn(d, **dict(rule.get("p") or {})), dtype=np.int8)
    if op == "not":
        return (-rule_sides(d, rule.get("a"), depth + 1)).astype(np.int8)
    a = rule_sides(d, rule.get("a"), depth + 1)
    b = rule_sides(d, rule.get("b"), depth + 1)
    if op == "and":
        return np.where(a == b, a, 0).astype(np.int8)
    if op == "or":                           # either fires; a conflict is no trade
        return np.where(a == 0, b, np.where((b == 0) | (b == a), a, 0)).astype(np.int8)
    return np.zeros(n, dtype=np.int8)


@register_family(param_grid={"hold": [6, 12, 24, 48]},
                 tags=["grammatical_evolution", "generated", "composable"])
def family_ge_strategy(df: pd.DataFrame, *, rule: dict | None = None,
                       filters: list | None = None, stop_atr: float = 2.0, rr: float = 2.0,
                       hold: int = 24, bank_frac: float = 0.0, runner_trail_k: float = 0.0,
                       expansion_mult: float = 0.0, atr_n: int = 14) -> list:
    d = _h1(df)
    if len(d) < MIN_BARS or not rule:
        return []
    side = _apply_filters(d, _edge(rule_sides(d, rule)), filters)
    if side is None:
        return []
    sigs = hf.emit(d, side, stop_atr=stop_atr, rr=rr, hold=int(hold), atr_n=atr_n,
                   tag="ge_strategy", bank_frac=bank_frac, runner_trail_k=runner_trail_k)
    return apply_exit_operators(d, sigs, expansion_mult=float(expansion_mult),
                                exit_on_anchor_flip=False, anchor=None, atr_n=int(atr_n))
