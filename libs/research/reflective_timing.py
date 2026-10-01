"""REFLECTIVE FACTOR TIMING -- regime analogues plus a memory of how those analogues did.

The IBK Securities 2026 design, in the desk's own terms. At each rebalance:

  1. ANALOGUES. Z-score today's regime vector against its own history (expanding, point-in-time)
     and take the K historical days nearest by Z-distance whose forward window has already closed.
  2. QUANT CALL. Each factor's mean forward return over those analogues is its predicted return;
     the book tilts from equal weight toward the factors the analogues favour.
  3. REFLECTION. Every past call is kept with its regime, its prediction and, once the window
     closes, its outcome. Before acting, the calls made in regimes most like today's are graded:
     the per-factor bias between what was predicted and what happened corrects today's
     prediction, and the cross-sectional skill of those calls scales how hard the book tilts.
     Analogues that kept being wrong in this kind of regime lose their voice here; ones that kept
     being right gain it. That accumulated, regime-specific learning is the whole innovation.
  4. SHORT NEWS CONTEXT (optional). An abnormal 3-day news intensity shrinks the tilt toward equal
     weight. The paper found 3 days helped and a month hurt, so the window is a parameter the
     contract measures rather than a belief.

Nothing here sizes a live book. It returns factor weights and a measured contract; wiring into
the allocator is a separate, gated change. Every configuration run is a trial and is counted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

TRADING_DAYS = 252


@dataclass(frozen=True)
class TimingConfig:
    k_analogs: int = 20
    horizon: int = 21            # rebalance period and forward window, in rows
    min_history: int = 252       # rows before the first decision
    tilt: float = 1.0            # tilt strength on the standardised prediction
    reflect: bool = True
    k_reflect: int = 12          # past decisions graded per rebalance
    reflect_prior: float = 6.0   # pseudo-decisions of shrinkage toward "no correction"
    news_window: int = 3
    news_z_cut: float = 1.5
    news_shrink: float = 0.5
    cost_per_turnover: float = 1e-4


@dataclass
class Decision:
    t: int
    z: np.ndarray
    pred: np.ndarray             # quant prediction before reflection
    outcome: np.ndarray | None = None


@dataclass
class TimingResult:
    weights: np.ndarray          # (T, K), row d = weights held over day d
    returns: np.ndarray          # (T,) net portfolio returns, NaN before the first decision
    decisions: list[Decision] = field(default_factory=list)
    multipliers: list[float] = field(default_factory=list)


def zscore_pit(states: np.ndarray, min_obs: int = 20) -> np.ndarray:
    """Expanding z-score: row t uses rows 0..t only. NaN until `min_obs` rows exist."""
    x = np.asarray(states, dtype=float)
    out = np.full_like(x, np.nan)
    csum = np.nancumsum(x, axis=0)
    csq = np.nancumsum(x * x, axis=0)
    cnt = np.cumsum(~np.isnan(x), axis=0).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = csum / cnt
        var = csq / cnt - mu * mu
        sd = np.sqrt(np.maximum(var, 0.0))
        z = (x - mu) / sd
    ok = (cnt >= min_obs) & (sd > 1e-12)
    out[ok] = z[ok]
    return out


def forward_sums(factors: np.ndarray, horizon: int) -> np.ndarray:
    """Y[s] = sum of factor returns over s+1..s+horizon; NaN where the window runs off the end."""
    f = np.nan_to_num(np.asarray(factors, dtype=float))
    t, k = f.shape
    c = np.vstack([np.zeros((1, k)), np.cumsum(f, axis=0)])
    y = np.full((t, k), np.nan)
    n = t - horizon
    if n > 0:
        y[:n] = c[horizon + 1:t + 1] - c[1:n + 1]
    return y


def _nearest(z_now: np.ndarray, z_hist: np.ndarray, k: int) -> np.ndarray:
    ok = ~np.isnan(z_hist).any(axis=1)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return idx
    d = np.sqrt(np.mean((z_hist[idx] - z_now) ** 2, axis=1))
    return idx[np.argsort(d, kind="stable")[:k]]


def _weights_from_pred(pred: np.ndarray, scale: np.ndarray, tilt: float,
                       mult: float) -> np.ndarray:
    k = pred.size
    s = np.clip(tilt * mult * pred / np.maximum(scale, 1e-12), -1.0, 1.0)
    w = (1.0 + s) / k
    tot = w.sum()
    return w / tot if tot > 0 else np.full(k, 1.0 / k)


def _reflect(z_now: np.ndarray, past: list[Decision], cfg: TimingConfig
             ) -> tuple[np.ndarray, float]:
    """Per-factor bias correction and a tilt multiplier from past calls in similar regimes."""
    graded = [d for d in past if d.outcome is not None]
    if not graded:
        return np.zeros_like(z_now[:0]), 1.0
    zs = np.vstack([d.z for d in graded])
    pick = _nearest(z_now, zs, cfg.k_reflect)
    if pick.size == 0:
        return np.zeros(0), 1.0
    preds = np.vstack([graded[i].pred for i in pick])
    outs = np.vstack([graded[i].outcome for i in pick])
    n = float(pick.size)
    shrink = n / (n + cfg.reflect_prior)
    bias = shrink * np.mean(outs - preds, axis=0)
    # Cross-sectional skill: did the analogues rank the factors the right way round?
    pc = preds - preds.mean(axis=1, keepdims=True)
    oc = outs - outs.mean(axis=1, keepdims=True)
    den = np.sqrt(np.sum(pc * pc) * np.sum(oc * oc))
    skill = float(np.sum(pc * oc) / den) if den > 1e-18 else 0.0
    mult = float(np.clip(1.0 + 2.0 * shrink * skill, 0.0, 2.0))
    return bias, mult


def run_timing(factors: np.ndarray, states: np.ndarray, cfg: TimingConfig | None = None,
               news: np.ndarray | None = None, *, method: str = "reflect") -> TimingResult:
    """Walk-forward timing. method: "equal" | "analog" | "reflect".

    `states[t]` must already be known at the close of row t (lag it before calling if needed).
    Weights decided at row t are held over rows t+1..t+horizon.
    """
    cfg = cfg or TimingConfig()
    f = np.asarray(factors, dtype=float)
    t_n, k = f.shape
    z = zscore_pit(states)
    y = forward_sums(f, cfg.horizon)
    news_z = zscore_pit(np.asarray(news, dtype=float).reshape(-1, 1))[:, 0] \
        if news is not None else None

    weights = np.full((t_n, k), np.nan)
    decisions: list[Decision] = []
    mults: list[float] = []
    ret = np.full(t_n, np.nan)
    w_prev = np.full(k, 1.0 / k)
    for t in range(cfg.min_history, t_n - 1, cfg.horizon):
        for d in decisions:
            if d.outcome is None and d.t + cfg.horizon <= t:
                d.outcome = y[d.t].copy()
        if method == "equal" or np.isnan(z[t]).any():
            w = np.full(k, 1.0 / k)
        else:
            closed = t - cfg.horizon + 1          # s + horizon <= t  <=>  s < closed
            hist = y[:closed]
            idx = _nearest(z[t], z[:closed], cfg.k_analogs)
            idx = idx[~np.isnan(hist[idx]).any(axis=1)] if idx.size else idx
            if idx.size < max(3, cfg.k_analogs // 2):
                w = np.full(k, 1.0 / k)
            else:
                pred = hist[idx].mean(axis=0)
                scale = np.nanstd(hist, axis=0)
                mult = 1.0
                adj = pred
                if method == "reflect" and cfg.reflect:
                    bias, mult = _reflect(z[t], decisions, cfg)
                    if bias.size == k:
                        adj = pred + bias
                if news_z is not None:
                    lo = max(0, t - cfg.news_window + 1)
                    window = news_z[lo:t + 1]
                    if window.size and np.nanmean(np.abs(window)) > cfg.news_z_cut:
                        mult *= cfg.news_shrink
                w = _weights_from_pred(adj, scale, cfg.tilt, mult)
                decisions.append(Decision(t=t, z=z[t].copy(), pred=pred.copy()))
                mults.append(mult)
        end = min(t + cfg.horizon, t_n - 1)
        weights[t + 1:end + 1] = w
        # turnover cost is charged on the first held day
        weights_cost = cfg.cost_per_turnover * float(np.abs(w - w_prev).sum())
        w_prev = w
        f_slice = np.nan_to_num(f[t + 1:end + 1])
        if f_slice.size:
            r = f_slice @ w
            r[0] -= weights_cost
            ret[t + 1:end + 1] = r
    return TimingResult(weights=weights, returns=ret, decisions=decisions, multipliers=mults)


def metrics(returns: np.ndarray) -> dict[str, Any]:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 20:
        return {"status": "UNMEASURED", "n": int(r.size)}
    sd = r.std(ddof=1)
    logr = np.log1p(np.clip(r, -0.99, None))
    eq = np.cumsum(logr)
    dd = float(np.max(np.maximum.accumulate(eq) - eq))
    return {
        "n": int(r.size),
        "ann_return": float(r.mean() * TRADING_DAYS),
        "ann_vol": float(sd * np.sqrt(TRADING_DAYS)),
        "sharpe": float(r.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else 0.0,
        "elog_ann": float(logr.mean() * TRADING_DAYS),
        "max_dd_log": dd,
    }


def block_bootstrap_diff(a: np.ndarray, b: np.ndarray, *, n_boot: int = 2000, block: int = 21,
                         seed: int = 7) -> dict[str, float]:
    """Stationary-block bootstrap of the annualised Sharpe difference a - b on common days."""
    m = ~(np.isnan(a) | np.isnan(b))
    a, b = a[m], b[m]
    n = a.size
    if n < 3 * block:
        return {"status": float("nan")}
    rng = np.random.default_rng(seed)

    def sh(x: np.ndarray) -> float:
        s = x.std(ddof=1)
        return float(x.mean() / s * np.sqrt(TRADING_DAYS)) if s > 0 else 0.0

    obs = sh(a) - sh(b)
    diffs = np.empty(n_boot)
    nb = int(np.ceil(n / block))
    for i in range(n_boot):
        starts = rng.integers(0, n - block, size=nb)
        ix = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        diffs[i] = sh(a[ix]) - sh(b[ix])
    return {
        "sharpe_diff": obs,
        "ci_lo": float(np.quantile(diffs, 0.05)),
        "ci_hi": float(np.quantile(diffs, 0.95)),
        "p_le_zero": float(np.mean(diffs <= 0.0)),
    }
