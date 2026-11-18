"""REGIME DISAGREEMENT -- several of our own regime systems read the same instrument, and the
disagreement between them is a feature family of its own.

WHY (ROMAN-0806, re-scoped 2026-11-11). The 10-06 directive asked for Markov, HMM, switching-vol,
Bayesian-filter and Kalman regimes side by side, plus an external API's "semantic regimes", and
said: "Disagreement between these regime systems becomes another feature family." The external
API was never wired and the principal dropped it on 11-11 ("replicated without it"), so every
vote here is a model this repository owns and can re-execute bit for bit.

THE SYSTEMS, each CAUSAL (a day's reading uses closes up to and including that day only):

    vol axis -- P(stress), in [0, 1]
      markov    control-room realised-vol percentile (simple classification, no fitted params)
      ewma      RiskMetrics EWMA vol (lambda 0.94), percentile against its own trailing year
      garch     GARCH(1,1) one-step forecast, parameters fitted only on PAST data at each
                yearly refit (variance targeting + grid MLE), percentile against its trailing year
      hmm       2-state Gaussian HMM on scaled returns, refit yearly on the trailing 3 years
                BEFORE the segment, forward-filtered: P(the high-variance state)

    trend axis -- P(up), in [0, 1]
      markov    control-room efficiency ratio x the sign of the 20-day move
      kalman    local-linear-trend Kalman filter: Phi(slope / sd(slope))
      tsmom     Phi(t-stat of the trailing 60-day mean return)
      hmm       the same HMM's filtered posterior over its states' 20-day drift sign

    transition axis
      bocpd     Bayesian online change-point (Adams & MacKay), Normal-Gamma on scaled returns:
                P(run length < 5 days)

THE DISAGREEMENT of an axis is the ensemble's mutual information, H(mean p) - mean H(p_i), in
bits: 0 when every system says the same thing (however confidently), largest when confident
systems contradict each other. That is the standard "epistemic" split of predictive entropy, so
uncertainty that every model shares is NOT counted as disagreement. Each axis's disagreement is
then ranked against its own trailing year, so "split" means split for THIS instrument.

AN OPTIONAL EXTRA VOTE: typed, calibrated probabilities from the LLM lab, read from the vintaged
file `LLM_STATES` (`{"symbol","date","asof","p_stress","p_up","model"}` rows) and counted only
when `asof` precedes the day it votes on. It is a READING for the report, never a gate input:
the tradable family below uses the deterministic systems only (LLMs propose, never size), so the
gauntlet can rebuild every cell exactly. Absent file: the vote is UNMEASURED, not neutral.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.special import gammaln, ndtr

from libs.regime.control_room import daily_frame, label_days, trailing_pct
from libs.regime.hmm import GaussianHMM

ROOT = Path(__file__).resolve().parents[2]
LLM_STATES = ROOT / "desks" / "mt5" / "data" / "regime_llm_states.jsonl"

RANK_WIN = 252
EWMA_LAMBDA = 0.94
REFIT = 252                 # yearly refits (GARCH, HMM)
TRAIN = 756                 # each refit trains on the trailing three years BEFORE the segment
MIN_TRAIN = 378             # no reading before a year and a half of history
HMM_ITERS = 40
TSMOM_WIN = 60
DRIFT_H = 20
BOCPD_HAZARD = 1.0 / 120.0
BOCPD_RMAX = 300
BOCPD_RECENT = 5
SPLIT_PCT, CONSENSUS_PCT = 2 / 3, 1 / 3
FRESH_P, SETTLED_P = 0.5, 0.1

VOL_SYSTEMS = ("markov", "ewma", "garch", "hmm")
TREND_SYSTEMS = ("markov", "kalman", "tsmom", "hmm")
AXES = ("vol", "trend", "transition")

_CACHE: dict[tuple[Any, ...], pd.DataFrame] = {}


# ------------------------------------------------------------------------------- primitives

def _h(p: np.ndarray) -> np.ndarray:
    """Binary entropy in bits; 0 at 0 and 1."""
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return np.asarray(-(q * np.log2(q) + (1 - q) * np.log2(1 - q)), dtype=float)


def mutual_information(probs: np.ndarray) -> np.ndarray:
    """H(mean p) - mean H(p_i) per row of an (n, m) array, ignoring NaN members; NaN with < 2."""
    p = np.asarray(probs, dtype=float)
    ok = np.isfinite(p)
    cnt = ok.sum(axis=1)
    pz = np.where(ok, p, 0.0)
    mean = np.divide(pz.sum(axis=1), cnt, out=np.full(p.shape[0], np.nan), where=cnt > 0)
    mh = np.divide(np.where(ok, _h(np.where(ok, p, 0.5)), 0.0).sum(axis=1), cnt,
                   out=np.full(p.shape[0], np.nan), where=cnt > 0)
    out = _h(np.nan_to_num(mean, nan=0.5)) - mh
    out[cnt < 2] = np.nan
    return np.asarray(np.maximum(out, 0.0), dtype=float)


def _scaled_returns(lr: np.ndarray) -> np.ndarray:
    """Returns divided by the trailing-year std known BEFORE the day (causal standardisation)."""
    sd = pd.Series(lr).rolling(RANK_WIN, min_periods=60).std().shift(1).to_numpy()
    return np.where(sd > 0, lr / np.where(sd > 0, sd, 1.0), np.nan)


def _segments(n: int) -> list[tuple[int, int, int]]:
    """(train_lo, seg_lo, seg_hi): each yearly segment is read with params trained on
    [train_lo, seg_lo) only."""
    out = []
    for lo in range(MIN_TRAIN, n, REFIT):
        out.append((max(0, lo - TRAIN), lo, min(n, lo + REFIT)))
    return out


def ewma_vol(lr: np.ndarray) -> np.ndarray:
    r2 = np.nan_to_num(lr, nan=0.0) ** 2
    v = lfilter([1 - EWMA_LAMBDA], [1, -EWMA_LAMBDA], r2)
    v[:20] = np.nan
    return np.asarray(np.sqrt(v), dtype=float)


def _garch_var(r: np.ndarray, a: float, b: float, var: float) -> np.ndarray:
    """h_t = w + a r_{t-1}^2 + b h_{t-1} with w = var (1 - a - b): the forecast FOR day t."""
    w = var * (1 - a - b)
    r2 = np.r_[var, r[:-1] ** 2]
    return np.asarray(lfilter([a], [1, -b], r2) + w / (1 - b), dtype=float)


def garch_vol(lr: np.ndarray) -> np.ndarray:
    """One-step-ahead GARCH(1,1) vol for day t+1, from params fitted on the past only."""
    r = np.nan_to_num(lr, nan=0.0)
    out = np.full(r.size, np.nan)
    grid = [(a, p - a) for a in (0.03, 0.05, 0.08, 0.12) for p in (0.90, 0.95, 0.98, 0.995)]
    for tlo, lo, hi in _segments(r.size):
        tr = r[tlo:lo]
        var = float(tr.var()) or 1e-12
        best, ab = -np.inf, grid[0]
        for a, b in grid:
            h = _garch_var(tr, a, b, var)
            ll = -0.5 * float(np.sum(np.log(h) + tr * tr / h))
            if ll > best:
                best, ab = ll, (a, b)
        a, b = ab
        # run from the segment's training start so the state at `lo` is warm, read [lo, hi)
        seg = r[tlo:hi]
        h = _garch_var(seg, a, b, var)
        nxt = var * (1 - a - b) + a * seg ** 2 + b * h       # forecast for the NEXT day
        out[lo:hi] = np.sqrt(nxt[lo - tlo:])
    return out


def hmm_readings(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(P(high-variance state), P(up over DRIFT_H days)) from yearly-refit 2-state HMMs."""
    n = z.size
    p_hi = np.full(n, np.nan)
    p_up = np.full(n, np.nan)
    x = np.nan_to_num(z, nan=0.0)
    for tlo, lo, hi in _segments(n):
        tr = x[tlo:lo]
        if tr.size < MIN_TRAIN // 2 or not np.isfinite(z[tlo:lo]).any():
            continue
        m = GaussianHMM(2, n_iter=HMM_ITERS, seed=0).fit(tr)
        post = m.filter_posterior(x[tlo:hi])[lo - tlo:]
        var = m.vars[:, 0]
        mu = m.means[:, 0]
        p_hi[lo:hi] = post[:, int(np.argmax(var))]
        up = ndtr(mu * math.sqrt(DRIFT_H) / np.sqrt(var))
        p_up[lo:hi] = post @ up
    p_hi[~np.isfinite(z)] = np.nan
    p_up[~np.isfinite(z)] = np.nan
    return p_hi, p_up


def kalman_trend(logp: np.ndarray, z_scale: np.ndarray) -> np.ndarray:
    """Local-linear-trend Kalman filter on log price; Phi(slope / sd(slope)). Noise is scaled by
    the causal return std, so the filter is scale-free across instruments."""
    n = logp.size
    out = np.full(n, np.nan)
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    s = np.array([logp[0] if np.isfinite(logp[0]) else 0.0, 0.0])
    P = np.eye(2)
    for t in range(n):
        sd = z_scale[t]
        y = logp[t]
        if not (np.isfinite(sd) and sd > 0 and np.isfinite(y)):
            continue
        R = sd * sd
        Q = np.diag([0.05 * R, 0.0005 * R])
        s = F @ s
        P = F @ P @ F.T + Q
        S = P[0, 0] + R
        K = P[:, 0] / S
        s = s + K * (y - s[0])
        P = P - np.outer(K, P[0, :])
        out[t] = float(ndtr(s[1] / math.sqrt(max(P[1, 1], 1e-18))))
    return out


def bocpd_recent(z: np.ndarray, hazard: float = BOCPD_HAZARD, rmax: int = BOCPD_RMAX,
                 recent: int = BOCPD_RECENT) -> np.ndarray:
    """P(run length < `recent`) after each observation, Normal-Gamma prior (0, 1, 1, 1)."""
    n = z.size
    out = np.full(n, np.nan)
    mu = np.array([0.0])
    kap = np.array([1.0])
    alp = np.array([1.0])
    bet = np.array([1.0])
    logr = np.array([0.0])
    lh, l1h = math.log(hazard), math.log1p(-hazard)
    seen = 0
    for t in range(n):
        x = z[t]
        if not np.isfinite(x):
            continue
        seen += 1
        nu = 2 * alp
        sc2 = bet * (kap + 1) / (alp * kap)
        lp = (gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(nu * np.pi * sc2)
              - (nu + 1) / 2 * np.log1p((x - mu) ** 2 / (nu * sc2)))
        grow = logr + lp + l1h
        cp = np.logaddexp.reduce(logr + lp + lh)
        logr = np.r_[cp, grow]
        mu = np.r_[0.0, (kap * mu + x) / (kap + 1)]
        bet = np.r_[1.0, bet + kap * (x - mu[1:]) ** 2 / (2 * (kap + 1))]
        kap = np.r_[1.0, kap + 1]
        alp = np.r_[1.0, alp + 0.5]
        if logr.size > rmax:
            tail = np.logaddexp.reduce(logr[rmax - 1:])
            logr = np.r_[logr[:rmax - 1], tail]
            mu, kap, alp, bet = mu[:rmax], kap[:rmax], alp[:rmax], bet[:rmax]
        logr = logr - np.logaddexp.reduce(logr)
        if seen > recent:   # the first `recent` runs are short by construction, not evidence
            out[t] = float(np.exp(logr[:recent]).sum())
    return out


# ------------------------------------------------------------------------------- the table

def readings(daily: pd.DataFrame) -> pd.DataFrame:
    """Per-day votes, per-axis disagreement and the state labels. Causal row by row."""
    close = daily["close"].to_numpy(float)
    logp = np.log(close)
    lr = np.r_[np.nan, np.diff(logp)]
    lab = label_days(daily)
    z = _scaled_returns(lr)
    sd = pd.Series(lr).rolling(RANK_WIN, min_periods=60).std().to_numpy()
    p_hi, p_hmm_up = hmm_readings(z)
    ret20 = pd.Series(logp).diff(20).to_numpy()
    m60 = pd.Series(lr).rolling(TSMOM_WIN).mean().to_numpy()
    s60 = pd.Series(lr).rolling(TSMOM_WIN).std().to_numpy()
    t60 = np.where(s60 > 0, m60 / np.where(s60 > 0, s60, 1.0) * math.sqrt(TSMOM_WIN), np.nan)
    vol = {
        "markov": lab["vol_pct"].to_numpy(float),
        "ewma": trailing_pct(ewma_vol(lr), RANK_WIN),
        "garch": trailing_pct(garch_vol(lr), RANK_WIN),
        "hmm": p_hi,
    }
    trend = {
        "markov": 0.5 + 0.5 * np.sign(np.nan_to_num(ret20)) * lab["er_pct"].to_numpy(float),
        "kalman": kalman_trend(logp, sd),
        "tsmom": ndtr(t60),
        "hmm": p_hmm_up,
    }
    df = pd.DataFrame(index=daily.index)
    for k, v in vol.items():
        df[f"vol_{k}"] = v
    for k, v in trend.items():
        df[f"trend_{k}"] = v
    df["transition_bocpd"] = bocpd_recent(z)
    df["mi_vol"] = mutual_information(np.column_stack([vol[k] for k in VOL_SYSTEMS]))
    df["mi_trend"] = mutual_information(np.column_stack([trend[k] for k in TREND_SYSTEMS]))
    vs = np.column_stack([vol[k] for k in VOL_SYSTEMS])
    cnt = np.isfinite(vs).sum(axis=1)
    df["vol_mean"] = np.divide(np.nansum(vs, axis=1), cnt, out=np.full(len(df), np.nan),
                               where=cnt > 0)
    for ax in ("vol", "trend"):
        pct = trailing_pct(df[f"mi_{ax}"].to_numpy(float), RANK_WIN)
        df[f"{ax}_pct"] = pct
        df[ax] = np.where(np.isnan(pct), "", np.where(pct > SPLIT_PCT, "split",
                                                     np.where(pct < CONSENSUS_PCT,
                                                              "consensus", "mid")))
    b = df["transition_bocpd"].to_numpy(float)
    df["transition"] = np.where(np.isnan(b), "", np.where(b >= FRESH_P, "fresh",
                                                          np.where(b <= SETTLED_P,
                                                                   "settled", "mid")))
    return df


def readings_for_bars(h1: pd.DataFrame) -> pd.DataFrame:
    """`readings` of an H1 frame, cached per frame extent (the gauntlet calls per cell)."""
    idx = h1.index
    key = (len(h1), str(idx[0]) if len(h1) else "", str(idx[-1]) if len(h1) else "",
           float(h1["close"].iloc[-1]) if len(h1) else 0.0)
    got = _CACHE.get(key)
    if got is None:
        got = readings(daily_frame(h1))
        if len(_CACHE) > 64:
            _CACHE.clear()
        _CACHE[key] = got
    return got


# ------------------------------------------------------------------------- the LLM vote

def llm_votes(symbol: str, path: Path | None = None) -> pd.DataFrame | None:
    """The LLM lab's vintaged typed probabilities for `symbol`, one row per voted day, keeping
    only rows whose `asof` precedes the day voted on. None when the file is absent or empty."""
    p = path or LLM_STATES
    rows: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict) or str(r.get("symbol")) != symbol:
                    continue
                day, asof = str(r.get("date") or ""), str(r.get("asof") or "")
                if not day or not asof or asof[:10] >= day:
                    continue
                rows.append({"date": day,
                             "p_stress": _prob(r.get("p_stress")), "p_up": _prob(r.get("p_up"))})
    except OSError:
        return None
    if not rows:
        return None
    return pd.DataFrame(rows).groupby("date").last()


def _prob(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if 0.0 <= v <= 1.0 else float("nan")


def with_llm(df: pd.DataFrame, votes: pd.DataFrame | None) -> dict[str, Any]:
    """How often the LLM vote agrees with the deterministic ensemble, on the days it voted.
    UNMEASURED without votes: an absent vote is never read as agreement."""
    if votes is None or votes.empty:
        return {"status": "UNMEASURED", "why": f"no vintaged rows in {LLM_STATES.name}"}
    j = df.join(votes, how="inner")
    if j.empty:
        return {"status": "UNMEASURED", "why": "no voted day overlaps the bars"}
    vm = j[[f"vol_{k}" for k in VOL_SYSTEMS]].mean(axis=1)
    tm = j[[f"trend_{k}" for k in TREND_SYSTEMS]].mean(axis=1)
    agree_v = ((j["p_stress"] > 0.5) == (vm > 0.5))[j["p_stress"].notna()]
    agree_t = ((j["p_up"] > 0.5) == (tm > 0.5))[j["p_up"].notna()]
    return {"status": "MEASURED", "days": len(j),
            "vol_agreement": round(float(agree_v.mean()), 3) if len(agree_v) else None,
            "trend_agreement": round(float(agree_t.mean()), 3) if len(agree_t) else None}


# ------------------------------------------------------------------------- predictiveness

def predictiveness(df: pd.DataFrame, daily: pd.DataFrame, horizon: int = 5) -> dict[str, Any]:
    """Does disagreement predict what the directive asked about? Spearman rank correlations of
    each axis's disagreement with the NEXT `horizon` days' realised vol (beyond what today's
    vol already says: the residual against the ensemble's mean vol score) and |return|."""
    close = daily["close"].to_numpy(float)
    lr = np.r_[np.nan, np.diff(np.log(close))]
    fwd_rv = pd.Series(lr[::-1]).rolling(horizon).std().to_numpy()[::-1]
    fwd_rv = np.r_[fwd_rv[1:], np.nan]                      # days t+1..t+horizon
    fwd_abs = np.abs(pd.Series(np.log(close)).shift(-horizon).to_numpy() - np.log(close))
    out: dict[str, Any] = {"horizon_days": horizon}
    base = df["vol_mean"].to_numpy(float)
    for ax in ("mi_vol", "mi_trend", "transition_bocpd"):
        x = df[ax].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(fwd_rv) & np.isfinite(base)
        if ok.sum() < 100:
            out[ax] = {"status": "UNMEASURED", "n": int(ok.sum())}
            continue
        rv = pd.Series(fwd_rv[ok]).rank().to_numpy()
        bs = pd.Series(base[ok]).rank().to_numpy()
        beta = np.polyfit(bs, rv, 1)
        resid = rv - np.polyval(beta, bs)
        xr = pd.Series(x[ok]).rank().to_numpy()
        ok2 = ok & np.isfinite(fwd_abs)
        out[ax] = {"n": int(ok.sum()),
                   "rho_fwd_vol": round(float(np.corrcoef(xr, rv)[0, 1]), 4),
                   "rho_fwd_vol_beyond_level": round(float(np.corrcoef(xr, resid)[0, 1]), 4),
                   "rho_fwd_abs_move": round(float(np.corrcoef(
                       pd.Series(x[ok2]).rank(), pd.Series(fwd_abs[ok2]).rank())[0, 1]), 4)}
    return out
