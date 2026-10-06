"""LATENT MACRO STATES BY KALMAN FILTER -- inflation, the dollar and gold's macro fair value, with
the residuals mined (ROMAN-0839, ROMAN-0840, ROMAN-0841).

All filtering is `libs.quant_models.kalman` (the desk's one state-space module). Everything
published is FILTERED (a_{t|t}) or ONE-STEP-AHEAD (a_{t|t-1}, y_hat_{t|t-1}); the RTS smoother is
never used here.

THE CLOCK. One row per broker trading day d of XAUUSD, available at A_d = d+1 01:00 UTC (the PIT
law's earliest instant for a daily close). Every input enters at the first A_d at or after the
instant it became knowable:
  broker closes            close of day d at A_d (declared lag, CONVENTIONS)
  FRED daily market series `market_state.knowable` (H.15 / next-day 09:00 ET), so at A_d the
                           desk holds day d-1's DFII10 / T10YIE / T5YIE, never day d's
  CPI / PCE monthly prints ALFRED FIRST PRINTS at the agency's scheduled release instant when the
                           lake holds them (calendar basis); otherwise FRED's REVISED series at a
                           DECLARED conservative lag (CPI 45 days, PCE 62 days after the
                           reference month's first day, 13:30 UTC) -- named in the report,
                           because a revised value is a look-ahead the first-print path avoids
HYPERPARAMETERS (noise variances, loadings, standardisation) are fitted by MLE on a TRAINING
window (the first TRAIN_DAYS rows) and frozen; every contract is measured on rows after it.

THE STATES.
  ws_latent_inflation  local-level latent inflation pressure pi_t observed through standardised
                       CPI m/m, PCE m/m (annualised) and breakevens T5YIE/T10YIE (each with its
                       own noise variance, missing on days without a new print). Published: the
                       state, its sd, the state's update z (its own surprise) and the CPI print's
                       innovation z on release days.
  ws_latent_dollar     one common factor of the six USD crosses' log prices, signs aligned so
                       USD-up is positive (EURUSD, GBPUSD, AUDUSD inverted), loadings by PCA of
                       training-window returns, state = [factor, idiosyncratic random walks].
                       Published: factor level, its update z, and each pair's residual z (pair
                       rich (+) / cheap (-) against the factor, in the pair's own quote direction).
  ws_gold_fair_value   time-varying regression of log XAUUSD on [1, DFII10, dollar factor,
                       T10YIE (if held)], random-walk betas; fair value = x_d' beta_{d|d-1};
                       residual z = the one-step-ahead innovation over its sd (gold rich > 0).

THE CONTRACTS.
  ROMAN-0841 gated_gain   residual-reversion cell on XAUUSD: -sign(z) x the next tradeable
                          day's return (close d+1 -> d+2, the first close after A_d), traded
                          only when |z| >= 1, against the same cell traded every day; null =
                          circular shift, strata = trailing realised-vol tercile.
  ROMAN-0841 forecast_gain  next-week log change of gold (close d -> d+5) forecast by
                          kappa x (fair value - price), kappa an expanding no-intercept regression
                          on already-knowable weeks, against the random walk (zero change).
  ROMAN-0840 gated_gain   per USD pair, the same residual-reversion cell on the pair's residual
                          against the dollar factor.
  ROMAN-0839 forecast_gain  the next CPI m/m print forecast from the latent state the day before
                          the print, against the random walk (the previous print). min_n is
                          LOOSENED to 60 from the spine's 250 because the target is monthly; the
                          contract row says so.

NO AUTHORITY. State and cells only; the -1 side on residual cells is the mechanism's declared
direction for a gauntlet cell, never a live order.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.quant_models import kalman  # noqa: E402
from libs.research import sensor_engines as se  # noqa: E402

ENGINE = "latent_states"
REPORT = DESK / "reports" / "LATENT_STATES.json"
S_INFL = "ws_latent_inflation"
S_USD = "ws_latent_dollar"
S_GOLD = "ws_gold_fair_value"
UNMEASURED = "UNMEASURED"
CARD_INFL, CARD_USD, CARD_GOLD = "ROMAN-0839", "ROMAN-0840", "ROMAN-0841"

#: Aligned so USD-up is positive.
USD_PAIRS: dict[str, int] = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1,
                             "USDCAD": 1, "USDCHF": 1}
METALS = ("XAUUSD", "XAGUSD")
TRAIN_DAYS = 750
MIN_DAYS = TRAIN_DAYS + 260
GATE_Z = 1.0
RESID_EWMA = 20
CPI_MIN_N = 60
#: Declared lags for REVISED monthly FRED series (reference-month first day -> knowable).
MONTHLY_LAG_D = {"CPIAUCSL": 45, "PCEPI": 62}
DAILY_FRED = ("T5YIE", "T10YIE", "DFII10")
CLOSE_LAG = timedelta(days=1, hours=1)


# ============================================================================== small helpers
def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text or text == UNMEASURED:
        return None
    try:
        got = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (got if got.tzinfo else got.replace(tzinfo=UTC)).astimezone(UTC)


def avail(day: date) -> datetime:
    """A_d: the instant the close of broker day d is knowable."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + CLOSE_LAG


def on_clock(obs: Sequence[tuple[datetime, float]], clock: Sequence[datetime]) -> np.ndarray:
    """Each observation placed on the FIRST clock instant at or after its knowable instant
    (later observations landing on the same instant replace earlier ones); NaN elsewhere."""
    out = np.full(len(clock), np.nan)
    ck = np.asarray([c.timestamp() for c in clock])
    for at, v in sorted(obs, key=lambda x: x[0]):
        i = int(np.searchsorted(ck, at.timestamp(), side="left"))
        if i < len(clock) and math.isfinite(v):
            out[i] = v
    return out


def asof(obs: Sequence[tuple[datetime, float]], clock: Sequence[datetime]) -> np.ndarray:
    """Latest observation knowable at or before each clock instant (NaN before the first)."""
    o = sorted(obs, key=lambda x: x[0])
    ts = np.asarray([a.timestamp() for a, _ in o])
    vs = np.asarray([v for _, v in o], dtype=float)
    out = np.full(len(clock), np.nan)
    if ts.size == 0:
        return out
    idx = np.searchsorted(ts, [c.timestamp() for c in clock], side="right") - 1
    ok = idx >= 0
    out[ok] = vs[idx[ok]]
    return out


def trailing_z(x: np.ndarray, span: int = RESID_EWMA, sd_window: int = 252) -> np.ndarray:
    """(x - EWMA_span(x up to t)) / trailing sd of that gap (gaps strictly before t)."""
    lam = 1.0 - 2.0 / (span + 1.0)
    gap = np.full(x.size, np.nan)
    m = np.nan
    for i, v in enumerate(x):
        if not math.isfinite(v):
            continue
        m = v if not math.isfinite(m) else lam * m + (1 - lam) * v
        gap[i] = v - m
    out = np.full(x.size, np.nan)
    for i in range(30, x.size):
        h = gap[max(0, i - sd_window):i]
        h = h[np.isfinite(h)]
        if h.size >= 30 and math.isfinite(gap[i]):
            sd = float(h.std(ddof=1))
            out[i] = gap[i] / sd if sd > 0 else np.nan
    return out


def vol_tercile(r: np.ndarray, window: int = 20) -> list[Any]:
    """Trailing realised-vol tercile (vol of returns strictly before t, terciles by expanding
    rank), the control stratum `gated_gain` asks for."""
    out: list[Any] = [None] * r.size
    hist: list[float] = []
    for i in range(window, r.size):
        w = r[i - window:i]
        w = w[np.isfinite(w)]
        if w.size < window // 2:
            continue
        v = float(w.std())
        if len(hist) >= 60:
            q = float(np.mean(np.asarray(hist) <= v))
            out[i] = 0 if q < 1 / 3 else (1 if q < 2 / 3 else 2)
        hist.append(v)
    return out


# ============================================================================== data intake
def load_closes(symbols: Sequence[str], now: datetime) -> dict[str, list[tuple[str, float]]]:
    from macro.market_state import _chart, daily_closes
    out = {}
    for s in symbols:
        rows = daily_closes(_chart(s), now)
        if rows:
            out[s] = rows
    return out


def fred_daily(series: Mapping[str, list[tuple[str, float]]], sid: str
               ) -> list[tuple[datetime, float]]:
    from macro.market_state import knowable
    return [(knowable(d, sid), v) for d, v in series.get(sid, [])]


def inflation_prints(now: datetime, series: Mapping[str, list[tuple[str, float]]],
                     alfred: Path | None = None) -> dict[str, Any]:
    """{"cpi"/"pce": {"rows": [(knowable, annualised m/m %)], "basis": ...}}."""
    from macro import release_vintages as rv
    out: dict[str, Any] = {}
    for name, title, sid in (("cpi", "USD CPI m/m", "CPIAUCSL"),
                             ("pce", "USD Core PCE Price Index m/m", "PCEPI")):
        spec = rv.BY_TITLE[title]
        df = rv.load_alfred(spec.series, alfred or rv.ALFRED)
        rows: list[tuple[datetime, float]] = []
        if df is not None:
            for p in rv.release_vintage(df, spec):
                at = rv.scheduled_utc(spec, date.fromisoformat(p["vintage"]))
                if at <= now:
                    rows.append((at, 12.0 * float(p["actual"])))
            if rows:
                out[name] = {"rows": rows, "basis": "calendar",
                             "source": f"alfred:{spec.series} first prints"}
                continue
        lvl = series.get(sid) or []
        for (_d0, v0), (d1, v1) in zip(lvl, lvl[1:], strict=False):
            if v0 > 0:
                ref = date.fromisoformat(d1[:10])
                at = datetime(ref.year, ref.month, ref.day, 13, 30, tzinfo=UTC) + timedelta(
                    days=MONTHLY_LAG_D[sid])
                if at <= now:
                    rows.append((at, 1200.0 * (v1 / v0 - 1.0)))
        if rows:
            out[name] = {"rows": rows, "basis": "declared_lag",
                         "source": f"fred:{sid} REVISED, lag {MONTHLY_LAG_D[sid]}d (look-ahead "
                                   "in revisions; ALFRED first prints preferred)"}
    return out


# ============================================================================== the dollar
def dollar_state(closes: Mapping[str, list[tuple[str, float]]], dates: Sequence[date],
                 train: int = TRAIN_DAYS) -> dict[str, Any]:
    pairs = [p for p in USD_PAIRS if p in closes]
    if len(pairs) < 3:
        return {"status": UNMEASURED, "why": f"{len(pairs)} USD pairs with bars; need 3"}
    idx = {d: i for i, d in enumerate(dates)}
    Y = np.full((len(dates), len(pairs)), np.nan)
    for j, p in enumerate(pairs):
        for ds, v in closes[p]:
            i = idx.get(date.fromisoformat(ds[:10]))
            if i is not None and v > 0:
                Y[i, j] = USD_PAIRS[p] * math.log(v)
    first = np.array([Y[np.isfinite(Y[:, j]), j][0] if np.isfinite(Y[:, j]).any() else 0.0
                      for j in range(len(pairs))])
    Y = Y - first
    R = np.diff(Y[:train], axis=0)
    R = R[np.all(np.isfinite(R), axis=1)]
    if R.shape[0] < 200:
        return {"status": UNMEASURED, "why": f"{R.shape[0]} complete training returns < 200"}
    C = np.cov(R.T)
    w, V = np.linalg.eigh(C)
    lam = V[:, -1] * math.sqrt(max(w[-1], 1e-18))
    lam = lam if lam.sum() >= 0 else -lam
    psi = np.maximum(np.diag(C) - lam ** 2, 1e-12)
    p, m = len(pairs), len(pairs) + 1
    Z = np.hstack([lam[:, None], np.eye(p)])
    a0 = np.zeros(m)

    # Measurement noise DECLARED (quote noise ~ 1e-4 in log price); the one free parameter, the
    # idiosyncratic-to-PCA variance scale s, is fitted by MLE on the training window.
    h = 1e-8

    def build(th: np.ndarray) -> kalman.StateSpace:
        return kalman.StateSpace(Z=Z, H=np.eye(p) * h, T=np.eye(m),
                                 Q=np.diag(np.concatenate([[1.0], th[0] * psi])), a0=a0,
                                 P0=np.eye(m) * 1e-6)

    fit = kalman.fit_mle(Y[:train], build, [1.0], maxiter=40)
    res = kalman.kalman_filter(Y, fit.model)
    f = res.a_filt[:, 0]
    resid = {}
    for j, pr in enumerate(pairs):
        resid[pr] = USD_PAIRS[pr] * trailing_z(res.a_filt[:, 1 + j])
    return {"status": "MEASURED", "pairs": pairs, "loadings": [float(x) for x in lam],
            "idio_var": [float(x) for x in psi], "mle": fit.to_dict(), "factor": f,
            "factor_sd": np.sqrt(res.P_filt[:, 0, 0]), "update_z": res.state_update_z(0),
            "resid_z": resid, "aligned_logs": Y}


# ============================================================================== gold fair value
def gold_fair_value(y: np.ndarray, X: np.ndarray, names: Sequence[str],
                    train: int = TRAIN_DAYS) -> dict[str, Any]:
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    first = int(np.flatnonzero(ok)[0]) if ok.any() else len(y)
    if int(ok.sum()) < train + 100:
        return {"status": UNMEASURED, "why": f"{int(ok.sum())} complete rows < {train + 100}"}
    tr_end = int(np.flatnonzero(ok)[train - 1]) + 1
    # Regressors standardised on the TRAINING window only (the constant stays 1), and ONE shared
    # random-walk variance for every beta: a fair value whose betas may each wander at their own
    # MLE rate lets the intercept chase the price and the "fair value" becomes the price.
    Xs = X.copy()
    tr = X[first:tr_end]
    for j in range(X.shape[1]):
        col = tr[:, j][np.isfinite(tr[:, j])]
        sd = float(col.std()) if col.size > 1 else 0.0
        if sd > 0:
            Xs[:, j] = (X[:, j] - float(col.mean())) / sd
    fit = kalman.fit_tvp_regression(y[first:tr_end], Xs[first:tr_end], shared_q=True,
                                    maxiter=150)
    sig2, q = float(fit.params[0]), float(fit.params[1])
    yy = kalman.tvp_y(y, Xs)
    model = kalman.tvp_regression(yy, Xs, sig2, q)
    res = kalman.kalman_filter(yy, model)
    fv = res.y_hat[:, 0].copy()
    fv[~ok] = np.nan
    return {"status": "MEASURED", "regressors": list(names), "mle": fit.to_dict(),
            "betas_on": "training-standardised regressors (constant unscaled)",
            "train_end_index": tr_end, "fair_value": fv, "resid_z": res.innovation_z()[:, 0],
            "betas": res.a_pred}


# ============================================================================== inflation
def inflation_state(obs: Mapping[str, np.ndarray], train: int = TRAIN_DAYS) -> dict[str, Any]:
    names = [k for k, v in obs.items() if np.isfinite(v[:train]).sum() >= 12]
    if not names:
        return {"status": UNMEASURED, "why": "no inflation input with >= 12 training points"}
    Y = np.column_stack([obs[k] for k in names])
    mean = np.nanmean(Y[:train], axis=0)
    sd = np.nanstd(Y[:train], axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    S = (Y - mean) / sd
    p = len(names)

    def build(th: np.ndarray) -> kalman.StateSpace:
        return kalman.StateSpace(Z=np.ones((p, 1)), H=np.diag(th[:p]), T=np.eye(1),
                                 Q=np.array([[th[p]]]), a0=np.zeros(1), P0=np.eye(1) * 10.0)

    fit = kalman.fit_mle(S[:train], build, [0.5] * p + [0.01], maxiter=150)
    res = kalman.kalman_filter(S, fit.model)
    return {"status": "MEASURED", "inputs": names, "mean": mean.tolist(), "sd": sd.tolist(),
            "mle": fit.to_dict(), "state": res.a_filt[:, 0],
            "state_sd": np.sqrt(res.P_filt[:, 0, 0]), "state_pred": res.a_pred[:, 0],
            "update_z": res.state_update_z(0), "innov_z": res.innovation_z(),
            "Y": Y}


# ============================================================================== contracts
def reversion_contract(z: np.ndarray, r_next: np.ndarray, *, cards: Sequence[str], label: str,
                       start: int, falsifier: str) -> dict[str, Any]:
    payoff = -np.sign(z) * r_next
    gate = np.abs(z) >= GATE_Z
    sl = slice(start, None)
    strata = vol_tercile(np.concatenate([[np.nan], r_next[:-1]]))
    row = se.gated_gain(payoff[sl], gate[sl], engine=ENGINE, cards=cards, falsifier=falsifier,
                        baseline="the same residual-reversion cell traded every day",
                        strata=strata[start:])
    row["label"] = label
    return row


def week_forecast_contract(logp: np.ndarray, fv: np.ndarray, start: int) -> dict[str, Any]:
    """Next-week log change from the last close the desk holds at A_d (close d -> close d+5),
    forecast by kappa (fv_d - logp_d); kappa by expanding no-intercept regression on weeks
    whose outcome was knowable at A_d (j + 5 <= d). A forecast, not a payoff: no fill at close d
    is assumed, only that close d is known when the forecast is made."""
    n = logp.size
    y = np.full(n, np.nan)
    y[:n - 5] = logp[5:] - logp[:n - 5]
    gap = fv - logp
    model = np.full(n, np.nan)
    sxx = sxy = 0.0
    cnt = 0
    fin = np.flatnonzero(np.isfinite(gap))
    # burn-in: the diffuse start's first filtered gaps are huge and would own the regression
    burn = int(fin[0]) + 60 if fin.size else n
    for d in range(n):
        j = d - 5
        if j >= burn and math.isfinite(gap[j]) and math.isfinite(y[j]):
            sxx += gap[j] * gap[j]
            sxy += gap[j] * y[j]
            cnt += 1
        if cnt >= 60 and sxx > 0 and math.isfinite(gap[d]):
            model[d] = (sxy / sxx) * gap[d]
    sl = slice(start, None)
    # in basis points: the spine rounds gains to 6 decimals, and a squared weekly log change
    # (~1e-4) would round a real loss reduction to zero
    row = se.forecast_gain(1e4 * y[sl], 1e4 * model[sl], np.zeros(n)[sl], engine=ENGINE,
                           cards=[CARD_GOLD],
                           falsifier=("the filtered fair value does not forecast next-week gold "
                                      "better than a random walk"),
                           baseline="random walk (zero expected change)", loss="mse")
    row["label"] = "XAUUSD:next_week_change:fair_value_gap"
    row["unit"] = "bp^2"
    return row


def cpi_contract(infl: Mapping[str, Any], start: int, min_n: int = CPI_MIN_N) -> dict[str, Any]:
    falsifier = "the latent state does not forecast the next CPI print better than the last print"
    common = {"engine": ENGINE, "cards": [CARD_INFL], "falsifier": falsifier,
              "baseline": "random walk (previous CPI print)"}
    if infl.get("status") != "MEASURED" or "cpi" not in infl["inputs"]:
        row = se.contract(**common, metric="mse_reduction", value=None, baseline_value=None,
                          n=0, min_n=min_n, why=infl.get("why") or "no CPI input")
    else:
        j = infl["inputs"].index("cpi")
        col = infl["Y"][:, j]
        days = np.flatnonzero(np.isfinite(col))
        ys, ms, bs = [], [], []
        for a, b in zip(days, days[1:], strict=False):
            if b < start:
                continue
            ys.append(col[b])
            bs.append(col[a])
            ms.append(infl["mean"][j] + infl["sd"][j] * infl["state_pred"][b])
        row = se.forecast_gain(ys, ms, bs, loss="mse", min_n=min_n, block=6, **common)
    row["label"] = "US:cpi_mm_annualised:latent_inflation"
    row["min_n_note"] = f"min_n loosened 250 -> {min_n}: the target is a monthly print"
    return row


# ============================================================================== build
def build(now: datetime, *, closes: Mapping[str, list[tuple[str, float]]] | None = None,
          series: Mapping[str, list[tuple[str, float]]] | None = None,
          prints: Mapping[str, Any] | None = None, train: int = TRAIN_DAYS,
          cpi_min_n: int = CPI_MIN_N) -> dict[str, Any]:
    from macro.market_state import load_series
    syms = list(USD_PAIRS) + list(METALS)
    cl = dict(load_closes(syms, now) if closes is None else closes)
    fred = dict(load_series() if series is None else series)
    pr = dict(inflation_prints(now, fred) if prints is None else prints)
    rep: dict[str, Any] = {"engine": ENGINE, "at": now.isoformat(timespec="seconds"),
                           "authority": "NONE", "train_days": train,
                           "inputs": {"closes": sorted(cl), "fred": sorted(
                               s for s in DAILY_FRED if fred.get(s)),
                               "prints": {k: {"n": len(v["rows"]), "basis": v["basis"],
                                              "source": v["source"]} for k, v in pr.items()}}}
    gold = cl.get("XAUUSD") or []
    dates = [date.fromisoformat(d[:10]) for d, _ in gold if avail(date.fromisoformat(d[:10]))
             <= now]
    if len(dates) < MIN_DAYS:
        why = f"{len(dates)} XAUUSD days < {MIN_DAYS}"
        rep.update({"status": UNMEASURED, "why": why, "series": {}, "contracts": [
            se.contract(engine=ENGINE, cards=[c], metric=m, baseline=b, falsifier=f,
                        value=None, baseline_value=None, n=len(dates), why=why) | {"label": lb}
            for c, m, b, f, lb in (
                (CARD_GOLD, "kelly_growth_annual", "ungated residual reversion",
                 "gold residual reversion gated by |z| adds nothing", "XAUUSD:gold_resid"),
                (CARD_GOLD, "mse_reduction", "random walk",
                 "fair value does not forecast next-week gold", "XAUUSD:next_week"),
                (CARD_USD, "kelly_growth_annual", "ungated residual reversion",
                 "pair residual vs dollar factor does not revert", "USD:pair_resid"),
                (CARD_INFL, "mse_reduction", "random walk",
                 "latent inflation does not forecast CPI", "US:cpi"))]})
        return rep
    clock = [avail(d) for d in dates]
    gmap = {date.fromisoformat(d[:10]): v for d, v in gold}
    logp = np.log(np.asarray([gmap[d] for d in dates], dtype=float))
    r_gold = np.diff(logp, prepend=np.nan)
    r_next = np.concatenate([r_gold[2:], [np.nan, np.nan]])     # close d+1 -> d+2
    n = len(dates)
    series_out: dict[str, list[dict[str, Any]]] = {S_INFL: [], S_USD: [], S_GOLD: []}
    contracts: list[dict[str, Any]] = []

    # ---- dollar
    usd = dollar_state(cl, dates, train)
    rep["dollar"] = {k: v for k, v in usd.items() if not isinstance(v, np.ndarray | dict)
                     or k == "mle"}
    if usd["status"] == "MEASURED":
        for pr_name in usd["pairs"]:
            pm = {date.fromisoformat(d[:10]): v for d, v in cl[pr_name]}
            px = np.asarray([pm.get(d, np.nan) for d in dates], dtype=float)
            rr = np.diff(np.log(px), prepend=np.nan)
            nxt = np.concatenate([rr[2:], [np.nan, np.nan]])
            contracts.append(reversion_contract(
                usd["resid_z"][pr_name], nxt, cards=[CARD_USD], start=train,
                label=f"{pr_name}:resid_vs_dollar_factor",
                falsifier=f"{pr_name} residual against the dollar factor does not revert"))
        for i in range(n):
            if not math.isfinite(usd["factor"][i]):
                continue
            row = {"available_time": clock[i].isoformat(), "event_time": dates[i].isoformat(),
                   "source_id": S_USD, "dollar_state": round(float(usd["factor"][i]), 8),
                   "dollar_state_sd": round(float(usd["factor_sd"][i]), 8),
                   "dollar_innovation_z": _r(usd["update_z"][i])}
            for pr_name, z in usd["resid_z"].items():
                row[f"{pr_name}_resid_z"] = _r(z[i])
            series_out[S_USD].append(row)
    else:
        contracts.append(se.contract(engine=ENGINE, cards=[CARD_USD], metric="kelly_growth_annual",
                                     baseline="ungated residual reversion",
                                     falsifier="pair residual vs dollar factor does not revert",
                                     value=None, baseline_value=None, n=0, why=usd["why"])
                         | {"label": "USD:pair_resid"})

    # ---- gold fair value
    dfii = asof(fred_daily(fred, "DFII10"), clock)
    be10 = asof(fred_daily(fred, "T10YIE"), clock)
    cols = [np.ones(n), dfii]
    names = ["const", "DFII10"]
    if usd["status"] == "MEASURED":
        cols.append(usd["factor"])
        names.append("dollar_factor")
    if np.isfinite(be10).sum() > train:
        cols.append(be10)
        names.append("T10YIE")
    gfv = gold_fair_value(logp, np.column_stack(cols), names, train)
    rep["gold"] = {k: v for k, v in gfv.items() if not isinstance(v, np.ndarray)}
    if gfv["status"] == "MEASURED":
        start = max(train, int(gfv["train_end_index"]))
        z = gfv["resid_z"]
        contracts.append(reversion_contract(
            z, r_next, cards=[CARD_GOLD], start=start, label="XAUUSD:gold_resid_vs_fair_value",
            falsifier="gold rich/cheap against its filtered macro fair value does not revert"))
        contracts.append(week_forecast_contract(logp, gfv["fair_value"], start))
        for i in range(n):
            if not math.isfinite(gfv["fair_value"][i]):
                continue
            series_out[S_GOLD].append({
                "available_time": clock[i].isoformat(), "event_time": dates[i].isoformat(),
                "source_id": S_GOLD, "gold_fair_value": round(float(gfv["fair_value"][i]), 8),
                "gold_gap": round(float(gfv["fair_value"][i] - logp[i]), 8),
                "gold_residual_z": _r(z[i]),
                **{f"beta_{nm}": round(float(gfv["betas"][i, k]), 8)
                   for k, nm in enumerate(names)}})
    else:
        for metric, lb in (("kelly_growth_annual", "XAUUSD:gold_resid"),
                           ("mse_reduction", "XAUUSD:next_week")):
            contracts.append(se.contract(engine=ENGINE, cards=[CARD_GOLD], metric=metric,
                                         baseline="ungated / random walk",
                                         falsifier="gold fair value residual has no content",
                                         value=None, baseline_value=None, n=0, why=gfv["why"])
                             | {"label": lb})

    # ---- inflation
    obs = {k: on_clock(v["rows"], clock) for k, v in pr.items()}
    for sid in ("T5YIE", "T10YIE"):
        if fred.get(sid):
            obs[sid] = on_clock(fred_daily(fred, sid), clock)
    infl = inflation_state(obs, train)
    rep["inflation"] = {k: v for k, v in infl.items() if not isinstance(v, np.ndarray)}
    contracts.append(cpi_contract(infl, train, cpi_min_n))
    if infl["status"] == "MEASURED":
        cpi_j = infl["inputs"].index("cpi") if "cpi" in infl["inputs"] else None
        for i in range(n):
            row = {"available_time": clock[i].isoformat(), "event_time": dates[i].isoformat(),
                   "source_id": S_INFL, "infl_state": round(float(infl["state"][i]), 8),
                   "infl_state_sd": round(float(infl["state_sd"][i]), 8),
                   "infl_innovation_z": _r(infl["update_z"][i])}
            if cpi_j is not None:
                row["cpi_print_z"] = _r(infl["innov_z"][i, cpi_j])
            series_out[S_INFL].append(row)
    rep.update({"status": "MEASURED", "series": series_out, "contracts": contracts,
                "rows": {k: len(v) for k, v in series_out.items()}})
    return rep


def _r(x: Any, nd: int = 6) -> float | None:
    v = float(x)
    return round(v, nd) if math.isfinite(v) else None


# ============================================================================== publish
def ledger_observations(rep: Mapping[str, Any], received_at: datetime) -> list[Any]:
    from libs.research import sensor_contract as sc
    out: list[Any] = []
    specs = ((S_INFL, "infl_state", "infl_innovation_z", ("XAUUSD",)),
             (S_USD, "dollar_state", "dollar_innovation_z", tuple(USD_PAIRS)),
             (S_GOLD, "gold_gap", "gold_residual_z", ("XAUUSD",)))
    for sid, metric, zcol, ents in specs:
        rows = (rep.get("series") or {}).get(sid) or []
        if not rows:
            continue
        last = rows[-1]
        if last.get(metric) is None:
            continue
        for ent in ents:
            out.append(sc.make(
                sensor_id=f"latent_states:{sid}", source_id=sid, metric=metric, kind="state",
                sensor_class="latent_state", entity=ent, value=last[metric],
                event_time=last["event_time"], knowable_at=last["available_time"],
                knowable_basis="declared_lag", received_at=received_at,
                parse_complete_at=received_at, surprise_z=last.get(zcol),
                licence="derived: broker bars, FRED public data",
                attributes={"filter": "kalman filtered, hyperparameters frozen on training"}))
    return out


def publish_all(rep: Mapping[str, Any], received_at: datetime) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, rows in (rep.get("series") or {}).items():
        out[sid] = se.write_lake_series(sid, rows)
    cells = [
        se.emit_conditioner_cells(
            S_GOLD, ["gold_residual_z"], METALS, sides=(-1,), generator=ENGINE,
            data_source="fred:DFII10",
            mechanism=("gold above its filtered macro fair value (real yield, dollar factor, "
                       "breakevens) is rich and mean-reverts toward it"),
            falsifier="gated residual-reversion gain <= 0 or p >= 0.05 (ROMAN-0841)"),
        se.emit_conditioner_cells(
            S_INFL, ["infl_state", "infl_innovation_z"], METALS, sides=(1, -1),
            generator=ENGINE, data_source="fred:T10YIE",
            mechanism="latent inflation pressure and its surprise reprice the metals' hedge",
            falsifier="the latent state does not forecast CPI (ROMAN-0839)"),
        se.emit_conditioner_cells(
            S_USD, ["dollar_state", "dollar_innovation_z"], tuple(USD_PAIRS), sides=(1, -1),
            generator=ENGINE, data_source="mt5:bars",
            mechanism="the common dollar factor and its surprise move every USD cross",
            falsifier="the factor's surprise carries no next-day content (ROMAN-0840)"),
    ]
    for pair in USD_PAIRS:
        cells.append(se.emit_conditioner_cells(
            S_USD, [f"{pair}_resid_z"], (pair,), sides=(-1,), generator=ENGINE,
            data_source="mt5:bars",
            mechanism=f"{pair} rich against the common dollar factor reverts toward it",
            falsifier=f"{pair} residual-reversion gated gain <= 0 (ROMAN-0840)"))
    out["cells"] = cells
    out["contracts_path"] = str(se.publish(ENGINE, rep.get("contracts") or [],
                                           extra={"inputs": rep.get("inputs")}))
    try:
        from libs.research import sensor_contract as sc
        out["ledger"] = sc.SensorLedger().append(ledger_observations(rep, received_at))
    except Exception as exc:                             # pragma: no cover - ledger guard
        out["ledger"] = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--now", default="", help="ISO UTC evaluation instant (default: now)")
    args = ap.parse_args(argv)
    now = _parse(args.now) or datetime.now(UTC)
    rep = build(now)
    verdicts = {v: sum(1 for c in rep["contracts"] if c["verdict"] == v)
                for v in (se.GAIN, se.NO_GAIN, se.UNMEASURED)}
    summary = {k: v for k, v in rep.items() if k != "series"}
    summary["verdicts"] = verdicts
    if not args.dry_run:
        summary["published"] = publish_all(rep, datetime.now(UTC))
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(summary, indent=1, default=str) + "\n", "utf-8")
    print(f"{ENGINE} status={rep.get('status')} rows={rep.get('rows')} verdicts={verdicts} "
          f"why={rep.get('why', '')} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
