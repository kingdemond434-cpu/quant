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
"""
from __future__ import annotations

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
