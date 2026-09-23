"""alpha_habitat: MARKET_TRACTABILITY / ALPHA_HABITAT engine.

Rolling statistical fingerprint per instrument (session-conditioned) so research
compute is allocated by mechanism-market compatibility, not by assumption.

Metrics (H1, per symbol, where meaningful also per session):
  SPREAD_R, SLIPPAGE_R, RETURN_SKEW, EXCESS_KURTOSIS, TAIL_INDEX,
  JUMP_FREQUENCY, RETURN_AUTOCORR, ABS_RETURN_AUTOCORR, VOL_CLUSTERING,
  HURST, TREND_PERSISTENCE, MEAN_REVERSION_STRENGTH, BREAKOUT_FOLLOW_THROUGH,
  FALSE_BREAKOUT_RATE, SESSION_SEASONALITY, RANGE_STABILITY, COST_TO_MOVE_RATIO,
  NEWS_JUMP_SENSITIVITY

Also emits a PAIR x MECHANISM affinity matrix built from the real hunt evidence
(hunt12 session-range-breakout, hunt16 Davidd families) using OOS walk-forward
expectancy, plus a habitat search: winning market -> fingerprint -> nearest
habitat neighbors (EURUSD etc. act as baseline/control environments).

CLUSTER/COMPUTE ONLY ON PAST X (features), never future P&L.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
REPORTS = BASE / "reports"
SESSIONS = {"asia": (0, 6), "london_am": (7, 12), "ny_open": (13, 15), "afternoon": (16, 23)}


def _skew(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) < 50:
        return float("nan")
    m = x.mean()
    sd = x.std(ddof=1)
    if sd <= 0:
        return float("nan")
    return float(((x - m) ** 3).mean() / sd ** 3)


def _kurt(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) < 50:
        return float("nan")
    m = x.mean()
    sd = x.std(ddof=1)
    if sd <= 0:
        return float("nan")
    return float(((x - m) ** 4).mean() / sd ** 4 - 3.0)


def _hurst(rs: np.ndarray) -> float:
    rs = rs[np.isfinite(rs)]
    if len(rs) < 256:
        return float("nan")
    n = len(rs)
    lags = [n // 32, n // 16, n // 8, n // 4]
    rs_log = []
    for lag in lags:
        chunks = len(rs) // lag
        if chunks < 4:
            continue
        seg = rs[: chunks * lag].reshape(chunks, lag)
        mean = seg.mean(axis=1, keepdims=True)
        dev = np.cumsum(seg - mean, axis=1)
        rng = dev.max(axis=1) - dev.min(axis=1)
        std = seg.std(axis=1, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rr = rng / np.where(std > 0, std, np.nan)
        rr = rr[np.isfinite(rr)]
        if len(rr):
            rs_log.append((np.log(lag), np.log(rr.mean())))
    if len(rs_log) < 3:
        return float("nan")
    xs, ys = zip(*rs_log)
    return float(np.polyfit(xs, ys, 1)[0])


def fingerprint(h1: pd.DataFrame, costs_pts: float, tick: float, contract: float) -> dict:
    o = h1["open"].to_numpy(float)
    h = h1["high"].to_numpy(float)
    l = h1["low"].to_numpy(float)
    c = h1["close"].to_numpy(float)
    mid = (h + l) / 2
    r = np.diff(np.log(c))
    hl = (h - l) / np.where(mid > 0, mid, 1.0)
    ar = np.abs(r)
    atr = np.convolve(hl, np.ones(24) / 24, mode="same")
    atr = np.maximum(atr, 1e-9)
    spread_r = costs_pts * tick / np.median(atr * mid)
    slippage_r = costs_pts * tick * 0.5 / np.median(atr * mid)
    j = len(r) - len(np.isfinite(r))
    jb = (ar / np.where(ar.std() > 0, ar.std(), 1.0)) > 4.0
    jump_freq = float(jb.mean())
    ret_ac = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 10 else float("nan")
    abs_ac = float(np.corrcoef(ar[:-1], ar[1:])[0, 1]) if len(r) > 10 else float("nan")
    vol_clust = float(np.corrcoef(ar[1:-1], ar[2:])[0, 1]) if len(r) > 10 else float("nan")
    h1_close = pd.Series(c, index=h1.index)
    daily = h1_close.resample("D").last()
    daily_r = np.log(daily).diff().to_numpy()
    daily_r = daily_r[np.isfinite(daily_r)]
    hurst = _hurst(daily_r)
    sign = np.sign(r)
    runs = np.diff(np.concatenate([[0], sign]))
    run_len = np.diff(np.where(runs != 0)[0])
    trend_pers = float(run_len.mean()) if len(run_len) else float("nan")
    pac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 10 else float("nan")
    meanrev = float(-pac1) if pac1 == pac1 else float("nan")
    n_break, cont, failed = 0, 0, 0
    window = 24
    roll_hi = pd.Series(h).rolling(window).max().shift(1).to_numpy()
    roll_lo = pd.Series(l).rolling(window).min().shift(1).to_numpy()
    for i in range(window + 1, len(r) - 24):
        if c[i] > roll_hi[i]:
            n_break += 1
            if c[i + 12] > roll_hi[i]:
                cont += 1
            if l[i + 1:i + 13].min() < roll_hi[i]:
                failed += 1
    follow = float(cont / n_break) if n_break else float("nan")
    false_br = float(failed / n_break) if n_break else float("nan")
    hours = h1.index.hour if isinstance(h1.index, pd.DatetimeIndex) else None
    sess_means = {}
    for sname, (a, b) in SESSIONS.items():
        if hours is None:
            continue
        m = np.isin(hours[1:], range(a, b + 1))
        sl = ar[m]
        sess_means[sname] = float(sl.mean()) if len(sl) else 0.0
    tot = sum(sess_means.values()) or 1e-9
    conc = float(sum((v / tot) ** 2 for v in sess_means.values())) if sess_means else float("nan")
    d_hi = pd.Series(h, index=h1.index).resample("D").max().to_numpy()
    d_lo = pd.Series(l, index=h1.index).resample("D").min().to_numpy()
    d_c = pd.Series(c, index=h1.index).resample("D").last().to_numpy()
    d_rng = (d_hi - d_lo) / np.where(d_c > 0, d_c, 1.0)
    d_rng = d_rng[np.isfinite(d_rng)]
    range_stab = float(d_rng.std() / np.where(d_rng.mean() > 0, d_rng.mean(), 1.0)) if len(d_rng) else float("nan")
    cost_move = float((costs_pts * tick) / np.median(atr * mid))
    post_jump = float(ar[np.where(jb)[0] + 1].mean()) if jb.any() and np.any(jb[:-1]) else float("nan")
    news_jump = float(post_jump / (ar.mean() + 1e-9))
    return dict(
        spread_r=round(spread_r, 6), slippage_r=round(slippage_r, 6),
        return_skew=round(_skew(r), 4), excess_kurtosis=round(_kurt(r), 3),
        tail_index=round(float(np.quantile(ar, 0.995) / np.quantile(ar, 0.95)), 3),
        jump_frequency=round(jump_freq, 5),
        return_autocorr=round(ret_ac, 4), abs_return_autocorr=round(abs_ac, 4),
        vol_clustering=round(vol_clust, 4), hurst=round(hurst, 3),
        trend_persistence=round(trend_pers, 3), mean_reversion_strength=round(meanrev, 4),
        breakout_follow_through=round(follow, 4), false_breakout_rate=round(false_br, 4),
        session_seasonality=round(conc, 3), range_stability=round(range_stab, 3),
        cost_to_move_ratio=round(cost_move, 5), news_jump_sensitivity=round(news_jump, 3),
    )


def affinity(hunt_files: list[str]) -> dict:
    rows = []
    for f in hunt_files:
        p = REPORTS / f
        if not p.exists():
            continue
        data = json.loads(p.read_text("utf-8"))
        for r in data.get("all", []):
            wf = np.array(r.get("wf", []), dtype=float)
            oos = float(np.nanmean(wf)) if len(wf) else float("nan")
            fam = "SESSION_RANGE_BREAKOUT" if "hunt12" in f else r.get("fam", "?")
            rows.append(dict(sym=r["sym"], fam=fam, exp=r.get("exp", 0.0),
                             t=r.get("t", 0.0), oos=oos))
    mat: dict[str, dict] = {}
    for r in rows:
        mat.setdefault(r["sym"], {})
        key = r["fam"]
        prev = mat[r["sym"]].get(key)
        if prev is None or (r["oos"] == r["oos"] and (prev["oos"] != prev["oos"] or r["oos"] > prev["oos"])):
            mat[r["sym"]][key] = {"exp": round(r["exp"], 3), "t": round(r["t"], 2),
                                  "oos": None if r["oos"] != r["oos"] else round(r["oos"], 3)}
    return mat


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    fp = {}
    for sym, m in meta.items():
        h1p = UNI / f"{sym}_H1.parquet"
        if not h1p.exists():
            continue
        h1 = families._h1(pd.read_parquet(h1p))
        fp[sym] = fingerprint(h1, float(m.get("median_spread_pts", 10)),
                              float(m.get("tick_size", 1e-5)), float(m.get("contract_size", 1e5)))
    aff = affinity(["hunt12.json", "hunt16.json"])
    out = {
        "fingerprints": fp,
        "affinity_matrix": aff,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }
    (REPORTS / "market_fingerprints.json").write_text(json.dumps(out, indent=2, default=str),
                                                      encoding="utf-8")
    syms = sorted(fp)
    cols = sorted(next(iter(fp.values())))
    X = np.array([[fp[s][c] for c in cols] for s in syms], dtype=float)
    mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0)
    Z = (X - mu) / np.where(sd > 0, sd, 1.0)
    print(f"fingerprints for {len(syms)} symbols; affinity cells: "
          f"{sum(len(v) for v in aff.values())}", flush=True)
    winners = ["AUDCAD", "XAUUSD", "AUDJPY"]
    for w in winners:
        if w not in fp:
            continue
        i = syms.index(w)
        d = np.sqrt(np.nansum((Z - Z[i]) ** 2, axis=1))
        order = np.argsort(d)
        near = [f"{syms[k]} ({d[k]:.1f})" for k in order[1:6]]
        print(f"{w}: nearest habitats {near}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())