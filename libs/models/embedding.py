"""A self-supervised market embedding and the historical-analogue engine built on it.

    z_t = Encoder(X_{t-L:t})

The encoder is a PCA over standardised feature windows -- deliberately linear, so the embedding
can be read, and trained on NO trading labels: its objective is masked-bar reconstruction (hide
the last bar of the window, predict its features from the embedding of the rest), scored as the
gain over predicting the window mean. That is the self-supervised task; when the gain is ~0 the
embedding has learned nothing and says so.

WHAT z_t IS FOR (never a buy/sell): nearest-neighbour regime analogues, conditioning for the
allocator's state posterior, anomaly distance, execution state. `analogues` implements
Bridgewater's case method mechanically: given now, retrieve the k most similar past windows,
report what matched (the features nearest in z), what differed, and the DISTRIBUTION of what
followed -- never "1974 looked similar, therefore".

TWO OBJECTIVES, ONE FUNCTION CLASS. `WindowPCA` and `ContrastiveEncoder` are both a linear map
of the standardised window; they differ only in what they are asked to keep. PCA keeps
VARIANCE, and in return data variance is owned by the rare bar -- a news spike, an open-gap --
so PCA's top directions are the shapes of a handful of windows. The contrastive encoder keeps
what SURVIVES A PERTURBATION of the typical window (jitter plus masked bars) while still telling
that window from every other one (InfoNCE), which is a statement about the median window, not
the loudest. Neither is admitted on its self-supervised score: `representation_gain` fits a
ridge on the embedding and a ridge on the raw last bars, walk-forward, and a representation is
kept only when it forecasts the forward quantity better than the bars it was built from.
"""
from __future__ import annotations

import copy
from typing import Any

import numpy as np


class MarketEncoder:
    def __init__(self, window: int = 24, dim: int = 8) -> None:
        self.window = window
        self.dim = dim
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.components: np.ndarray | None = None
        self.explained: np.ndarray | None = None
        self.reconstruction_gain: float = float("nan")

    def _windows(self, x: np.ndarray) -> np.ndarray:
        from numpy.lib.stride_tricks import sliding_window_view
        assert self.mu is not None and self.sd is not None
        xs = np.nan_to_num((x - self.mu) / self.sd)
        w = sliding_window_view(xs, (self.window, xs.shape[1]))[:, 0]      # (T-L+1, L, F)
        return w.reshape(w.shape[0], -1)

    def fit(self, x: np.ndarray) -> MarketEncoder:
        self.mu = np.nanmean(x, axis=0)
        sd = np.nanstd(x, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        w = self._windows(x)
        w = w - w.mean(axis=0)
        _u, s, vt = np.linalg.svd(w, full_matrices=False)
        k = int(min(self.dim, vt.shape[0]))
        self.components = vt[:k]
        var = s ** 2
        self.explained = var[:k] / max(var.sum(), 1e-12)
        # SELF-SUPERVISED OBJECTIVE: reconstruct the masked last bar from the rest.
        full = self._windows(x)
        n_f = x.shape[1]
        head, last = full[:, :-n_f], full[:, -n_f:]
        z = (head - head.mean(axis=0)) @ np.linalg.pinv(self.components[:, :-n_f]).T \
            if self.components.shape[1] > n_f else head[:, :k]
        zb = np.column_stack([np.ones(z.shape[0]), z])
        beta = np.linalg.lstsq(zb, last, rcond=None)[0]
        pred = zb @ beta
        err = float(np.mean((last - pred) ** 2))
        base = float(np.mean((last - last.mean(axis=0)) ** 2))
        self.reconstruction_gain = float(1.0 - err / base) if base > 0 else 0.0
        return self

    def embed(self, x: np.ndarray) -> np.ndarray:
        assert self.components is not None
        w = self._windows(x)
        out: np.ndarray = (w - w.mean(axis=0)) @ self.components.T
        return out


def analogues(z_now: np.ndarray, z_hist: np.ndarray, forward: np.ndarray, *, k: int = 20,
              feature_names: list[str] | None = None, x_now: np.ndarray | None = None,
              x_hist: np.ndarray | None = None, exclude_last: int = 0) -> dict[str, Any]:
    """The k nearest past windows in embedding space, and what followed them.

    `forward` is the realised quantity after each historical window (e.g. the next-24-bar
    return); the answer is its DISTRIBUTION over the analogues, with the match quality, never a
    point forecast. When raw features are supplied the report also says which features matched
    and which differed most.
    """
    n = z_hist.shape[0] - exclude_last
    d = np.sqrt(((z_hist[:n] - z_now[None, :]) ** 2).sum(axis=1))
    idx = np.argsort(d)[:k]
    fwd = forward[idx]
    out: dict[str, Any] = {
        "k": len(idx), "indices": idx.tolist(), "distance_mean": round(float(d[idx].mean()), 4),
        "distance_all_median": round(float(np.median(d)), 4),
        "forward": {"mean": round(float(fwd.mean()), 6), "median": round(float(np.median(fwd)), 6),
                    "p10": round(float(np.quantile(fwd, 0.1)), 6),
                    "p90": round(float(np.quantile(fwd, 0.9)), 6),
                    "p_positive": round(float((fwd > 0).mean()), 4)},
        "uncertainty": "distribution over analogues; the mean is not a forecast",
    }
    if x_now is not None and x_hist is not None:
        diff = np.abs(x_hist[idx].mean(axis=0) - x_now)
        order = np.argsort(diff)
        names = feature_names or [f"f{i}" for i in range(len(diff))]
        out["matched"] = [names[i] for i in order[:3]]
        out["differed"] = [names[i] for i in order[::-1][:3]]
    return out


# ----------------------------------------------------------------------------- windows
def windows_from_series(x: np.ndarray, window: int) -> np.ndarray:
    """(T, F) or (T,) series -> (T - window + 1, window, F) causal windows ending at each bar.

    Window i ends at bar i + window - 1, so `forward[i]` for a representation test must be the
    quantity realised AFTER that bar; the caller aligns it, this function only cuts.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    w = sliding_window_view(x, (window, x.shape[1]))[:, 0]
    return np.ascontiguousarray(w)


def _as_windows(w: np.ndarray) -> np.ndarray:
    """(N, L, F) or (N, L) -> (N, L, F); a 2-D input is read as one feature per bar."""
    w = np.asarray(w, dtype=float)
    return w[:, :, None] if w.ndim == 2 else w


class _Scaler:
    """Per-FEATURE moments pooled over bar positions, the same convention as `MarketEncoder`.

    Standardising per feature (not per bar position) keeps the window's shape intact: a bar that
    was large stays large relative to its neighbours, which is exactly what the encoders are
    meant to read. Standardising per position would erase it.
    """

    def __init__(self) -> None:
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None

    def fit(self, w3: np.ndarray) -> _Scaler:
        flat = w3.reshape(-1, w3.shape[2])
        self.mu = np.nanmean(flat, axis=0)
        sd = np.nanstd(flat, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        return self

    def flat(self, w3: np.ndarray) -> np.ndarray:
        assert self.mu is not None and self.sd is not None
        xs = np.nan_to_num((w3 - self.mu) / self.sd)
        out: np.ndarray = xs.reshape(w3.shape[0], -1)
        return out


class WindowPCA:
    """PCA over standardised windows: `MarketEncoder`'s objective on pre-cut windows.

    Exists so the contrastive encoder can be scored against PCA on IDENTICAL rows by
    `representation_gain`; `MarketEncoder` cuts its own windows from a series and cannot be fed
    the same matrix.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.scaler = _Scaler()
        self.centre: np.ndarray | None = None
        self.components: np.ndarray | None = None
        self.explained: np.ndarray | None = None

    def fit(self, windows: np.ndarray) -> WindowPCA:
        w3 = _as_windows(windows)
        flat = self.scaler.fit(w3).flat(w3)
        self.centre = flat.mean(axis=0)
        _u, s, vt = np.linalg.svd(flat - self.centre, full_matrices=False)
        k = int(min(self.dim, vt.shape[0]))
        self.components = vt[:k]
        var = s ** 2
        self.explained = var[:k] / max(float(var.sum()), 1e-12)
        return self

    def embed(self, windows: np.ndarray) -> np.ndarray:
        assert self.components is not None and self.centre is not None
        flat = self.scaler.flat(_as_windows(windows))
        out: np.ndarray = (flat - self.centre) @ self.components.T
        return out


def _unit(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = np.sqrt((h ** 2).sum(axis=1, keepdims=True))
    n = np.maximum(n, 1e-12)
    return h / n, n


def _infonce(v1: np.ndarray, v2: np.ndarray, w: np.ndarray,
             tau: float) -> tuple[float, np.ndarray]:
    """Symmetric InfoNCE on cosine similarity and its gradient with respect to W.

    Row i's positive is its own second view; every other row in the batch is a negative, both
    ways round. The gradient goes through the L2 normalisation, so the projection's scale is
    not a free win: only DIRECTION agreement counts.
    """
    b = v1.shape[0]
    z1, n1 = _unit(v1 @ w)
    z2, n2 = _unit(v2 @ w)
    s = z1 @ z2.T / tau
    s_max = s.max()
    rows = np.log(np.exp(s - s_max).sum(axis=1)) + s_max
    cols = np.log(np.exp(s - s_max).sum(axis=0)) + s_max
    diag = np.diag(s)
    loss = float(0.5 * (np.mean(rows - diag) + np.mean(cols - diag)))
    p = np.exp(s - rows[:, None])                       # softmax over j for each i
    q = np.exp(s - cols[None, :])                       # softmax over i for each j
    ds = (p + q - 2.0 * np.eye(b)) / (2.0 * b)
    dz1 = ds @ z2 / tau
    dz2 = ds.T @ z1 / tau
    dh1 = (dz1 - z1 * (dz1 * z1).sum(axis=1, keepdims=True)) / n1
    dh2 = (dz2 - z2 * (dz2 * z2).sum(axis=1, keepdims=True)) / n2
    grad: np.ndarray = v1.T @ dh1 + v2.T @ dh2
    return loss, grad


class ContrastiveEncoder:
    """A linear projection W (d x k) trained by InfoNCE over two augmented views of each window.

        z = normalise(W^T x),   views: x + jitter * eps,  then a random `mask_frac` of bars zeroed

    WHY THESE TWO AUGMENTATIONS: jitter says "a representation must not change when every bar is
    nudged by a fraction of its own scale" (tick noise, a stale print); masking says "it must not
    hinge on any one bar" (the spike, the gap). A direction that only a few loud bars carry is
    destroyed by masking; a direction the whole window carries survives it. PCA has no such
    preference and so is fooled by the loud bar, which owns the variance.

    WHY LINEAR AND SMALL: the projection is a matrix that can be printed; `steps` batches of
    `batch` windows with an Adam step each is a fraction of a second, and the encoder is refitted
    per fold by `representation_gain` so nothing leaks.
    """

    def __init__(self, dim: int = 8, tau: float = 0.1, steps: int = 300, lr: float = 0.03,
                 jitter: float = 0.3, mask_frac: float = 0.25, batch: int = 256,
                 seed: int = 0) -> None:
        self.dim = dim
        self.tau = max(float(tau), 1e-3)
        self.steps = steps
        self.lr = lr
        self.jitter = jitter
        self.mask_frac = mask_frac
        self.batch = batch
        self.seed = seed
        self.scaler = _Scaler()
        self.centre: np.ndarray | None = None
        self.w: np.ndarray | None = None
        self.shape: tuple[int, int] = (0, 0)               # (bars, features) of a window
        self.loss_path: list[float] = []
        self.alignment: float = float("nan")
        self.uniformity: float = float("nan")

    # ------------------------------------------------------------------ augmentations
    def augment(self, flat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """One view of standardised, centred, flattened windows: jitter then bar masking.

        Public so a test can ask the question the objective asks: are two views of one window
        nearer each other than a window is to a stranger?
        """
        bars, feats = self.shape
        v = flat + self.jitter * rng.standard_normal(flat.shape)
        keep = rng.random((flat.shape[0], bars, 1)) >= self.mask_frac
        out: np.ndarray = (v.reshape(flat.shape[0], bars, feats) * keep).reshape(flat.shape)
        return out

    def _prepare(self, windows: np.ndarray) -> np.ndarray:
        assert self.centre is not None
        flat: np.ndarray = self.scaler.flat(_as_windows(windows)) - self.centre
        return flat

    # ------------------------------------------------------------------------ training
    def fit(self, windows: np.ndarray) -> ContrastiveEncoder:
        w3 = _as_windows(windows)
        self.shape = (int(w3.shape[1]), int(w3.shape[2]))
        flat = self.scaler.fit(w3).flat(w3)
        self.centre = flat.mean(axis=0)
        x = flat - self.centre
        n, d = x.shape
        k = int(min(self.dim, d))
        rng = np.random.default_rng(self.seed)
        w = np.linalg.qr(rng.standard_normal((d, k)))[0]
        m = np.zeros_like(w)
        v = np.zeros_like(w)
        b1, b2, eps = 0.9, 0.999, 1e-8
        self.loss_path = []
        for t in range(1, self.steps + 1):
            idx = rng.choice(n, size=min(self.batch, n), replace=False)
            xb = x[idx]
            loss, grad = _infonce(self.augment(xb, rng), self.augment(xb, rng), w, self.tau)
            m = b1 * m + (1 - b1) * grad
            v = b2 * v + (1 - b2) * grad ** 2
            w = w - self.lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
            self.loss_path.append(loss)
        self.w = w
        # Wang & Isola's two reads of a contrastive representation, on the training windows:
        # alignment = mean cosine between two views of one window (1 is perfect);
        # uniformity = log mean exp(-2 |z_i - z_j|^2) over pairs (more negative = better spread).
        z1, _ = _unit(self.augment(x, rng) @ w)
        z2, _ = _unit(self.augment(x, rng) @ w)
        self.alignment = float(np.mean((z1 * z2).sum(axis=1)))
        sample = rng.choice(n, size=min(512, n), replace=False)
        zs, _ = _unit(x[sample] @ w)
        d2 = ((zs[:, None, :] - zs[None, :, :]) ** 2).sum(axis=2)
        off = ~np.eye(zs.shape[0], dtype=bool)
        self.uniformity = float(np.log(np.mean(np.exp(-2.0 * d2[off]))))
        return self

    # ------------------------------------------------------------------------- reading
    def embed(self, windows: np.ndarray, normalise: bool = True) -> np.ndarray:
        """z for each window; unit-norm by default because that is what the objective trained."""
        assert self.w is not None, "fit first"
        h = self._prepare(windows) @ self.w
        if not normalise:
            return np.asarray(h, dtype=float)
        z, _ = _unit(h)
        return np.asarray(z, dtype=float)

    def nn_forward_stats(self, z_query: np.ndarray, z_hist: np.ndarray, forward: np.ndarray,
                         k: int = 20, **kw: Any) -> dict[str, Any]:
        """The case method on this embedding: `analogues` of the query among the history."""
        return analogues(np.asarray(z_query, dtype=float), np.asarray(z_hist, dtype=float),
                         np.asarray(forward, dtype=float), k=k, **kw)


# --------------------------------------------------------------------------- admission
def _ridge_fit(x: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = xb.T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, xb.T @ y)
    return out


def _oos_score(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray, yte: np.ndarray,
               lam: float, score: str) -> float:
    """Ridge on train-standardised inputs; R^2 (about the TRAIN mean) or sign log-score gain."""
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    a, b = (xtr - mu) / sd, (xte - mu) / sd
    if score == "sign":
        s_tr = np.where(ytr > 0, 1.0, -1.0)
        s_te = np.where(yte > 0, 1.0, -1.0)
        beta = _ridge_fit(a, s_tr, lam)
        raw = np.column_stack([np.ones(b.shape[0]), b]) @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(4.0 * raw, -50.0, 50.0)))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        p0 = float(np.clip((s_tr > 0).mean(), 1e-6, 1 - 1e-6))
        hit = s_te > 0
        ls = np.mean(np.where(hit, np.log(p), np.log(1 - p)))
        base = np.mean(np.where(hit, np.log(p0), np.log(1 - p0)))
        return float(ls - base)
    beta = _ridge_fit(a, ytr, lam)
    pred = np.column_stack([np.ones(b.shape[0]), b]) @ beta
    sse = float(np.sum((yte - pred) ** 2))
    sst = float(np.sum((yte - ytr.mean()) ** 2))
    return float(1.0 - sse / sst) if sst > 0 else 0.0


def representation_gain(windows: np.ndarray, forward: np.ndarray, *, encoder: Any = None,
                        raw_bars: int = 1, n_folds: int = 4, lam: float = 1.0,
                        score: str = "r2") -> dict[str, Any]:
    """Does the embedding forecast `forward` better than the raw last bars it was cut from?

    Walk-forward with expanding folds: on each fold the encoder is refitted on the train windows
    only (a fresh copy, so no fold sees a later one), a ridge is fitted on its embedding and
    another on the last `raw_bars` bars of the window, and both are scored out of sample --
    R^2 about the train mean by default, or the sign log-score gain over the base rate with
    `score="sign"`. The gain is the difference. A representation is ADMITTED only when the gain
    is positive AND the embedding's own score is positive: beating a useless baseline by being
    less useless is not admission.
    """
    w3 = _as_windows(windows)
    y = np.asarray(forward, dtype=float)
    n = w3.shape[0]
    assert y.shape[0] == n, "one forward value per window"
    enc = encoder if encoder is not None else ContrastiveEncoder()
    edges = np.linspace(n // 2, n, n_folds + 1).astype(int)
    per_fold: list[dict[str, float]] = []
    for i in range(n_folds):
        a, b = int(edges[i]), int(edges[i + 1])
        if b - a < 10 or a < 20:
            continue
        e = copy.deepcopy(enc).fit(w3[:a])
        ztr, zte = e.embed(w3[:a]), e.embed(w3[a:b])
        raw_tr = w3[:a, -raw_bars:, :].reshape(a, -1)
        raw_te = w3[a:b, -raw_bars:, :].reshape(b - a, -1)
        per_fold.append({"embedding": _oos_score(ztr, y[:a], zte, y[a:b], lam, score),
                         "raw": _oos_score(raw_tr, y[:a], raw_te, y[a:b], lam, score)})
    if not per_fold:
        return {"n": n, "folds": 0, "verdict": "UNMEASURED", "why": "too few windows"}
    emb = float(np.mean([f["embedding"] for f in per_fold]))
    raw = float(np.mean([f["raw"] for f in per_fold]))
    gain = emb - raw
    return {"n": n, "folds": len(per_fold), "score": score, "encoder": type(enc).__name__,
            "embedding": round(emb, 6), "raw": round(raw, 6), "gain": round(gain, 6),
            "per_fold": per_fold,
            "verdict": "ADMIT" if gain > 0 and emb > 0 else "REFUSE",
            "rule": "admit only when the embedding beats the raw last bars AND scores > 0"}
