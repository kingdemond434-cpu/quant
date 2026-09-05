"""Predict the distribution shift, don't just detect it; adapt fast without forgetting slow.

DDG-DA (Microsoft): forecast p(D_{t+h} | D_{1:t}) -- the NEXT window's distribution -- rather
than classify the current one. Here the distribution is summarised by declared statistics per
window (volatility, breakout hit-rate, spread rank, correlation to the market driver, mean
range), and the forecast for the next window is a learned weighting of recent windows, fitted
by least squares on how well past windows predicted their successors. The hazard is how far the
forecast sits from the long-run baseline, in the baseline's own between-window units, so an
allocator can hear "the next week's volatility distribution is about to move" as a number.

DoubleAdapt: keep a SLOW model (ridge on the long history) and a FAST adapter (ridge on the
recent window, shrunk toward zero), and predict with theta_slow + delta_fast. The fast part is
refitted each step and can never wander far, so the machine responds to a changed market
without retraining from scratch on twenty recent bars.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

STATS: tuple[str, ...] = ("vol", "range", "hit_rate", "spread_rank", "abs_ret")


def window_stats(df: pd.DataFrame, window: int = 24) -> pd.DataFrame:
    """One row of declared distribution statistics per non-overlapping window."""
    c = df["close"].astype(float)
    r = np.log(c).diff()
    rng = ((df["high"] - df["low"]) / c).astype(float)
    hi48 = df["high"].rolling(48, min_periods=48).max().shift(1)
    breakout = (df["high"] > hi48).astype(float)
    follow = (c.shift(-6) > c).astype(float)
    hit = (breakout * follow).where(breakout > 0)
    spread = (df["spread"].astype(float) if "spread" in df.columns
              else pd.Series(np.nan, index=df.index))
    sp_rank = spread.rolling(240, min_periods=60).rank(pct=True)
    g = np.arange(len(df)) // window
    out = pd.DataFrame({
        "vol": r.groupby(g).std(), "range": rng.groupby(g).mean(),
        "hit_rate": hit.groupby(g).mean(), "spread_rank": sp_rank.groupby(g).mean(),
        "abs_ret": r.abs().groupby(g).mean(),
    })
    return out.iloc[:-1] if len(df) % window else out


def forecast_next(stats: pd.DataFrame, lags: int = 6) -> dict[str, Any]:
    """Learned lag weights per statistic; forecast for the next window and its hazard."""
    out: dict[str, Any] = {"per_stat": {}, "hazard": {}}
    if len(stats) < 4 * lags:
        return {**out, "why": f"need {4 * lags} windows"}
    z_all = []
    for col in STATS:
        s = stats[col].to_numpy(dtype=float)
        s = np.where(np.isfinite(s), s, np.nan)
        if np.isnan(s).mean() > 0.5:
            continue
        s = pd.Series(s).ffill().bfill().to_numpy()
        x = np.column_stack([s[lags - k - 1: len(s) - k - 1] for k in range(lags)])
        y = s[lags:]
        w = np.linalg.lstsq(np.column_stack([np.ones(x.shape[0]), x]), y, rcond=None)[0]
        pred_hist = np.column_stack([np.ones(x.shape[0]), x]) @ w
        resid_sd = float(np.std(y - pred_hist, ddof=1)) if y.size > 2 else float("nan")
        x_now = np.r_[1.0, s[::-1][:lags]]
        f = float(x_now @ w)
        base_mu, base_sd = float(np.mean(s)), float(np.std(s, ddof=1))
        z = (f - base_mu) / base_sd if base_sd > 0 else 0.0
        z_all.append(abs(z))
        out["per_stat"][col] = {"forecast": round(f, 6), "baseline": round(base_mu, 6),
                                "z": round(z, 3), "resid_sd": round(resid_sd, 6),
                                "weights": [round(float(v), 4) for v in w[1:]]}
        out["hazard"][col] = round(abs(z), 3)
    out["hazard_max"] = round(max(z_all), 3) if z_all else None
    out["verdict"] = ("DRIFT_AHEAD" if z_all and max(z_all) > 2.0 else
                      ("WATCH" if z_all and max(z_all) > 1.0 else "STABLE"))
    return out


class SlowFast:
    """theta_slow on the long history, delta_fast shrunk toward zero on the recent window."""

    def __init__(self, lam_slow: float = 10.0, lam_fast: float = 50.0, recent: int = 120) -> None:
        self.lam_slow, self.lam_fast, self.recent = lam_slow, lam_fast, recent
        self.slow: np.ndarray | None = None
        self.fast: np.ndarray | None = None

    @staticmethod
    def _ridge(x: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
        xb = np.column_stack([np.ones(x.shape[0]), x])
        a = xb.T @ xb + lam * np.eye(xb.shape[1])
        a[0, 0] -= lam
        return np.linalg.solve(a, xb.T @ y)

    def fit(self, x: np.ndarray, y: np.ndarray) -> SlowFast:
        self.slow = self._ridge(x, y, self.lam_slow)
        self.adapt(x[-self.recent:], y[-self.recent:])
        return self

    def adapt(self, x_recent: np.ndarray, y_recent: np.ndarray) -> SlowFast:
        assert self.slow is not None
        xb = np.column_stack([np.ones(x_recent.shape[0]), x_recent])
        resid = y_recent - xb @ self.slow
        self.fast = self._ridge(x_recent, resid, self.lam_fast)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        assert self.slow is not None and self.fast is not None
        xb = np.column_stack([np.ones(x.shape[0]), x])
        out: np.ndarray = xb @ (self.slow + self.fast)
        return out

    def adaptation_size(self) -> float:
        assert self.slow is not None and self.fast is not None
        denom = max(float(np.linalg.norm(self.slow[1:])), 1e-12)
        return float(np.linalg.norm(self.fast[1:])) / denom
