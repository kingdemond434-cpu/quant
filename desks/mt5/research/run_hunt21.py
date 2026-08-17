"""Hunt #21: CROSS-MARKET RESIDUAL DESK (docs/NEWS_LINEAGE.md class 5/7/8).

Predict what an asset SHOULD do given the state of related markets, trade the
divergence. All factors from our own 22-symbol H1 universe (no external series
invented). H4 resolution.

Direction cells (standard FAMILIES, rebuilt by universal_gate):
  cmr_xau_factor_resid  XAUUSD vs factor model (EURUSD, USDCAD, AUDJPY, BTCUSD,
                        XAGUSD) rolling-OLS on H4 log returns, window 120:
                        residual z < -2 -> LONG (gold underperformed its model)
                        z > +2 -> SHORT (expect reversion)
  cmr_xau_factor_lag    composite predicted move; when |predicted| large but XAU
                        moved < 30% of it -> enter in the factor direction
                        (leader -> laggard propagation)
  cmr_tri_resid         triangular consistency: EURGBP vs EURUSD-GBPUSD legs
                        (same pattern for AUDNZD, AUDCAD, NZDCAD, EURCHF, GBPJPY)
                        residual z-score mean reversion both sides

Pair cells via UNIVERSAL_CELLS: one cell per triangle (both sides in one cell's
z-signals; daily R per side recorded separately as two cells in the report).

SURVIVOR CLAIMS: universal_gate.py 10-gate pass ONLY. Battery stats are
descriptive only. Marker reports/DONE_hunt21.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402
from run_hunt17 import _atr, resample  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
ATR_K = 1.2
W = 120
Z_THR = 2.0

XAU_FACTORS = ["EURUSD", "USDCAD", "AUDJPY", "BTCUSD", "XAGUSD"]
TRIANGLES = [  # (traded pair, [(leg sym, sign in log-return identity), ...])
    ("EURGBP", [("EURUSD", 1.0), ("GBPUSD", -1.0)]),
    ("AUDNZD", [("AUDUSD", 1.0), ("NZDUSD", -1.0)]),
    ("AUDCAD", [("AUDJPY", 1.0), ("CADJPY", -1.0)]),
    ("NZDCAD", [("NZDJPY", 1.0), ("CADJPY", -1.0)]),
    ("EURCHF", [("EURUSD", 1.0), ("USDCHF", 1.0)]),
    ("GBPJPY", [("GBPUSD", 1.0), ("USDJPY", 1.0)]),
]


def _sig(t, side, ref, atr_v, rr=1.5, ttl=8, tag="", trigger=None, wait_bars=2):
    risk = atr_v * ATR_K
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=t, side=side, stop=ref - side * risk,
                  target=ref + side * risk * rr, ttl_bars=ttl, tag=tag,
                  trigger=trigger, wait_bars=wait_bars)


def _load(sym: str) -> pd.DataFrame:
    return families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))


def _aligned_log_returns(sym: str, index: pd.DatetimeIndex) -> np.ndarray:
    h4, _ = resample(_load(sym))
    h4 = h4.reindex(index)
    c = np.log(h4["close"].to_numpy(float))
    r = np.full(len(c), np.nan)
    r[1:] = np.diff(c)
    return r


def _rolling_ols(y: np.ndarray, X: np.ndarray, w: int):
    """Per-bar rolling OLS of y on X (with intercept). Returns beta (n x k),
    intercept, fitted, residual, and in-sample residual z over the window."""
    n = len(y)
    k = X.shape[1]
    beta = np.full((n, k), np.nan)
    alpha = np.full(n, np.nan)
    fitted = np.full(n, np.nan)
    resid = np.full(n, np.nan)
    z = np.full(n, np.nan)
    X1 = np.column_stack([np.ones(len(y)), X])
    for i in range(w, n):
        seg = slice(i - w, i)
        Xw = X1[seg]
        yw = y[seg]
        if not (np.isfinite(Xw).all() and np.isfinite(yw).all()):
            continue
        b, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        alpha[i] = b[0]
        beta[i] = b[1:]
        f = Xw @ b
        e = yw - f
        sd = e.std(ddof=1)
        if sd > 0:
            fitted[i] = X1[i] @ b
            resid[i] = y[i] - fitted[i]
            z[i] = resid[i] / sd
    return beta, alpha, fitted, resid, z


def fam_cmr_xau_factor_resid(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                             w: int = W, z_thr: float = Z_THR, rr: float = 1.5,
                             ttl: int = 8) -> list[Signal]:
    idx = h4.index
    y = _aligned_log_returns("XAUUSD", idx)
    X = np.column_stack([_aligned_log_returns(f, idx) for f in XAU_FACTORS])
    _, _, _, _, z = _rolling_ols(y, X, w)
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    out = []
    for i in range(w + 1, len(h4) - 1):
        if not np.isfinite(z[i]):
            continue
        if side > 0 and z[i] < -z_thr:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "cmr_xau_factor_resid"))
            except ValueError:
                pass
        if side < 0 and z[i] > z_thr:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "cmr_xau_factor_resid"))
            except ValueError:
                pass
    return out


def fam_cmr_xau_factor_lag(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                           w: int = W, lag_k: float = 1.5, rr: float = 1.5,
                           ttl: int = 8) -> list[Signal]:
    """Leader->laggard: factor model predicts a big XAU move; XAU has NOT moved
    (residual near zero); enter in the predicted direction."""
    idx = h4.index
    y = _aligned_log_returns("XAUUSD", idx)
    X = np.column_stack([_aligned_log_returns(f, idx) for f in XAU_FACTORS])
    beta, alpha, fitted, resid, z = _rolling_ols(y, X, w)
    pred_sd = np.full(len(y), np.nan)
    for i in range(w, len(y)):
        if np.isfinite(fitted[i]):
            seg = fitted[i - w: i]
            pred_sd[i] = seg.std(ddof=1) if len(seg) > 1 else np.nan
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    out = []
    for i in range(w + 1, len(h4) - 1):
        p, ps, rz, ay = fitted[i], pred_sd[i], z[i], y[i]
        if not (np.isfinite(p) and np.isfinite(ps) and np.isfinite(rz)
                and np.isfinite(ay) and ps > 0):
            continue
        lagged = abs(p) >= lag_k * ps and abs(ay) <= 0.3 * abs(p)
        if side > 0 and lagged and p > 0:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "cmr_xau_factor_lag"))
            except ValueError:
                pass
        if side < 0 and lagged and p < 0:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                "cmr_xau_factor_lag"))
            except ValueError:
                pass
    return out


def fam_cmr_tri_resid(h4: pd.DataFrame, d1: pd.DataFrame, side: int,
                      traded: str, legs: list, w: int = W, z_thr: float = Z_THR,
                      rr: float = 1.5, ttl: int = 8) -> list[Signal]:
    idx = h4.index
    y = _aligned_log_returns(traded, idx)
    leg_rets = [s * _aligned_log_returns(sym, idx) for sym, s in legs]
    pred = np.sum(leg_rets, axis=0)
    d = y - pred
    sd = pd.Series(d).rolling(w, min_periods=w // 2).std().to_numpy()
    z = d / np.where(sd > 0, sd, np.nan)
    a = _atr(h4, 14)
    c = h4["close"].to_numpy(float)
    out = []
    for i in range(w + 1, len(h4) - 1):
        if not np.isfinite(z[i]):
            continue
        if side > 0 and z[i] < -z_thr:
            try:
                out.append(_sig(h4.index[i], 1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                f"cmr_tri_{traded}"))
            except ValueError:
                pass
        if side < 0 and z[i] > z_thr:
            try:
                out.append(_sig(h4.index[i], -1, float(c[i]), float(a.iloc[i]), rr, ttl,
                                f"cmr_tri_{traded}"))
            except ValueError:
                pass
    return out


FAMILIES = {
    "cmr_xau_factor_resid": fam_cmr_xau_factor_resid,
    "cmr_xau_factor_lag": fam_cmr_xau_factor_lag,
}
SYMS = ["XAUUSD"]


def UNIVERSAL_CELLS(meta: dict):
    """Hook for universal_gate: one Cell per triangle per side."""
    import importlib
    f17 = importlib.import_module("run_hunt17")
    for traded, legs in TRIANGLES:
        h1 = _load(traded)
        h4, d1 = f17.resample(h1)
        for side in (1, -1):
            sigs = fam_cmr_tri_resid(h4, d1, side, traded, legs)
            m = meta.get(traded, {})
            costs = Costs(spread_per_lot=0.48 if traded == "XAUUSD" else max(
                m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5),
                0.05), commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
            from universal_gate import Cell
            yield Cell(f"{traded}.cmr_tri_resid.{'L' if side > 0 else 'S'}",
                       traded, h4, sigs, costs)


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    log = open(BASE / "logs" / "hunt21_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt21_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text("utf-8"))
            done, results = saved.get("done", []), list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'cell':<32} {'n':>5} {'exp':>7} {'t':>5} {'PF':>5} {'maxDD':>7}")
    h1 = _load("XAUUSD")
    h4, d1 = resample(h1)
    costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
    for fname, fn in FAMILIES.items():
        for side in (1, -1):
            tag = f"XAUUSD.{fname}.{'L' if side > 0 else 'S'}"
            if tag in done:
                continue
            sigs = fn(h4, d1, side)
            if len(sigs) < 60:
                done.append(tag)
                continue
            r = run_backtest(h4, sigs, costs).stats()
            tprint(f"{tag:<32} {r['n']:5d} {r['expectancy_r']:+7.3f} {r['t_stat']:5.2f} "
                   f"{r['profit_factor']:5.2f} {r['max_dd_r']:7.1f}")
            results.append(dict(sym="XAUUSD", fam=fname, side="LONG" if side > 0 else "SHORT",
                                n=r["n"], exp=r["expectancy_r"], t=r["t_stat"],
                                pf=r["profit_factor"], maxdd=r["max_dd_r"]))
            done.append(tag)
            partial.write_text(json.dumps({"done": done, "all": results}, indent=2),
                               encoding="utf-8")
    for traded, legs in TRIANGLES:
        th4, td1 = resample(_load(traded))
        for side in (1, -1):
            tag = f"{traded}.cmr_tri_resid.{'L' if side > 0 else 'S'}"
            if tag in done:
                continue
            sigs = fam_cmr_tri_resid(th4, td1, side, traded, legs)
            if len(sigs) < 60:
                done.append(tag)
                continue
            m = meta.get(traded, {})
            costs = Costs(spread_per_lot=0.48 if traded == "XAUUSD" else max(
                m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5),
                0.05), commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
            r = run_backtest(th4, sigs, costs).stats()
            tprint(f"{tag:<32} {r['n']:5d} {r['expectancy_r']:+7.3f} {r['t_stat']:5.2f} "
                   f"{r['profit_factor']:5.2f} {r['max_dd_r']:7.1f}")
            results.append(dict(sym=traded, fam="cmr_tri_resid",
                                side="LONG" if side > 0 else "SHORT",
                                n=r["n"], exp=r["expectancy_r"], t=r["t_stat"],
                                pf=r["profit_factor"], maxdd=r["max_dd_r"]))
            done.append(tag)
            partial.write_text(json.dumps({"done": done, "all": results}, indent=2),
                               encoding="utf-8")
    (BASE / "reports" / "hunt21.json").write_text(
        json.dumps({"survivors": [], "all": results,
                    "note": "SURVIVOR CLAIMS ONLY via universal_gate.py 10-gate pass",
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{len(results)} cells swept. Survivor claims pending universal 10-gate pass.")
    (BASE / "reports" / "DONE_hunt21").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()