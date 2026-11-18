#!/usr/bin/env python3
"""SPILLOVER GRAPH: who transmits shocks to whom across the desk's asset classes, on desk bars.

    python desks/mt5/research/spillover_graph.py --once
    python desks/mt5/research/spillover_graph.py --once --force      # ignore the refresh window

WHY THIS EXISTS. `research/cross_asset_graph.py` measures PAIRWISE lead-lag on hourly bars --
does the driver's last-hour return carry information about the target's next hour -- and mints
the strong edges as `lead_lag` cells. What it does not measure is the SYSTEM: how much of each
instrument's forecast-error variance comes from shocks to the others, which instruments are net
TRANSMITTERS and which net RECEIVERS, and whether that connectedness is rising (the state in
which diversification fails). That is the connectedness table of Diebold and Yilmaz (2009, 2012,
"Better to give than to receive"), the standard spillover measure the CTA and macro shops read.
The build check of 2026-11-18 listed "cross-asset lead-lag and spillover graph" as not built.

WHAT IT COMPUTES, PER CHANNEL (daily log RETURNS, and daily Parkinson RANGE as the volatility
channel), on the desk's own H1 bars resampled to broker days:

    VAR(p) by OLS, p in 1..MAX_LAG chosen by BIC; generalized forecast-error variance
    decomposition at horizon H (Pesaran-Shin, so the table does not depend on variable order),
    rows normalised to 1:

        total     mean off-diagonal share -- the system's connectedness, 0..100
        to_i      shocks of i reaching the others (column sum off the diagonal)
        from_i    the others' shocks reaching i (row sum off the diagonal)
        net_i     to_i - from_i: a net TRANSMITTER is positive
        pair      net pairwise flow (theta_ji - theta_ij), the edges of the graph

    and the rolling TOTAL over the last ROLL_POINTS windows of ROLL_WINDOW days, so a reader
    sees whether connectedness is high now relative to its own history.

REPORT ONLY. Nothing here is a signal, a gate, a cap or a veto, and nothing reads it on the
money path; it is a measurement of the book's environment. Absent bars are named as absent
(L1.28a): a symbol with no H1 file is listed under `missing`, never zero-filled, and a channel
with too few common days reads UNMEASURED. Desk bars only: no external feed is read.

Clock: `hourly_cycle:spillover_graph` (core, layer `meta`). The table moves daily, so a pass
inside REFRESH_H of the last full computation over unchanged inputs stands down and says so.
Artifact: `desks/mt5/reports/SPILLOVER_GRAPH.json`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from functools import reduce
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = DESK / "data" / "universe"
OUT = DESK / "reports" / "SPILLOVER_GRAPH.json"
UNMEASURED = "UNMEASURED"

#: One or more instruments per asset class, so the table spans the book's classes rather than
#: twenty correlated equity names. Absent files are reported, not substituted.
ROSTER: dict[str, tuple[str, ...]] = {
    "indices": ("US500", "NAS100", "GER40", "UK100", "JPN225", "HK50", "AUS200"),
    "metals": ("XAUUSD", "XAGUSD", "XCUUSD"),
    "energy": ("XTIUSD", "XBRUSD", "XNGUSD"),
    "fx": ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF"),
    "bonds": ("UST10Y", "UKGILT"),
    "crypto": ("BTCUSD", "ETHUSD"),
}
#: Days of common history the full-sample table uses (the most recent ones).
SAMPLE_DAYS = 750
#: Fewest common days a table is computed on; fewer reads UNMEASURED.
MIN_DAYS = 250
MAX_LAG = 2
HORIZON = 10
ROLL_WINDOW = 250
ROLL_STEP = 21
ROLL_POINTS = 24
REFRESH_H = 20.0
TOP_PAIRS = 25


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------- the data ---
def _frame(symbol: str, universe_dir: Path) -> pd.DataFrame | None:
    path = universe_dir / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["open", "high", "low", "close"])
    except Exception:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        return None
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df if len(df) else None


def daily(df: pd.DataFrame) -> pd.DataFrame:
    """Broker-day bars from H1: the day's high, low and last close, keyed by the stamp's date.

    The stamps are broker time under a UTC label; a broker day is the desk's own trading day,
    so grouping on the stamp's date needs no conversion."""
    day = df.index.normalize()
    g = df.groupby(day)
    out = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
    out.index = pd.DatetimeIndex(out.index).tz_localize(None) if out.index.tz is not None \
        else pd.DatetimeIndex(out.index)
    return out


def common_calendar(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Each symbol's broker-day bars, restricted to the days EVERY listed symbol traded.

    The join comes BEFORE any differencing: a close diffed per symbol and joined afterwards can
    span two days for one symbol and one for another on the same row (a symbol missing a day
    contributes a two-day return beside everyone else's one-day return)."""
    dailies = {sym: daily(df) for sym, df in frames.items()}
    if not dailies:
        return {}
    days = reduce(lambda a, b: a.intersection(b),
                  (d.index for d in dailies.values())).sort_values()
    return {sym: d.loc[days] for sym, d in dailies.items()}


def coverage(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """How many broker days each symbol has against how many they ALL share, so a reader sees
    which symbol is shrinking the common calendar."""
    own = {sym: len(daily(df)) for sym, df in frames.items()}
    joined = common_calendar(frames)
    common = len(next(iter(joined.values()))) if joined else 0
    return {"common_days": common, "symbol_days": dict(sorted(own.items())),
            "common_share": {s: (round(common / n, 3) if n else None)
                             for s, n in sorted(own.items())}}


def channels(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Per channel, a (day x symbol) panel on the days EVERY listed symbol traded, every row
    the same interval for every symbol (joined first, differenced after)."""
    joined = common_calendar(frames)
    if not joined:
        return {}
    close = pd.DataFrame({s: d["close"].astype(float) for s, d in joined.items()})
    hi = pd.DataFrame({s: d["high"].astype(float) for s, d in joined.items()})
    lo = pd.DataFrame({s: d["low"].astype(float) for s, d in joined.items()})
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = np.log(close).diff()
        # Parkinson daily variance -> log volatility, the DY 2012 volatility channel
        pv = (np.log(hi / lo) ** 2) / (4.0 * math.log(2.0))
        vols = 0.5 * np.log(pv.where(pv > 0))
    out = {}
    for name, panel in (("returns", rets), ("volatility", vols)):
        out[name] = panel.replace([np.inf, -np.inf], np.nan).dropna()
    return out


# ------------------------------------------------------------------------------ the maths ---
def fit_var(x: np.ndarray, p: int) -> tuple[list[np.ndarray], np.ndarray, int]:
    """OLS VAR(p) with intercept: (coefficient matrices A_1..A_p, residual covariance, n_obs)."""
    t, k = x.shape
    y = x[p:]
    z = np.hstack([np.ones((t - p, 1))] + [x[p - i:t - i] for i in range(1, p + 1)])
    beta, *_ = np.linalg.lstsq(z, y, rcond=None)
    resid = y - z @ beta
    n = resid.shape[0]
    sigma = (resid.T @ resid) / max(n - z.shape[1], 1)
    coefs = [beta[1 + (i * k):1 + ((i + 1) * k)].T for i in range(p)]
    return coefs, sigma, n


def choose_lag(x: np.ndarray, max_lag: int = MAX_LAG) -> int:
    """BIC over 1..max_lag on a common estimation sample."""
    best, best_p = math.inf, 1
    k = x.shape[1]
    for p in range(1, max_lag + 1):
        xs = x[max_lag - p:]
        _c, sigma, n = fit_var(xs, p)
        sign, logdet = np.linalg.slogdet(sigma)
        if sign <= 0:
            continue
        bic = logdet + (math.log(n) / n) * p * k * k
        if bic < best:
            best, best_p = bic, p
    return best_p


def ma_coefficients(coefs: list[np.ndarray], horizon: int) -> list[np.ndarray]:
    """Moving-average matrices Psi_0..Psi_{H-1} of the VAR."""
    k = coefs[0].shape[0]
    psi = [np.eye(k)]
    for h in range(1, horizon):
        acc = np.zeros((k, k))
        for i, a in enumerate(coefs, start=1):
            if h - i >= 0:
                acc += a @ psi[h - i]
        psi.append(acc)
    return psi


def gfevd(coefs: list[np.ndarray], sigma: np.ndarray, horizon: int = HORIZON) -> np.ndarray:
    """Pesaran-Shin generalized FEVD, rows normalised to sum to 1. theta[i, j] is the share of
    i's H-step forecast-error variance due to shocks in j."""
    psi = ma_coefficients(coefs, horizon)
    k = sigma.shape[0]
    num = np.zeros((k, k))
    den = np.zeros(k)
    sd = np.sqrt(np.clip(np.diag(sigma), 1e-300, None))
    for p in psi:
        ps = p @ sigma
        num += (ps / sd[None, :]) ** 2
        den += np.einsum("ij,jk,ik->i", p, sigma, p)
    theta = num / den[:, None]
    return theta / theta.sum(axis=1, keepdims=True)


def connectedness(theta: np.ndarray, names: list[str]) -> dict[str, Any]:
    k = theta.shape[0]
    off = theta - np.diag(np.diag(theta))
    from_ = off.sum(axis=1)
    to = off.sum(axis=0)
    total = 100.0 * off.sum() / k
    pairs = []
    for i in range(k):
        for j in range(i + 1, k):
            flow = 100.0 * (theta[j, i] - theta[i, j])   # + : i transmits to j on net
            src, dst = (names[i], names[j]) if flow >= 0 else (names[j], names[i])
            pairs.append({"from": src, "to": dst, "net": round(abs(flow), 3),
                          "gross": round(100.0 * (theta[j, i] + theta[i, j]), 3)})
    pairs.sort(key=lambda r: -r["net"])
    nodes = {n: {"to": round(100.0 * float(to[i]), 3), "from": round(100.0 * float(from_[i]), 3),
                 "net": round(100.0 * float(to[i] - from_[i]), 3),
                 "own": round(100.0 * float(theta[i, i]), 3)} for i, n in enumerate(names)}
    return {"total": round(float(total), 3), "nodes": nodes, "pairs": pairs[:TOP_PAIRS],
            "transmitters": [n for n, v in sorted(nodes.items(), key=lambda kv: -kv[1]["net"])
                             if v["net"] > 0][:5],
            "receivers": [n for n, v in sorted(nodes.items(), key=lambda kv: kv[1]["net"])
                          if v["net"] < 0][:5]}


def table(panel: pd.DataFrame, *, horizon: int = HORIZON,
          sample_days: int = SAMPLE_DAYS) -> dict[str, Any]:
    """The connectedness table of one channel's panel, or UNMEASURED with the reason."""
    x = panel.tail(sample_days)
    if len(x) < MIN_DAYS or x.shape[1] < 2:
        return {"status": UNMEASURED,
                "why": f"{len(x)} common days across {x.shape[1]} symbols; need {MIN_DAYS} and 2"}
    arr = x.to_numpy(dtype=float)
    arr = (arr - arr.mean(axis=0)) / np.where(arr.std(axis=0) > 0, arr.std(axis=0), 1.0)
    p = choose_lag(arr)
    coefs, sigma, n = fit_var(arr, p)
    theta = gfevd(coefs, sigma, horizon)
    out = connectedness(theta, list(x.columns))
    out.update({"status": "MEASURED", "lag": p, "horizon": horizon, "days": int(n),
                "first_day": str(x.index[0].date()), "last_day": str(x.index[-1].date())})
    return out


def rolling_total(panel: pd.DataFrame, *, window: int = ROLL_WINDOW, step: int = ROLL_STEP,
                  points: int = ROLL_POINTS, horizon: int = HORIZON) -> list[dict[str, Any]]:
    """Total connectedness on trailing windows ending every `step` days, oldest first."""
    n = len(panel)
    if n < window:
        return []
    ends = list(range(n, window - 1, -step))[:points]
    out = []
    for end in sorted(ends):
        x = panel.iloc[end - window:end].to_numpy(dtype=float)
        sd = x.std(axis=0)
        if (sd <= 0).any():
            continue
        x = (x - x.mean(axis=0)) / sd
        coefs, sigma, _n = fit_var(x, 1)
        theta = gfevd(coefs, sigma, horizon)
        off = theta - np.diag(np.diag(theta))
        out.append({"day": str(panel.index[end - 1].date()),
                    "total": round(float(100.0 * off.sum() / theta.shape[0]), 3)})
    return out


# -------------------------------------------------------------------------------- the run ---
def _fingerprint(universe_dir: Path) -> dict[str, int]:
    fp = {}
    for syms in ROSTER.values():
        for s in syms:
            try:
                fp[s] = (universe_dir / f"{s}_H1.parquet").stat().st_mtime_ns
            except OSError:
                continue
    return fp


def _fresh(prev: Any, fp: dict[str, int]) -> bool:
    if not isinstance(prev, dict) or prev.get("inputs") != fp:
        return False
    try:
        at = datetime.fromisoformat(str(prev.get("computed_at")))
    except ValueError:
        return False
    return (datetime.now(tz=UTC) - at).total_seconds() < REFRESH_H * 3600.0


def run(*, universe_dir: Path = UNIVERSE_DIR, out: Path = OUT, force: bool = False
        ) -> dict[str, Any]:
    t0 = time.monotonic()
    fp = _fingerprint(universe_dir)
    try:
        prev = json.loads(out.read_text("utf-8"))
    except (OSError, ValueError):
        prev = None
    if not force and _fresh(prev, fp):
        doc = dict(prev)
        doc.update({"generated_at": _now(), "stood_down": True,
                    "why": f"inputs unchanged and last computed under {REFRESH_H:g}h ago"})
        return doc
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    klass: dict[str, str] = {}
    for k, syms in ROSTER.items():
        for s in syms:
            f = _frame(s, universe_dir)
            if f is None:
                missing.append(s)
                continue
            frames[s] = f
            klass[s] = k
    chans = channels(frames)
    result: dict[str, Any] = {}
    for name in ("returns", "volatility"):
        panel = chans.get(name)
        if panel is None or panel.empty:
            result[name] = {"status": UNMEASURED,
                            "why": f"no common days across {len(frames)} symbols"}
            continue
        tab = table(panel)
        if tab.get("status") == "MEASURED":
            tab["rolling_total"] = rolling_total(panel.tail(SAMPLE_DAYS + ROLL_WINDOW))
            roll = [r["total"] for r in tab["rolling_total"]]
            tab["total_percentile_vs_rolling"] = (
                round(float(np.mean([v <= roll[-1] for v in roll])), 3) if roll else None)
        result[name] = tab
    return {
        "generated_at": _now(), "computed_at": _now(), "stood_down": False,
        "leg": "spillover_graph", "method": (
            "Diebold-Yilmaz connectedness: OLS VAR(p<=%d, BIC) on standardised daily series, "
            "Pesaran-Shin generalized FEVD at horizon %d, rows normalised" % (MAX_LAG, HORIZON)),
        "channels": result, "symbols": sorted(frames), "asset_class": klass,
        "missing": sorted(missing), "inputs": fp, "coverage": coverage(frames),
        "source": "desk H1 bars (desks/mt5/data/universe/*_H1.parquet) only",
        "consumers": "report only: no signal, gate, cap or veto reads it",
        "wall_s": round(time.monotonic() - t0, 2)}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    os.replace(tmp, path)


def render(doc: dict[str, Any]) -> str:
    parts = []
    for name, tab in (doc.get("channels") or {}).items():
        if tab.get("status") == "MEASURED":
            parts.append(f"{name} total {tab['total']:.1f} (top transmitter "
                         f"{(tab.get('transmitters') or ['-'])[0]})")
        else:
            parts.append(f"{name} {UNMEASURED}")
    tail = " [stood down]" if doc.get("stood_down") else ""
    return (f"spillover_graph: {len(doc.get('symbols') or [])} symbols, "
            f"{len(doc.get('missing') or [])} missing; " + "; ".join(parts) + tail)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--force", action="store_true", help="recompute inside the refresh window")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run(out=a.out, force=a.force)
    _write(a.out, doc)
    print(render(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
