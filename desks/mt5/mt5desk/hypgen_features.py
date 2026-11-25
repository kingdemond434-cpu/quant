"""Causal bar features shared by the model-based generated families (analog_knn, ranked_linear,
neural_policy). Every column at bar t reads only bars <= t (closed bars); nothing is fitted here.

The feature NAMES are the contract: a cell's params list the names it uses, so the gauntlet
rebuilds exactly the inputs the generator searched over.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, min_periods=n).mean()
    return 100.0 - 100.0 / (1.0 + up / dn.replace(0.0, np.nan))


def _z(x: pd.Series, n: int) -> pd.Series:
    m = x.rolling(n, min_periods=n).mean()
    s = x.rolling(n, min_periods=n).std()
    return (x - m) / s.replace(0.0, np.nan)


def _builders(d: pd.DataFrame) -> dict:
    c = d["close"].astype(float)
    lr = np.log(c).diff()
    vol = lr.rolling(100, min_periods=30).std()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - c.shift()).abs(),
                    (d["low"] - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=14).mean()
    v = d["tick_volume"] if "tick_volume" in d.columns else d.get("volume")
    hours = pd.Series(d.index.hour, index=d.index, dtype=float)
    out = {}
    for k in (1, 2, 4, 8, 24, 72):
        out[f"ret_{k}"] = lambda k=k: np.log(c).diff(k) / (vol * np.sqrt(k))
    for n in (20, 50, 200):
        out[f"z_{n}"] = lambda n=n: _z(c, n)
    out["rsi_14"] = lambda: (_rsi(c, 14) - 50.0) / 50.0
    out["rsi_2"] = lambda: (_rsi(c, 2) - 50.0) / 50.0
    out["atr_rank"] = lambda: atr.rolling(250, min_periods=50).rank(pct=True) - 0.5
    out["range_atr"] = lambda: (d["high"] - d["low"]) / atr.replace(0.0, np.nan)
    out["body"] = lambda: (c - d["open"]) / atr.replace(0.0, np.nan)
    out["vol_z"] = (lambda: _z(np.log1p(v.astype(float)), 50)) if v is not None \
        else (lambda: pd.Series(0.0, index=d.index))
    out["hour_sin"] = lambda: np.sin(2 * np.pi * hours / 24.0)
    out["hour_cos"] = lambda: np.cos(2 * np.pi * hours / 24.0)
    out["chan_pos"] = lambda: ((c - d["low"].rolling(50, min_periods=50).min())
                               / (d["high"].rolling(50, min_periods=50).max()
                                  - d["low"].rolling(50, min_periods=50).min()).replace(0.0, np.nan)
                               - 0.5)
    return out


FEATURES: tuple[str, ...] = ("ret_1", "ret_2", "ret_4", "ret_8", "ret_24", "ret_72", "z_20",
                             "z_50", "z_200", "rsi_14", "rsi_2", "atr_rank", "range_atr", "body",
                             "vol_z", "hour_sin", "hour_cos", "chan_pos")


def matrix(d: pd.DataFrame, names: list[str] | tuple[str, ...]) -> np.ndarray:
    """(n_bars, len(names)) float matrix, clipped to +-5, NaN where a feature is not yet formed."""
    b = _builders(d)
    cols = []
    for nm in names:
        f = b.get(str(nm))
        if f is None:
            raise KeyError(f"unknown feature {nm}")
        cols.append(pd.Series(f(), index=d.index).astype(float).to_numpy())
    x = np.column_stack(cols) if cols else np.zeros((len(d), 0))
    x[~np.isfinite(x)] = np.nan
    return np.clip(x, -5.0, 5.0)


def forward_log_return(d: pd.DataFrame, h: int) -> np.ndarray:
    """Next-open-to-open over h bars, the fill convention (signal at close t, fill at open t+1).
    Used ONLY as a label for bars whose label window has fully closed before the decision bar."""
    o = np.log(d["open"].astype(float).to_numpy())
    y = np.full(len(o), np.nan)
    if len(o) > h + 1:
        y[:-(h + 1)] = o[h + 1:] - o[1:-h]
    return y


def emit(d: pd.DataFrame, side: np.ndarray, *, stop_atr: float, rr: float, hold: int,
         atr_n: int = 14, tag: str, bank_frac: float = 0.0, runner_trail_k: float = 0.0) -> list:
    """Signals from a per-bar side array (-1/0/+1, stamped on the closing bar, filled next open),
    one position at a time, ATR stop / RR target / time stop. Shared by the generated families."""
    from mt5desk.engine import Signal
    from mt5desk.families import _atr
    if stop_atr <= 0 or rr <= 0 or hold < 1:
        return []
    atr = _atr(d, max(2, int(atr_n))).to_numpy(dtype=float)
    px = d["close"].to_numpy(dtype=float)
    idx = d.index
    sigs = []
    last_exit = -1
    for i in np.flatnonzero(np.asarray(side[:-1]) != 0):
        if i <= last_exit:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        s = int(np.sign(side[i]))
        e = px[i]
        sigs.append(Signal(time=idx[i], side=s, stop=e - s * stop_atr * a,
                           target=e + s * stop_atr * a * rr, ttl_bars=int(hold), tag=tag,
                           trigger=None, wait_bars=1, bank_frac=float(bank_frac),
                           runner_trail_k=float(runner_trail_k)))
        last_exit = i + int(hold)
    return sigs
