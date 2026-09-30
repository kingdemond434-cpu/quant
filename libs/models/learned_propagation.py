"""Two learned predictors over the cross-asset daily panel, numpy only, walk-forward, PIT.

WHY THIS EXISTS. `libs/research/adapters/pyg_temporal.py` trains a GConvGRU and hands back a
REPRESENTATION packet: node embeddings and a loss curve, nothing the gauntlet can judge. And it
needs torch, which the trading box does not have. This module is the numpy version of the two
ideas that packet gestured at, built so that its output is a PREDICTION per (day, instrument) that
a family can turn into signals and the gauntlet can then certify or kill:

  1. GRAPH PROPAGATION ("gnn"). Nodes are instruments, edges are measured on the TRAINING WINDOW
     only: either the lead-lag correlation corr(z_j,t , z_i,t+1) (j leads i) or the
     contemporaneous correlation corr(z_j,t , z_i,t). Each node's feature vector is propagated
     one or two hops through the row-normalised, top-k sparsified, SIGNED adjacency, and one
     ridge (closed form, weights shared by every node, like a GCN layer) maps
     [own features, 1-hop, 2-hop] to the next day's volatility-scaled return. The economic
     claim is information diffusion: news priced first in one market reaches the slower one with
     a lag, and the graph says which markets are fast for which.

  2. ATTENTION OVER THE INSTRUMENT'S OWN RECENT PATH ("attention"). A single- or few-head
     scaled dot-product attention whose query is today's token and whose keys are the last L
     days' tokens (return, absolute return, the panel's mean return, a position code). Query and
     key projections are trained by minibatch Adam with hand-written gradients; the readout is
     then re-solved by ridge on the attended context. Weights are shared across instruments. The
     claim is state dependence: whether yesterday's move continues or reverts depends on what the
     recent path looked like, which a fixed-lag linear model cannot express.

POINT IN TIME, BY CONSTRUCTION. Everything is indexed on the broker-date grid. The prediction in
row t is for the return from close(t) to close(t+1) and uses:
  * features at t built from returns <= t (volatility is a causal EWMA; its scale for r_t is
    sigma_{t-1});
  * a model fitted at refit index k <= t on training rows s <= k-1, whose targets are returns
    <= k <= t;
  * a refit schedule anchored at the START of the grid (k = MIN_TRAIN, MIN_TRAIN + REFIT, ...),
    so appending or perturbing later data can never move an earlier refit.
A test perturbs the future and asserts every earlier prediction is bit-identical.

NO HYPERPARAMETER HERE WAS CHOSEN ON THE TEST PERIOD. The constants below were fixed before the
first run of the measurable contract and every configuration in the grid is reported, charged as
a trial, and never pruned by its out-of-sample result.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

#: Walk-forward schedule (rows of the daily grid). Declared, never searched.
MIN_TRAIN = 500
REFIT_EVERY = 21
TRAIN_WINDOW = 1000
#: Ridge penalty as a multiple of the row count on standardised columns: the fitted slope is
#: shrunk by ~1/(1 + alpha). Daily returns are mostly noise, so the shrinkage is heavy on purpose.
RIDGE_ALPHA = 0.5
VOL_HALFLIFE = 20
CLIP_Z = 5.0
#: Edges kept per node after ranking by |weight|; the rest are zeroed before normalising.
TOP_K = 5
#: Commission per side as a fraction of notional (Fusion Zero publishes USD 2.25 per 100k lot
#: per side = 0.225bp; rounded up to 0.25bp and applied to every instrument).
COMMISSION_PER_SIDE = 2.5e-5
TRADING_DAYS = 252
#: Cross-sections thinner than this carry no IC reading for the day.
MIN_CROSS_SECTION = 5

#: The declared grids. EVERY entry is a trial; the first entry of each is the pre-declared
#: primary configuration the contract headlines, chosen before any result existed.
GNN_GRID: tuple[dict[str, Any], ...] = (
    {"adjacency": "lead_lag", "layers": 1},
    {"adjacency": "lead_lag", "layers": 2},
    {"adjacency": "corr", "layers": 1},
    {"adjacency": "corr", "layers": 2},
)
ATTENTION_GRID: tuple[dict[str, Any], ...] = (
    {"heads": 1, "lookback": 20},
    {"heads": 2, "lookback": 20},
    {"heads": 1, "lookback": 10},
    {"heads": 2, "lookback": 10},
)
ADJACENCIES = ("lead_lag", "corr")

#: Attention training (declared). Head dimension, Adam step, epochs on the first fit and on each
#: warm-started refit, minibatch, L2 on the projections.
ATT_DIM = 4
ATT_LR = 0.01
ATT_EPOCHS_FIRST = 5
ATT_EPOCHS_WARM = 2
ATT_BATCH = 512
ATT_L2 = 1e-3
ATT_SEED = 7


# ================================================================================ the panel
@dataclass
class Panel:
    """The daily cross-asset grid. `ret[t, i]` = log close(t)/close(prev grid date), NaN where
    instrument i printed no bar on date t. `cost[t, i]` = one-side cost fraction (half the day's
    median spread over price, plus commission), NaN when unmeasurable."""

    dates: pd.DatetimeIndex
    symbols: list[str]
    ret: np.ndarray
    cost: np.ndarray


def _utc_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index, utc=True, errors="coerce"))
    out = out[~out.index.isna()]
    return out[~out.index.duplicated(keep="last")].sort_index()


def daily_panel(bars: Mapping[str, pd.DataFrame],
                tick_sizes: Mapping[str, float] | None = None) -> Panel:
    """Broker-date closes for every instrument on one weekday grid.

    The grid is the union of Monday-Friday broker dates any instrument printed on. A crypto CFD's
    weekend is folded into Monday's return (Friday close to Monday close), which is what a
    weekday-only desk holding it would earn. A missing day is NaN, never a zero return.
    """
    syms = sorted(bars)
    closes: dict[str, pd.Series] = {}
    costs: dict[str, pd.Series] = {}
    for s in syms:
        d = _utc_index(bars[s])
        if d.empty or "close" not in d.columns:
            continue
        day = d.index.normalize()
        c = d["close"].astype(float)
        closes[s] = c.groupby(day).last()
        tick = float((tick_sizes or {}).get(s) or 0.0)
        if "spread" in d.columns and tick > 0:
            sp = (d["spread"].astype(float) * tick).groupby(day).median()
            costs[s] = 0.5 * sp / closes[s] + COMMISSION_PER_SIDE
    syms = [s for s in syms if s in closes]
    if not syms:
        return Panel(pd.DatetimeIndex([]), [], np.zeros((0, 0)), np.zeros((0, 0)))
    grid = pd.DatetimeIndex(sorted(set().union(*[set(v.index) for v in closes.values()])))
    grid = grid[grid.weekday < 5]
    ret = np.full((len(grid), len(syms)), np.nan)
    cost = np.full((len(grid), len(syms)), np.nan)
    for j, s in enumerate(syms):
        c = closes[s]
        on_grid = c.reindex(grid)
        printed = on_grid.notna().to_numpy()
        lc = np.log(on_grid.ffill().to_numpy(dtype=float))
        r = np.full(len(grid), np.nan)
        r[1:] = lc[1:] - lc[:-1]
        r[~printed] = np.nan
        ret[:, j] = r
        if s in costs:
            cost[:, j] = costs[s].reindex(grid).to_numpy(dtype=float)
    return Panel(grid, syms, ret, cost)


# ============================================================================= features
def causal_vol(ret: np.ndarray, halflife: int = VOL_HALFLIFE) -> np.ndarray:
    """sigma[t] from returns <= t (EWMA of squares, NaN-skipping). NaN until 20 observations."""
    lam = 0.5 ** (1.0 / float(halflife))
    t_n, n = ret.shape
    out = np.full((t_n, n), np.nan)
    var = np.full(n, np.nan)
    seen = np.zeros(n, dtype=int)
    warm: list[list[float]] = [[] for _ in range(n)]
    for t in range(t_n):
        r = ret[t]
        for j in range(n):
            x = r[j]
            if not np.isfinite(x):
                continue
            seen[j] += 1
            if seen[j] <= 20:
                warm[j].append(x * x)
                if seen[j] == 20:
                    var[j] = float(np.mean(warm[j]))
                continue
            var[j] = lam * var[j] + (1.0 - lam) * x * x
        out[t] = np.sqrt(var)
    out[out <= 0] = np.nan
    return out


@dataclass
class Design:
    """Everything the models share, all causal. `z[t]` = r_t / sigma_{t-1}; `y[t]` = z[t+1]
    (the target of row t); `x[t, i, :]` = own features at t; `sigma[t]` is the scale known at t
    that `y[t]` is expressed in."""

    z: np.ndarray
    y: np.ndarray
    x: np.ndarray
    sigma: np.ndarray


OWN_FEATURES = ("z_t", "z_t-1", "z_t-2", "mean5", "mean20")


def design(panel: Panel) -> Design:
    ret = panel.ret
    sig = causal_vol(ret)
    t_n, n = ret.shape
    prev = np.full_like(sig, np.nan)
    prev[1:] = sig[:-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.clip(ret / prev, -CLIP_Z, CLIP_Z)
    z0 = np.nan_to_num(z)
    y = np.full((t_n, n), np.nan)
    y[:-1] = z[1:]

    def lag(a: np.ndarray, k: int) -> np.ndarray:
        o = np.zeros_like(a)
        if k < a.shape[0]:
            o[k:] = a[:a.shape[0] - k]
        return o

    cs = np.cumsum(z0, axis=0)

    def trail_mean(w: int) -> np.ndarray:
        o = cs.copy()
        o[w:] = cs[w:] - cs[:-w]
        return o / float(w)

    x = np.stack([z0, lag(z0, 1), lag(z0, 2), trail_mean(5), trail_mean(20)], axis=-1)
    return Design(z=z, y=y, x=x, sigma=sig)


# ================================================================================ ridge
@dataclass
class Ridge:
    mu: np.ndarray
    sd: np.ndarray
    w: np.ndarray
    b: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        out: np.ndarray = ((x - self.mu) / self.sd) @ self.w + self.b
        return out


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float = RIDGE_ALPHA) -> Ridge:
    """Closed-form ridge on standardised columns; the penalty is `alpha * n`."""
    n, f = x.shape
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    xs = (x - mu) / sd
    b = float(y.mean())
    w = np.linalg.solve(xs.T @ xs + alpha * n * np.eye(f), xs.T @ (y - b))
    return Ridge(mu, sd, w, b)


# ========================================================================= walk-forward
def refit_points(t_n: int, min_train: int = MIN_TRAIN,
                 refit_every: int = REFIT_EVERY) -> list[int]:
    """Refit indices, anchored at the START of the grid so the future cannot move them."""
    return list(range(min_train, t_n, refit_every))


def walk_forward(t_n: int, n: int, fit: Callable[[int, int, Any], Any],
                 predict: Callable[[Any, int, int], np.ndarray], *,
                 min_train: int = MIN_TRAIN, refit_every: int = REFIT_EVERY,
                 window: int = TRAIN_WINDOW) -> np.ndarray:
    """preds[t, i] for every row t >= min_train. `fit(lo, k, prev_model)` sees rows [lo, k-1]
    only (targets <= row k); `predict(model, a, b)` returns rows [a, b)."""
    preds = np.full((t_n, n), np.nan)
    model: Any = None
    for k in refit_points(t_n, min_train, refit_every):
        lo = max(0, k - window)
        model = fit(lo, k, model)
        if model is None:
            continue
        hi = min(k + refit_every, t_n)
        preds[k:hi] = predict(model, k, hi)
    return preds


def _train_rows(xd: np.ndarray, y: np.ndarray, lo: int, k: int) -> tuple[np.ndarray, np.ndarray]:
    xs = xd[lo:k].reshape(-1, xd.shape[-1])
    ys = y[lo:k].reshape(-1)
    ok = np.isfinite(ys)
    return xs[ok], ys[ok]


def ridge_predictions(d: Design, *, features: np.ndarray | None = None,
                      alpha: float = RIDGE_ALPHA, **wf: int) -> np.ndarray:
    """The baseline: one pooled ridge on each node's OWN lagged features, same folds."""
    xd = d.x if features is None else features
    t_n, n = d.y.shape

    def fit(lo: int, k: int, _prev: Any) -> Ridge | None:
        xs, ys = _train_rows(xd, d.y, lo, k)
        return fit_ridge(xs, ys, alpha) if ys.size > xd.shape[-1] * 5 else None

    def predict(m: Ridge, a: int, b: int) -> np.ndarray:
        return m.predict(xd[a:b].reshape(-1, xd.shape[-1])).reshape(b - a, n)

    return walk_forward(t_n, n, fit, predict, **wf)


def lagged_token_features(d: Design, lookback: int) -> np.ndarray:
    """Flattened [z, |z|, market] over the last `lookback` rows: the ridge the attention model
    must beat on exactly its own inputs."""
    tok = tokens(d)
    t_n, n, f = tok.shape
    out = np.zeros((t_n, n, lookback * f))
    for ell in range(lookback):
        out[ell:, :, ell * f:(ell + 1) * f] = tok[:t_n - ell]
    return out


# ======================================================================== graph model
def adjacency(x0: np.ndarray, y: np.ndarray, kind: str, top_k: int = TOP_K) -> np.ndarray:
    """Signed, top-k, row-normalised adjacency from TRAINING rows only.

    kind="lead_lag": A[i, j] = corr(z_j,t , z_i,t+1) -- j's move today, i's move tomorrow.
    kind="corr":     A[i, j] = corr(z_j,t , z_i,t)   -- the contemporaneous co-movement graph.
    """
    if kind not in ADJACENCIES:
        raise ValueError(f"unknown adjacency {kind!r}; known: {ADJACENCIES}")
    tgt = y if kind == "lead_lag" else np.where(x0 != 0, x0, np.nan)
    n = x0.shape[1]
    a = np.zeros((n, n))
    for i in range(n):
        m = np.isfinite(tgt[:, i])
        if m.sum() < 30:
            continue
        yi = tgt[m, i] - tgt[m, i].mean()
        xj = x0[m] - x0[m].mean(axis=0)
        den = np.sqrt((xj * xj).sum(axis=0) * (yi * yi).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            c = (xj * yi[:, None]).sum(axis=0) / den
        a[i] = np.nan_to_num(c)
    np.fill_diagonal(a, 0.0)
    if top_k and top_k < n - 1:
        keep = np.argsort(-np.abs(a), axis=1)[:, :top_k]
        mask = np.zeros_like(a, dtype=bool)
        np.put_along_axis(mask, keep, True, axis=1)
        a = np.where(mask, a, 0.0)
    s = np.abs(a).sum(axis=1, keepdims=True)
    return np.divide(a, s, out=np.zeros_like(a), where=s > 0)


def propagate(x: np.ndarray, a: np.ndarray, layers: int) -> np.ndarray:
    """[H0, A H0, A^2 H0, ...] along the feature axis; x is (T, N, F)."""
    hs = [x]
    cur = x
    for _ in range(int(layers)):
        cur = np.einsum("ij,tjf->tif", a, cur)
        hs.append(cur)
    return np.concatenate(hs, axis=-1)


@dataclass
class GraphModel:
    a: np.ndarray
    ridge: Ridge
    layers: int


def gnn_predictions(d: Design, *, adjacency_kind: str = "lead_lag", layers: int = 1,
                    alpha: float = RIDGE_ALPHA, top_k: int = TOP_K, **wf: int) -> np.ndarray:
    t_n, n = d.y.shape

    def fit(lo: int, k: int, _prev: Any) -> GraphModel | None:
        a = adjacency(d.x[lo:k, :, 0], d.y[lo:k], adjacency_kind, top_k)
        h = propagate(d.x[lo:k], a, layers)
        xs, ys = _train_rows(h, d.y[lo:k], 0, k - lo)
        if ys.size < h.shape[-1] * 5:
            return None
        return GraphModel(a, fit_ridge(xs, ys, alpha), layers)

    def predict(m: GraphModel, lo: int, hi: int) -> np.ndarray:
        h = propagate(d.x[lo:hi], m.a, m.layers)
        return m.ridge.predict(h.reshape(-1, h.shape[-1])).reshape(hi - lo, n)

    return walk_forward(t_n, n, fit, predict, **wf)


# ==================================================================== attention model
def tokens(d: Design) -> np.ndarray:
    """(T, N, 3): the day's vol-scaled return, its absolute size (centred), and the panel mean."""
    z0 = np.nan_to_num(d.z)
    cnt = np.isfinite(d.z).sum(axis=1)
    mkt = z0.sum(axis=1) / np.maximum(cnt, 1)
    return np.stack([z0, np.abs(z0) - 0.8, np.broadcast_to(mkt[:, None], z0.shape)], axis=-1)


def _sequences(tok: np.ndarray, lookback: int) -> np.ndarray:
    """(T, N, L, F) with position 0 = today, position l = l days ago (zeros before the start)."""
    t_n, n, f = tok.shape
    seq = np.zeros((t_n, n, lookback, f))
    for ell in range(lookback):
        seq[ell:, :, ell, :] = tok[:t_n - ell]
    return seq


@dataclass
class Attention:
    wq: np.ndarray   # (H, D, F+1)
    wk: np.ndarray   # (H, D, F+2)
    ridge: Ridge | None = None

    def context(self, seq: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        b, lk, _f = seq.shape
        qin = np.concatenate([seq[:, 0, :], np.ones((b, 1))], axis=1)
        pos = np.broadcast_to((np.arange(lk) / lk)[None, :, None], (b, lk, 1))
        kin = np.concatenate([seq, pos, np.ones((b, lk, 1))], axis=2)
        q = np.einsum("hdk,bk->bhd", self.wq, qin)
        k = np.einsum("hdk,blk->bhld", self.wk, kin)
        s = np.einsum("bhd,bhld->bhl", q, k) / math.sqrt(self.wq.shape[1])
        s = s - s.max(axis=2, keepdims=True)
        e = np.exp(s)
        al = e / e.sum(axis=2, keepdims=True)
        c = np.einsum("bhl,blf->bhf", al, seq)
        feats = np.concatenate([c.reshape(b, -1), seq[:, 0, :]], axis=1)
        return feats, {"qin": qin, "kin": kin, "q": q, "k": k, "al": al}


def _adam_step(p: np.ndarray, g: np.ndarray, st: dict[str, Any], key: str, t: int,
               lr: float = ATT_LR) -> None:
    m = st.setdefault(key + "_m", np.zeros_like(p))
    v = st.setdefault(key + "_v", np.zeros_like(p))
    m *= 0.9
    m += 0.1 * g
    v *= 0.999
    v += 0.001 * g * g
    p -= lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)


def train_attention(seq: np.ndarray, y: np.ndarray, *, heads: int, epochs: int,
                    init: Attention | None = None, seed: int = ATT_SEED) -> Attention:
    """Minibatch Adam on (Wq, Wk, w) with hand-written gradients, then a ridge readout."""
    rng = np.random.default_rng(seed)
    b_all, _lk, f = seq.shape
    if init is not None and init.wq.shape[0] == heads:
        model = Attention(init.wq.copy(), init.wk.copy())
    else:
        model = Attention(rng.normal(0, 0.3, (heads, ATT_DIM, f + 1)),
                          rng.normal(0, 0.3, (heads, ATT_DIM, f + 2)))
    nf = heads * f + f
    w = np.zeros(nf + 1)
    st: dict[str, Any] = {}
    step = 0
    ysd = float(np.std(y)) or 1.0
    for _ in range(int(epochs)):
        order = rng.permutation(b_all)
        for a0 in range(0, b_all, ATT_BATCH):
            idx = order[a0:a0 + ATT_BATCH]
            sb, yb = seq[idx], y[idx] / ysd
            bsz = idx.size
            feats, cache = model.context(sb)
            hmat = np.concatenate([feats, np.ones((bsz, 1))], axis=1)
            err = hmat @ w - yb
            gw = hmat.T @ err / bsz
            gc = (err[:, None] * w[None, :heads * f]).reshape(bsz, heads, f) / bsz
            # d loss / d alpha_l = gc . v_l ; softmax backward; then through q and k.
            ga = np.einsum("bhf,blf->bhl", gc, sb)
            al = cache["al"]
            gs = al * (ga - (al * ga).sum(axis=2, keepdims=True)) / math.sqrt(ATT_DIM)
            gq = np.einsum("bhl,bhld->bhd", gs, cache["k"])
            gk = np.einsum("bhl,bhd->bhld", gs, cache["q"])
            gwq = np.einsum("bhd,bk->hdk", gq, cache["qin"]) + ATT_L2 * model.wq
            gwk = np.einsum("bhld,blk->hdk", gk, cache["kin"]) + ATT_L2 * model.wk
            step += 1
            _adam_step(model.wq, gwq, st, "wq", step)
            _adam_step(model.wk, gwk, st, "wk", step)
            _adam_step(w, gw, st, "w", step)
    feats, _ = model.context(seq)
    model.ridge = fit_ridge(feats, y)
    return model


def attention_predictions(d: Design, *, heads: int = 1, lookback: int = 20,
                          **wf: int) -> np.ndarray:
    t_n, n = d.y.shape
    seq = _sequences(tokens(d), int(lookback))
    f = seq.shape[-1]

    def fit(lo: int, k: int, prev: Attention | None) -> Attention | None:
        s = seq[lo:k].reshape(-1, int(lookback), f)
        ys = d.y[lo:k].reshape(-1)
        ok = np.isfinite(ys)
        if ok.sum() < 200:
            return prev
        return train_attention(s[ok], ys[ok], heads=int(heads),
                               epochs=ATT_EPOCHS_WARM if prev is not None else ATT_EPOCHS_FIRST,
                               init=prev, seed=ATT_SEED + k)

    def predict(m: Attention, a: int, b: int) -> np.ndarray:
        feats, _ = m.context(seq[a:b].reshape(-1, int(lookback), f))
        assert m.ridge is not None
        return m.ridge.predict(feats).reshape(b - a, n)

    return walk_forward(t_n, n, fit, predict, **wf)


# ========================================================================== dispatcher
def predictions(d: Design, model: str, config: Mapping[str, Any], **wf: int) -> np.ndarray:
    """One walk-forward prediction panel for (model, config). Every call is one trial."""
    if model == "gnn":
        return gnn_predictions(d, adjacency_kind=str(config.get("adjacency", "lead_lag")),
                               layers=int(config.get("layers", 1)), **wf)
    if model == "attention":
        return attention_predictions(d, heads=int(config.get("heads", 1)),
                                     lookback=int(config.get("lookback", 20)), **wf)
    if model == "ridge":
        return ridge_predictions(d, **wf)
    if model == "ridge_lags":
        return ridge_predictions(
            d, features=lagged_token_features(d, int(config.get("lookback", 20))), **wf)
    if model == "naive_last":
        p = np.where(np.isfinite(d.z), d.z, np.nan)
        p[:wf.get("min_train", MIN_TRAIN)] = np.nan
        return p
    if model == "zero":
        p = np.zeros_like(d.y)
        p[:wf.get("min_train", MIN_TRAIN)] = np.nan
        return p
    raise ValueError(f"unknown model {model!r}")


# ============================================================================= metrics
def _rank(a: np.ndarray) -> np.ndarray:
    r = np.empty_like(a)
    r[np.argsort(a, kind="mergesort")] = np.arange(a.size, dtype=float)
    return r


def _tstat(x: Sequence[float]) -> float | None:
    a = np.asarray(x, dtype=float)
    if a.size < 3:
        return None
    sd = float(a.std(ddof=1))
    return float(a.mean() / (sd / math.sqrt(a.size))) if sd > 0 else None


def _r(v: float | None, k: int = 5) -> float | None:
    return None if v is None or not math.isfinite(v) else round(float(v), k)


def evaluate(preds: np.ndarray, panel: Panel, d: Design,
             start: int = MIN_TRAIN) -> dict[str, Any]:
    """OOS IC, rank-IC, hit rate and a cost-charged dollar-neutral long-short book.

    Row t's prediction is scored against r_{t+1}. The book ranks the day's predictions, demeans
    the ranks, divides by each instrument's sigma_t (known at t) and scales gross exposure to 1;
    it pays, on every change of weight, the instrument's one-side cost from the day's own median
    spread in the bars plus commission. An instrument with no measurable cost is priced at the
    cross-section's median cost that day rather than at zero.
    """
    t_n, n = preds.shape
    fwd = np.full((t_n, n), np.nan)
    fwd[:-1] = panel.ret[1:]
    ics, rics, gross, net, turn = [], [], [], [], []
    hits = total = 0
    w_prev = np.zeros(n)
    days = 0
    for t in range(start, t_n - 1):
        p, r = preds[t], fwd[t]
        ok = np.isfinite(p) & np.isfinite(r) & np.isfinite(d.sigma[t])
        if ok.sum() < MIN_CROSS_SECTION:
            continue
        days += 1
        pv, rv = p[ok], r[ok]
        nz = (pv != 0) & (rv != 0)
        hits += int((np.sign(pv[nz]) == np.sign(rv[nz])).sum())
        total += int(nz.sum())
        if np.std(pv) > 0 and np.std(rv) > 0:
            ics.append(float(np.corrcoef(pv, rv)[0, 1]))
            rics.append(float(np.corrcoef(_rank(pv), _rank(rv))[0, 1]))
            rk = _rank(pv)
            raw = (rk - rk.mean()) / d.sigma[t][ok]
            w = np.zeros(n)
            w[ok] = raw / np.abs(raw).sum()
        else:
            w = np.zeros(n)
        c = panel.cost[t].copy()
        med = np.nanmedian(c) if np.isfinite(c).any() else 0.0
        c = np.where(np.isfinite(c), c, med)
        dw = np.abs(w - w_prev)
        g = float(np.nansum(w * np.nan_to_num(r)))
        cost_t = float((dw * c).sum())
        gross.append(g)
        net.append(g - cost_t)
        turn.append(float(dw.sum()))
        w_prev = w

    def sharpe(x: list[float]) -> float | None:
        a = np.asarray(x, dtype=float)
        if a.size < 20 or float(a.std(ddof=1)) <= 0:
            return None
        return float(a.mean() / a.std(ddof=1) * math.sqrt(TRADING_DAYS))

    half = len(net) // 2
    return {
        "oos_days": days,
        "ic_mean": _r(float(np.mean(ics)) if ics else None),
        "ic_t": _r(_tstat(ics), 3),
        "rank_ic_mean": _r(float(np.mean(rics)) if rics else None),
        "rank_ic_t": _r(_tstat(rics), 3),
        "hit_rate": _r(hits / total if total else None, 4),
        "n_predictions_scored": total,
        "ls_sharpe_gross": _r(sharpe(gross), 3),
        "ls_sharpe_net": _r(sharpe(net), 3),
        "ls_sharpe_net_first_half": _r(sharpe(net[:half]), 3),
        "ls_sharpe_net_second_half": _r(sharpe(net[half:]), 3),
        "ls_mean_daily_net_bp": _r(float(np.mean(net)) * 1e4 if net else None, 3),
        "ls_mean_daily_turnover": _r(float(np.mean(turn)) if turn else None, 4),
        "ls_annual_cost_bp": _r(float(np.mean(np.subtract(gross, net))) * 1e4 * TRADING_DAYS
                                if net else None, 1),
    }


def per_symbol_ic(preds: np.ndarray, panel: Panel, start: int = MIN_TRAIN
                  ) -> dict[str, dict[str, float | int | None]]:
    """Time-series IC of each instrument's own prediction against its own next return."""
    fwd = np.full_like(panel.ret, np.nan)
    fwd[:-1] = panel.ret[1:]
    out: dict[str, dict[str, float | int | None]] = {}
    for j, s in enumerate(panel.symbols):
        p, r = preds[start:, j], fwd[start:, j]
        ok = np.isfinite(p) & np.isfinite(r)
        if ok.sum() < 30 or np.std(p[ok]) == 0 or np.std(r[ok]) == 0:
            out[s] = {"n": int(ok.sum()), "ic": None, "t": None}
            continue
        ic = float(np.corrcoef(p[ok], r[ok])[0, 1])
        nn = int(ok.sum())
        t = ic * math.sqrt(max(nn - 2, 1) / max(1e-12, 1 - ic * ic))
        out[s] = {"n": nn, "ic": round(ic, 5), "t": round(t, 3)}
    return out
