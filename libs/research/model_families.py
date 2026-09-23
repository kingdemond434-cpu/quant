"""MODEL-FAMILY SEARCH as its own civilization (Tier-1 item 6).

Ten families -- linear, sparse, tree, boosting, neural, state-space, Bayesian, sequence, graph,
mixture-of-experts -- each with the same discipline a factor gets: a lineage (which family it
descends from), a novelty key (nothing is re-tested under a new name), a falsifier (the declared
tax it must clear out of sample) and a verdict that can be UNMEASURED.

WHY THIS FILE IMPORTS NOTHING HEAVY AT MODULE SCOPE. `libs.models.zoo` reaches straight into
sklearn: on a box without it, every model family in the desk is a crash, and a crash is not a
verdict. Here EVERY family has a pure-Python fallback -- no numpy, no pandas, no sklearn -- so
the civilization always runs, and the heavy backend is a guarded accelerator whose absence is
recorded as `heavy_verdict: UNMEASURED` on that family's row rather than raised. That is the
law's "absence is never a clean verdict" applied to the learner instead of the data.

THE TAX IS THE FALSIFIER. A family's declared tax (nats per prediction) prices its freedom:
capacity, instability across folds, and -- for `sequence` and `state_space` -- the staleness of
the labels it needs before it can predict at all. `net_gain = OOS log score - baseline - tax`,
and only `net_gain > 0` is EARNS_ITS_PLACE. Two families that tie on gain are separated by the
tax, which is why a boosted stump has to beat a ridge by a measurable margin to be preferred.

The scoring convention is `libs.models.zoo`'s, deliberately: expanding-window folds, mean OOS
log score against the train-fold base rate, so a row from here and a row from the zoo are
comparable in COEVOLUTION.json without a translation table.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

UNMEASURED = "UNMEASURED"
POSITIVE = "EARNS_ITS_PLACE"
NEGATIVE = "TAXED_OUT"
#: Rows a family needs before its mean is a number rather than an anecdote.
MIN_ROWS = 120
EPS = 1e-6


@dataclass(frozen=True)
class Family:
    """One model family as the civilization sees it."""

    name: str
    #: Declared tax in nats per prediction -- the bar this family's gain must clear.
    tax: float
    #: The family it descends from; "" for a root. Lineage, exactly as a factor carries one.
    parent: str = ""
    #: Heavy backends tried in order before the pure-Python fallback.
    backends: tuple[str, ...] = ()
    #: What the family assumes -- the sentence a falsification has to contradict.
    assumption: str = ""
    #: Axes this family can be mutated along when a residual asks for a challenger.
    mutations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def novelty_key(self) -> str:
        return f"{self.name}|{self.parent}"


FAMILIES: dict[str, Family] = {
    "linear": Family("linear", 0.0, "", ("sklearn.linear_model",),
                     "the conditional mean is linear in the standardised features",
                     ("alpha", "features")),
    "sparse": Family("sparse", 0.0005, "linear", ("sklearn.linear_model",),
                     "only a few features carry signal; the rest are exactly zero",
                     ("l1", "features")),
    "tree": Family("tree", 0.0010, "", ("sklearn.tree",),
                   "the response is piecewise constant on axis-aligned regions",
                   ("depth", "min_leaf")),
    "boosting": Family("boosting", 0.0015, "tree", ("sklearn.ensemble",),
                       "many shallow, shrunken corrections beat one deep fit",
                       ("n_rounds", "shrinkage", "depth")),
    "neural": Family("neural", 0.0025, "", ("sklearn.neural_network", "torch"),
                     "a smooth low-dimensional nonlinearity fits the response",
                     ("hidden", "l2", "epochs")),
    "state_space": Family("state_space", 0.0015, "linear", ("statsmodels.tsa.statespace",),
                          "the edge is a slowly drifting latent level, observed with noise",
                          ("q_over_r", "window")),
    "bayesian": Family("bayesian", 0.0005, "linear", ("sklearn.naive_bayes",),
                       "class-conditional features are Gaussian and independent given the sign",
                       ("prior_strength",)),
    "sequence": Family("sequence", 0.0015, "linear", ("torch",),
                       "the recent path of the target itself predicts its next sign",
                       ("lags", "alpha")),
    "graph": Family("graph", 0.0015, "linear", ("networkx",),
                    "features are nodes; a consensus over correlated neighbours beats each one",
                    ("k", "threshold")),
    "mixture_of_experts": Family("mixture_of_experts", 0.0020, "linear",
                                 ("libs.models.router",),
                                 "the population is a mixture; one expert per gate bucket",
                                 ("n_experts", "gate_feature")),
}
#: The order a search walks the civilization in: cheapest tax first, so an expensive family is
#: only reached once the cheap ones have failed to explain the same rows.
ORDER: tuple[str, ...] = tuple(sorted(FAMILIES, key=lambda k: (FAMILIES[k].tax, k)))


# --------------------------------------------------------------- guarded heavy backends
def _import(mod: str) -> Any:
    try:
        __import__(mod)
    except Exception:
        return None
    import sys
    return sys.modules.get(mod)


def availability() -> dict[str, dict[str, Any]]:
    """Per family: which declared backends are importable here, and the verdict when none is.

    A family whose heavy backend is absent still RUNS on its pure-Python fallback; what is
    UNMEASURED is the heavy backend's own contribution, and that is what this records. An
    absent library is never a crash and never a zero.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, fam in FAMILIES.items():
        present = [m for m in fam.backends if _import(m) is not None]
        out[name] = {
            "backends_declared": list(fam.backends),
            "backends_present": present,
            "backend": "heavy" if present else "fallback",
            "heavy_verdict": "MEASURED" if present else UNMEASURED,
            "why": "" if present else (
                f"none of {list(fam.backends) or ['(no heavy backend declared)']} importable "
                "here; the pure-Python fallback carries this family and the heavy backend's "
                "contribution is UNMEASURED, not zero"),
            "tax": fam.tax, "parent": fam.parent, "assumption": fam.assumption,
        }
    return out


# --------------------------------------------------------------- pure-Python linear algebra
def _solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting. None when singular."""
    n = len(b)
    m = [[*row, b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col] / pv
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _standardise(xtr: list[list[float]], xte: list[list[float]]
                 ) -> tuple[list[list[float]], list[list[float]]]:
    if not xtr:
        return xtr, xte
    p = len(xtr[0])
    mu = [sum(r[j] for r in xtr) / len(xtr) for j in range(p)]
    sd = []
    for j in range(p):
        v = sum((r[j] - mu[j]) ** 2 for r in xtr) / max(1, len(xtr))
        sd.append(math.sqrt(v) if v > 0 else 1.0)
    def _z(rows: list[list[float]]) -> list[list[float]]:
        return [[(r[j] - mu[j]) / sd[j] for j in range(p)] for r in rows]
    return _z(xtr), _z(xte)


def _squash(raw: float, k: float = 4.0) -> float:
    return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, k * raw))))


def _ridge(x: list[list[float]], y: list[float], alpha: float) -> list[float] | None:
    p = len(x[0]) if x else 0
    if p == 0:
        return None
    xtx = [[sum(r[i] * r[j] for r in x) + (alpha if i == j else 0.0) for j in range(p)]
           for i in range(p)]
    xty = [sum(r[i] * t for r, t in zip(x, y, strict=True)) for i in range(p)]
    return _solve(xtx, xty)


def _pred_linear(w: list[float], x: list[list[float]], k: float = 4.0) -> list[float]:
    return [_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True)), k) for r in x]


# --------------------------------------------------------------- the ten fallbacks
def _f_linear(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], float(kw.get("alpha", 10.0)))
    if w is None:
        return None
    return _pred_linear(w, xte)


def _f_sparse(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    """ISTA: ridge start, then soft-threshold toward exact zeros."""
    lam = float(kw.get("l1", 0.15))
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if w is None:
        return None
    w = [0.0 if abs(c) < lam else math.copysign(abs(c) - lam, c) for c in w]
    if not any(w):
        return [0.5] * len(xte)
    return _pred_linear(w, xte)


def _best_split(x: list[list[float]], y: list[float], cols: Sequence[int]
                ) -> tuple[int, float, float, float] | None:
    n = len(y)
    if n < 8:
        return None
    best = None
    for j in cols:
        vals = sorted({r[j] for r in x})
        if len(vals) < 3:
            continue
        for q in (0.25, 0.5, 0.75):
            thr = vals[int(q * (len(vals) - 1))]
            lo = [y[i] for i in range(n) if x[i][j] <= thr]
            hi = [y[i] for i in range(n) if x[i][j] > thr]
            if len(lo) < 4 or len(hi) < 4:
                continue
            pl, ph = sum(lo) / len(lo), sum(hi) / len(hi)
            # weighted Gini reduction
            imp = (len(lo) * pl * (1 - pl) + len(hi) * ph * (1 - ph)) / n
            if best is None or imp < best[3]:
                best = (j, float(thr), pl, imp)
    if best is None:
        return None
    j, thr, pl, imp = best
    hi = [y[i] for i in range(n) if x[i][j] > thr]
    return (j, thr, pl, sum(hi) / len(hi))


def _f_tree(xtr, ytr, xte, **kw):                                     # type: ignore[no-untyped-def]
    cols = range(len(xtr[0]))
    root = _best_split(xtr, ytr, cols)
    if root is None:
        return None
    j, thr, p_lo, p_hi = root
    depth = int(kw.get("depth", 2))
    sub: dict[bool, tuple[int, float, float, float] | None] = {True: None, False: None}
    if depth > 1:
        for side in (True, False):
            idx = [i for i in range(len(ytr)) if (xtr[i][j] > thr) is side]
            if len(idx) >= 16:
                sub[side] = _best_split([xtr[i] for i in idx], [ytr[i] for i in idx], cols)
    out = []
    for r in xte:
        side = r[j] > thr
        node = sub[side]
        if node is not None:
            jj, tt, a, b = node
            out.append(b if r[jj] > tt else a)
        else:
            out.append(p_hi if side else p_lo)
    return [min(1 - EPS, max(EPS, v)) for v in out]


def _f_boosting(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """Shrunken stumps on the logit scale -- the smallest honest gradient booster."""
    rounds, eta = int(kw.get("n_rounds", 24)), float(kw.get("shrinkage", 0.18))
    n, p = len(ytr), len(xtr[0])
    p0 = sum(ytr) / n
    p0 = min(1 - EPS, max(EPS, p0))
    f_tr = [math.log(p0 / (1 - p0))] * n
    f_te = [math.log(p0 / (1 - p0))] * len(xte)
    for _ in range(rounds):
        resid = [ytr[i] - 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, f_tr[i]))))
                 for i in range(n)]
        best: tuple[float, int, float, float, float] | None = None
        for j in range(p):
            vals = sorted({r[j] for r in xtr})
            if len(vals) < 3:
                continue
            thr = vals[len(vals) // 2]
            lo = [resid[i] for i in range(n) if xtr[i][j] <= thr]
            hi = [resid[i] for i in range(n) if xtr[i][j] > thr]
            if len(lo) < 4 or len(hi) < 4:
                continue
            ml, mh = sum(lo) / len(lo), sum(hi) / len(hi)
            score = len(lo) * ml * ml + len(hi) * mh * mh
            if best is None or score > best[0]:
                best = (score, j, float(thr), ml, mh)
        if best is None:
            break
        _, j, thr, ml, mh = best
        for i in range(n):
            f_tr[i] += eta * (mh if xtr[i][j] > thr else ml) * 4.0
        for i, r in enumerate(xte):
            f_te[i] += eta * (mh if r[j] > thr else ml) * 4.0
    return [_squash(v, 1.0) for v in f_te]


def _f_neural(xtr, ytr, xte, **kw):                                   # type: ignore[no-untyped-def]
    """One tanh hidden layer, plain gradient descent, deterministic init."""
    h, epochs, lr = int(kw.get("hidden", 4)), int(kw.get("epochs", 120)), float(kw.get("lr", 0.2))
    n, p = len(ytr), len(xtr[0])
    w1 = [[math.sin(1.7 * (i + 1) * (j + 1)) * 0.4 for j in range(h)] for i in range(p)]
    b1 = [0.0] * h
    w2 = [math.cos(1.3 * (j + 1)) * 0.4 for j in range(h)]
    b2 = 0.0
    l2 = float(kw.get("l2", 1e-3))
    for _ in range(epochs):
        g1 = [[0.0] * h for _ in range(p)]
        gb1 = [0.0] * h
        g2 = [0.0] * h
        gb2 = 0.0
        for i in range(n):
            z = [sum(xtr[i][k] * w1[k][j] for k in range(p)) + b1[j] for j in range(h)]
            a = [math.tanh(v) for v in z]
            o = _squash(sum(a[j] * w2[j] for j in range(h)) + b2, 1.0)
            d = o - ytr[i]
            gb2 += d
            for j in range(h):
                g2[j] += d * a[j]
                dz = d * w2[j] * (1.0 - a[j] * a[j])
                gb1[j] += dz
                for k in range(p):
                    g1[k][j] += dz * xtr[i][k]
        for j in range(h):
            w2[j] -= lr * (g2[j] / n + l2 * w2[j])
            b1[j] -= lr * gb1[j] / n
            for k in range(p):
                w1[k][j] -= lr * (g1[k][j] / n + l2 * w1[k][j])
        b2 -= lr * gb2 / n
    out = []
    for r in xte:
        a = [math.tanh(sum(r[k] * w1[k][j] for k in range(p)) + b1[j]) for j in range(h)]
        out.append(_squash(sum(a[j] * w2[j] for j in range(h)) + b2, 1.0))
    return out


def _f_state_space(xtr, ytr, xte, **kw):                              # type: ignore[no-untyped-def]
    """Local-level Kalman on the linear score: the coefficient drifts, it is not fixed."""
    w = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if w is None:
        return None
    q_over_r = float(kw.get("q_over_r", 0.05))
    level, var = 0.0, 1.0
    for i, r in enumerate(xtr):
        s = sum(wi * xi for wi, xi in zip(w, r, strict=True))
        var += q_over_r
        k = var / (var + 1.0)
        level += k * ((2.0 * ytr[i] - 1.0) - s - level)
        var *= (1.0 - k)
    return [_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True)) + level) for r in xte]


def _f_bayesian(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """Gaussian naive Bayes with a conjugate prior on each class mean."""
    p = len(xtr[0])
    prior = float(kw.get("prior_strength", 1.0))
    stats: dict[int, tuple[list[float], list[float], float]] = {}
    for cls in (0, 1):
        rows = [xtr[i] for i in range(len(ytr)) if int(ytr[i]) == cls]
        if len(rows) < 3:
            return None
        mu = [(sum(r[j] for r in rows)) / (len(rows) + prior) for j in range(p)]
        var = [max(1e-4, sum((r[j] - mu[j]) ** 2 for r in rows) / len(rows)) for j in range(p)]
        stats[cls] = (mu, var, (len(rows) + prior) / (len(ytr) + 2 * prior))
    out = []
    for r in xte:
        lp = {}
        for cls in (0, 1):
            mu, var, pri = stats[cls]
            lp[cls] = math.log(pri) - 0.5 * sum(
                math.log(2 * math.pi * var[j]) + (r[j] - mu[j]) ** 2 / var[j] for j in range(p))
        m = max(lp.values())
        e1, e0 = math.exp(lp[1] - m), math.exp(lp[0] - m)
        out.append(min(1 - EPS, max(EPS, e1 / (e1 + e0))))
    return out


def _f_sequence(xtr, ytr, xte, **kw):                                 # type: ignore[no-untyped-def]
    """The target's own recent path, lagged into the design -- an AR(p) on the label."""
    lags = int(kw.get("lags", 3))
    def _aug(x: list[list[float]], y: list[float] | None) -> list[list[float]]:
        out = []
        for i, r in enumerate(x):
            tail = []
            for L in range(1, lags + 1):
                tail.append(2.0 * y[i - L] - 1.0 if (y is not None and i - L >= 0) else 0.0)
            out.append(list(r) + tail)
        return out
    a_tr = _aug(xtr, ytr)
    w = _ridge(a_tr, [2.0 * v - 1.0 for v in ytr], float(kw.get("alpha", 10.0)))
    if w is None:
        return None
    # The test fold cannot see its own labels: the lags carry the last TRAIN labels, decayed.
    carry = [2.0 * ytr[-L] - 1.0 if len(ytr) >= L else 0.0 for L in range(1, lags + 1)]
    return [_squash(sum(wi * xi for wi, xi in
                        zip(w, list(r) + [c * (0.8 ** t) for t, c in enumerate(carry)],
                            strict=True))) for r in xte]


def _f_graph(xtr, ytr, xte, **kw):                                    # type: ignore[no-untyped-def]
    """Features are nodes; each votes, and a node's weight is its degree in the corr graph."""
    p = len(xtr[0])
    thr = float(kw.get("threshold", 0.3))
    cols = [[r[j] for r in xtr] for j in range(p)]
    def _corr(a: list[float], b: list[float]) -> float:
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        da = math.sqrt(sum((v - ma) ** 2 for v in a))
        db = math.sqrt(sum((v - mb) ** 2 for v in b))
        return num / (da * db) if da > 0 and db > 0 else 0.0
    yc = [2.0 * v - 1.0 for v in ytr]
    votes = [_corr(cols[j], yc) for j in range(p)]
    deg = [1 + sum(1 for k in range(p) if k != j and abs(_corr(cols[j], cols[k])) > thr)
           for j in range(p)]
    # A node in a dense cluster is DOWN-weighted: its neighbours already said the same thing.
    w = [votes[j] / deg[j] for j in range(p)]
    return _pred_linear(w, xte, k=6.0)


def _f_moe(xtr, ytr, xte, **kw):                                      # type: ignore[no-untyped-def]
    """Hard gate on one feature's terciles, a ridge expert per bucket."""
    g = int(kw.get("gate_feature", 0)) % max(1, len(xtr[0]))
    vals = sorted(r[g] for r in xtr)
    q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
    def _bucket(v: float) -> int:
        return 0 if v <= q1 else (1 if v <= q2 else 2)
    experts: dict[int, list[float] | None] = {}
    for b in (0, 1, 2):
        idx = [i for i in range(len(ytr)) if _bucket(xtr[i][g]) == b]
        if len(idx) < 12:
            experts[b] = None
            continue
        experts[b] = _ridge([xtr[i] for i in idx], [2.0 * ytr[i] - 1.0 for i in idx], 10.0)
    glob = _ridge(xtr, [2.0 * v - 1.0 for v in ytr], 10.0)
    if glob is None:
        return None
    out = []
    for r in xte:
        w = experts[_bucket(r[g])] or glob
        out.append(_squash(sum(wi * xi for wi, xi in zip(w, r, strict=True))))
    return out


_FALLBACKS: dict[str, Any] = {"linear": _f_linear, "sparse": _f_sparse, "tree": _f_tree,
              "boosting": _f_boosting, "neural": _f_neural, "state_space": _f_state_space,
              "bayesian": _f_bayesian, "sequence": _f_sequence, "graph": _f_graph,
              "mixture_of_experts": _f_moe}


def _heavy(name: str, xtr: list[list[float]], ytr: list[float], xte: list[list[float]],
           params: dict[str, Any]) -> list[float] | None:
    """The accelerated path, entirely optional. Any failure returns None and the fallback runs."""
    try:
        if name == "linear":
            from sklearn.linear_model import Ridge
            m = Ridge(alpha=float(params.get("alpha", 10.0))).fit(
                xtr, [2.0 * v - 1.0 for v in ytr])
            return [_squash(float(v)) for v in m.predict(xte)]
        if name == "sparse":
            from sklearn.linear_model import Lasso
            m = Lasso(alpha=float(params.get("l1", 0.02)), max_iter=2000).fit(
                xtr, [2.0 * v - 1.0 for v in ytr])
            return [_squash(float(v)) for v in m.predict(xte)]
        if name == "tree":
            from sklearn.tree import DecisionTreeClassifier
            m = DecisionTreeClassifier(max_depth=int(params.get("depth", 2)),
                                       min_samples_leaf=8, random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "boosting":
            from sklearn.ensemble import HistGradientBoostingClassifier
            m = HistGradientBoostingClassifier(
                max_depth=3, max_iter=int(params.get("n_rounds", 120)),
                learning_rate=float(params.get("shrinkage", 0.05)), l2_regularization=1.0,
                random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "neural":
            from sklearn.neural_network import MLPClassifier
            m = MLPClassifier(hidden_layer_sizes=(int(params.get("hidden", 16)), 8),
                              alpha=1e-2, max_iter=300, random_state=0).fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
        if name == "bayesian":
            from sklearn.naive_bayes import GaussianNB
            m = GaussianNB().fit(xtr, ytr)
            return [float(v) for v in m.predict_proba(xte)[:, 1]]
    except Exception:
        return None
    return None


def fit_predict(name: str, xtr: list[list[float]], ytr: list[float], xte: list[list[float]],
                *, params: dict[str, Any] | None = None, allow_heavy: bool = True
                ) -> tuple[list[float] | None, str]:
    """(probabilities, backend). The fallback ALWAYS runs when the heavy path is absent."""
    if name not in FAMILIES:
        raise KeyError(name)
    p = dict(params or {})
    if allow_heavy:
        out = _heavy(name, xtr, ytr, xte, p)
        if out is not None:
            return [min(1 - EPS, max(EPS, float(v))) for v in out], "heavy"
    got: list[float] | None = _FALLBACKS[name](xtr, ytr, xte, **p)
    if got is None:
        return None, "fallback"
    return [min(1 - EPS, max(EPS, float(v))) for v in got], "fallback"


# --------------------------------------------------------------- scoring
def log_score(p: Sequence[float], y: Sequence[float]) -> float:
    n = len(y)
    if n == 0:
        return 0.0
    tot = 0.0
    for i in range(n):
        q = min(1 - EPS, max(EPS, p[i]))
        tot += y[i] * math.log(q) + (1 - y[i]) * math.log(1 - q)
    return tot / n


def walk_forward(name: str, x: list[list[float]], y: list[float], *, n_folds: int = 4,
                 params: dict[str, Any] | None = None, allow_heavy: bool = True,
                 min_rows: int = MIN_ROWS) -> dict[str, Any]:
    """Expanding-window folds; the zoo's convention so the two are comparable."""
    fam = FAMILIES.get(name)
    if fam is None:
        raise KeyError(name)
    n = len(y)
    avail = availability()[name]
    base_row = {"family": name, "n": n, "tax": fam.tax, "parent": fam.parent,
                "heavy_verdict": avail["heavy_verdict"], "backends_present":
                avail["backends_present"]}
    if n < min_rows:
        return {**base_row, "verdict": UNMEASURED, "backend": "none",
                "why": f"need {min_rows} rows, have {n}"}
    edges = [int(n // 3 + (n - n // 3) * i / n_folds) for i in range(n_folds + 1)]
    scores, bases, briers, backends = [], [], [], set()
    for i in range(n_folds):
        a, b = edges[i], edges[i + 1]
        if b - a < 10 or a < min_rows // 3:
            continue
        xtr, xte = _standardise(x[:a], x[a:b])
        ytr, yte = y[:a], y[a:b]
        if len(set(ytr)) < 2:
            continue
        probs, backend = fit_predict(name, xtr, ytr, xte, params=params, allow_heavy=allow_heavy)
        if probs is None:
            continue
        backends.add(backend)
        p0 = sum(ytr) / len(ytr)
        scores.append(log_score(probs, yte))
        bases.append(log_score([p0] * len(yte), yte))
        briers.append(sum((probs[k] - yte[k]) ** 2 for k in range(len(yte))) / len(yte))
    if not scores:
        return {**base_row, "verdict": UNMEASURED, "backend": "none",
                "why": "no scorable fold (constant labels or every fit refused)"}
    gain = sum(scores) / len(scores) - sum(bases) / len(bases)
    net = gain - fam.tax
    return {**base_row, "folds": len(scores),
            "log_score": round(sum(scores) / len(scores), 6),
            "baseline": round(sum(bases) / len(bases), 6),
            "gain": round(gain, 6), "net_gain": round(net, 6),
            "brier": round(sum(briers) / len(briers), 6),
            "backend": "heavy" if "heavy" in backends else "fallback",
            "verdict": POSITIVE if net > 0 else NEGATIVE}


def compete(x: list[list[float]], y: list[float], *, families: Sequence[str] = ORDER,
            n_folds: int = 4, allow_heavy: bool = True, min_rows: int = MIN_ROWS
            ) -> dict[str, Any]:
    """Every family on the same folds. The winner is the best NET gain, and only if positive."""
    res = {f: walk_forward(f, x, y, n_folds=n_folds, allow_heavy=allow_heavy,
                           min_rows=min_rows) for f in families}
    scored = {f: r for f, r in res.items() if r.get("net_gain") is not None}
    win = max(scored, key=lambda f: float(scored[f]["net_gain"])) if scored else None
    return {"results": res,
            "winner": win if win and float(scored[win]["net_gain"]) > 0 else None,
            "n_unmeasured": sum(1 for r in res.values() if r.get("verdict") == UNMEASURED),
            "rule": "winner = argmax (OOS log score - baseline - declared tax), only if > 0"}
