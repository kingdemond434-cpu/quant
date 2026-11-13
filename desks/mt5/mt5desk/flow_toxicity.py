"""Signed flow, toxicity, impact and spread regime from the venue's own quote tape. Pure arithmetic.

WHAT THIS ADDS, AND WHAT IT DELIBERATELY DOES NOT REPEAT. `mt5desk/microstructure.py` already owns
the per-hour COST side of the tape (effective and realised spread, mid drift after a fill, quote
intensity, the sign-only revision imbalance, the realised/bipower split). What the desk lacked --
named in `desks/mt5/docs/CAPABILITY_AUDIT.md` ("Microstructure features (OBI, book, toxicity):
MISSING, queued (Fincept)") -- is the INFORMATION side: who is pressing, how informed the pressing
looks, how much price a unit of pressing buys, and which spread regime the venue is in. These are
the classic market-microstructure constructions, re-implemented here from the literature; no code
from any terminal product was copied (Fincept Terminal is AGPL-3.0-or-later, so the desk cites it
as the prompt and copies nothing; see `libs.data.datahub.copy_allowed`).

  TICK-RULE SIGNED FLOW (Lee-Ready tick test). Each mid revision is signed by its direction; a
      revision that leaves the mid unchanged INHERITS the previous sign, which is the tick test's
      zero-tick rule and the difference from `orthogonal_sweep._tape_series`'s flow (that one
      scores a zero tick as 0). Two numbers per bar: the carried sum and the moves-only imbalance.
  QUOTE IMBALANCE. On a venue with per-side size this is (bid size - ask size) / total. Fusion
      publishes no depth (`data/tape/depth_probe.json`: 22 of 22 symbols NO_DEPTH) and no per-side
      tick size, so the column is the Cont-Kyle-Stoikov SIGN-ONLY revision imbalance per bar, and
      `quote_imbalance_basis` says "sign_only" on every row. It never fabricates a size.
  VPIN-STYLE TOXICITY (Easley-Lopez de Prado-O'Hara, bulk volume classification). The day's
      quote revisions are cut into equal-COUNT buckets (a CFD tape has no traded volume, so the
      count of revisions is the activity clock -- stated, not hidden). Each bucket's mid change is
      standardised by the TRAILING standard deviation of earlier buckets only (point-in-time: no
      bucket is scaled by a later one), the buy share is Phi(z), and the bucket's order imbalance
      is |2 Phi(z) - 1|. VPIN is the mean imbalance over a trailing window of buckets.
  KYLE-LAMBDA-STYLE IMPACT. The rolling OLS slope of the bar's own mid change (points) on its
      tick-rule flow: price moved per unit of net signed revisions. High lambda = thin, informed
      market; low lambda = deep, uninformed.
  SPREAD REGIME. The bar's mean quoted spread ranked against its own trailing window
      (percentile in [0, 1]); 1 = the widest the venue has quoted recently.

HONESTY RULES (enforced in code):
  1. A bar with fewer than MIN_TICKS_BAR revisions states NO derived number (NaN) -- UNMEASURED.
  2. Units are points; `point` is always passed in and never guessed.
  3. Every derived value is computed only from the bar itself and earlier bars, so the series can
     be stamped `available_time = bar close` and joined point-in-time.
  4. The two-stage split (additive per-bar AGGREGATES, then DERIVED rolling columns) is what lets
     the series accumulate past the tape's retention window: aggregates are recomputed per day
     and merged; the derivation is re-run over the whole accumulated history.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

#: Below this many quote revisions a bar states no derived number.
MIN_TICKS_BAR = 30
#: Buckets of BVC needed before a bucket's z-score is defined (trailing sigma). Below it: NaN.
BVC_MIN_SIGMA_BUCKETS = 10
#: Trailing buckets the sigma is measured over.
BVC_SIGMA_WINDOW = 50
#: Bars the VPIN mean is taken over (the bucket imbalances inside them, count-weighted).
VPIN_BARS = 24
#: Bars the Kyle-lambda regression is fitted on, and its minimum.
LAMBDA_BARS = 48
LAMBDA_MIN_BARS = 24
#: Bars the spread regime is ranked against, and its minimum.
REGIME_BARS = 240
REGIME_MIN_BARS = 24

#: The additive per-bar columns. Two partial days for the same bar sum correctly.
AGG_COLUMNS: tuple[str, ...] = (
    "n_ticks", "n_moves", "tr_flow", "tr_flow_moves", "ofi_sum", "spread_sum_pts", "spread_n",
    "path_pts", "bvc_oi_sum", "bvc_n")
#: The derived columns a conditioner may read. Each is a candidate signal for the judge.
SIGNAL_COLUMNS: tuple[str, ...] = (
    "tick_rule_imbalance", "quote_imbalance", "vpin", "signed_vpin", "kyle_lambda",
    "spread_regime_rank", "tick_intensity")


def tick_rule_signs(mid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(carried sign per revision, moved mask). Revision 0 has no predecessor and scores 0.

    The tick test: up-tick +1, down-tick -1, zero-tick inherits the last non-zero sign (0 until
    the first move). Returned per revision, aligned with `mid` (length n).
    """
    n = len(mid)
    out = np.zeros(n, dtype=np.float64)
    moved = np.zeros(n, dtype=bool)
    if n < 2:
        return out, moved
    d = np.diff(np.asarray(mid, dtype=np.float64))
    raw = np.sign(d)
    moved[1:] = raw != 0
    # forward-fill the last non-zero sign: index of the last move at or before each position
    s = pd.Series(np.where(raw != 0, raw, np.nan))
    out[1:] = s.ffill().fillna(0.0).to_numpy()
    return out, moved


def _phi(z: np.ndarray) -> np.ndarray:
    from scipy.special import ndtr
    return np.asarray(ndtr(z), dtype=np.float64)


def bvc_buckets(mid: np.ndarray, bucket_ticks: int) -> tuple[np.ndarray, np.ndarray]:
    """(bucket order imbalance |2 Phi(z) - 1|, index of each bucket's LAST revision).

    Buckets are consecutive runs of `bucket_ticks` revisions; a trailing partial bucket is
    dropped (it is not a bucket yet). z = bucket mid change / trailing sigma of EARLIER buckets'
    changes, so no bucket is scaled by information from after it. NaN where sigma is undefined.
    """
    v = max(2, int(bucket_ticks))
    n = len(mid) // v
    if n < 1:
        return np.empty(0), np.empty(0, dtype=np.int64)
    m = np.asarray(mid, dtype=np.float64)
    ends = np.arange(1, n + 1) * v - 1
    starts = ends - v + 1
    dp = m[ends] - m[starts]
    prev = pd.Series(dp).shift(1)
    sigma = prev.rolling(BVC_SIGMA_WINDOW, min_periods=BVC_MIN_SIGMA_BUCKETS).std(ddof=1)
    sig = sigma.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where((sig > 0) & np.isfinite(sig), dp / sig, np.nan)
    oi = np.where(np.isfinite(z), np.abs(2.0 * _phi(np.nan_to_num(z)) - 1.0), np.nan)
    return oi, ends


def bar_aggregates(ticks: pd.DataFrame, point: float, *, rule: str = "1h",
                   bucket_ticks: int = 50) -> pd.DataFrame:
    """Additive per-bar aggregates from one span of ticks (`ts`, `bid`, `ask`; ts UTC).

    Index: the bar START (UTC). Rows without a two-sided quote are dropped, never zero-filled.
    """
    if point <= 0:
        raise ValueError("point must be positive: the unit is never guessed")
    empty = pd.DataFrame(columns=list(AGG_COLUMNS), dtype=np.float64)
    if ticks is None or ticks.empty:
        return empty
    t = ticks[["ts", "bid", "ask"]].copy()
    t["ts"] = pd.to_datetime(t["ts"], utc=True, errors="coerce")
    t = t.dropna()
    t = t[(t["bid"] > 0) & (t["ask"] > 0)]
    if t.empty:
        return empty
    t = t.drop_duplicates().sort_values("ts", kind="mergesort").reset_index(drop=True)
    mid = ((t["bid"] + t["ask"]) / 2.0).to_numpy(dtype=np.float64)
    spread_pts = ((t["ask"] - t["bid"]) / point).to_numpy(dtype=np.float64)
    sign, moved = tick_rule_signs(mid)
    bid = t["bid"].to_numpy(dtype=np.float64)
    ask = t["ask"].to_numpy(dtype=np.float64)
    ofi = np.zeros(len(t), dtype=np.float64)
    if len(t) > 1:
        # Cont-Kyle-Stoikov sign-only: bid up or ask up = buy pressure (see
        # microstructure.order_flow_imbalance for why the ask term ADDS).
        ofi[1:] = np.sign(np.diff(bid)) + np.sign(np.diff(ask))
    dmid_abs = np.zeros(len(t), dtype=np.float64)
    if len(t) > 1:
        dmid_abs[1:] = np.abs(np.diff(mid)) / point
    bar = t["ts"].dt.floor(rule)
    frame = pd.DataFrame({
        "bar": bar, "n_ticks": 1.0, "n_moves": moved.astype(np.float64),
        "tr_flow": sign, "tr_flow_moves": np.where(moved, sign, 0.0), "ofi_sum": ofi,
        "spread_sum_pts": spread_pts, "spread_n": 1.0, "path_pts": dmid_abs,
        "mid_first": mid, "mid_last": mid})
    g = frame.groupby("bar", sort=True)
    agg = g[["n_ticks", "n_moves", "tr_flow", "tr_flow_moves", "ofi_sum", "spread_sum_pts",
             "spread_n", "path_pts"]].sum()
    agg["mid_open"] = g["mid_first"].first()
    agg["mid_close"] = g["mid_last"].last()
    oi, ends = bvc_buckets(mid, bucket_ticks)
    agg["bvc_oi_sum"] = 0.0
    agg["bvc_n"] = 0.0
    if len(oi):
        ok = np.isfinite(oi)
        if ok.any():
            b = pd.DataFrame({"bar": bar.to_numpy()[ends[ok]], "oi": oi[ok]})
            gb = b.groupby("bar")["oi"]
            agg.loc[gb.sum().index, "bvc_oi_sum"] = gb.sum().to_numpy()
            agg.loc[gb.count().index, "bvc_n"] = gb.count().to_numpy().astype(np.float64)
    agg.index = pd.DatetimeIndex(agg.index, name="bar")
    return agg


def merge_aggregates(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Replace every bar `new` covers with `new`'s row; keep the rest of `old`. Sorted."""
    if old is None or old.empty:
        return new.sort_index()
    if new.empty:
        return old.sort_index()
    keep = old.loc[~old.index.isin(new.index)]
    return pd.concat([keep, new]).sort_index()


def derive(agg: pd.DataFrame, point: float, *, rule: str = "1h") -> pd.DataFrame:
    """The signal columns over the accumulated aggregates, each from this bar and earlier ones."""
    if agg is None or agg.empty:
        return pd.DataFrame(columns=[*SIGNAL_COLUMNS, "available_time"])
    a = agg.sort_index().copy()
    measured = a["n_ticks"] >= MIN_TICKS_BAR
    out = pd.DataFrame(index=a.index)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["tick_rule_imbalance"] = np.where(a["n_moves"] > 0,
                                              a["tr_flow_moves"] / a["n_moves"], np.nan)
        out["quote_imbalance"] = np.where(a["n_ticks"] > 1,
                                          a["ofi_sum"] / (2.0 * (a["n_ticks"] - 1)), np.nan)
        out["spread_mean_pts"] = np.where(a["spread_n"] > 0,
                                          a["spread_sum_pts"] / a["spread_n"], np.nan)
    out["quote_imbalance_basis"] = "sign_only"
    out["tick_intensity"] = a["n_ticks"].astype(np.float64)
    oi_sum = a["bvc_oi_sum"].rolling(VPIN_BARS, min_periods=1).sum()
    oi_n = a["bvc_n"].rolling(VPIN_BARS, min_periods=1).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        vpin = np.where(oi_n >= BVC_MIN_SIGMA_BUCKETS, oi_sum / oi_n, np.nan)
    out["vpin"] = vpin
    out["signed_vpin"] = out["vpin"] * np.sign(out["tick_rule_imbalance"])
    dmid = (a["mid_close"] - a["mid_open"]) / point
    flow = a["tr_flow_moves"].where(measured)
    dm = dmid.where(measured)
    cov = dm.rolling(LAMBDA_BARS, min_periods=LAMBDA_MIN_BARS).cov(flow)
    var = flow.rolling(LAMBDA_BARS, min_periods=LAMBDA_MIN_BARS).var()
    out["kyle_lambda"] = (cov / var.where(var > 0)).replace([np.inf, -np.inf], np.nan)
    sp = out["spread_mean_pts"].where(measured)
    out["spread_regime_rank"] = sp.rolling(REGIME_BARS, min_periods=REGIME_MIN_BARS).rank(pct=True)
    for c in ("tick_rule_imbalance", "quote_imbalance", "spread_mean_pts", "vpin",
              "signed_vpin", "kyle_lambda", "spread_regime_rank"):
        out[c] = pd.to_numeric(out[c], errors="coerce").where(measured)
    out["tick_intensity"] = out["tick_intensity"].where(measured)
    step = pd.Timedelta(rule)
    out["event_time"] = out.index
    out["available_time"] = out.index + step
    return out


def series_frame(agg: pd.DataFrame, point: float, *, rule: str = "1h") -> pd.DataFrame:
    """The one file a conditioner reads: aggregates + derived columns + the PIT stamp."""
    der = derive(agg, point, rule=rule)
    if agg is None or agg.empty:
        return der
    return agg.join(der, how="left")


def default_bucket_ticks(ticks_per_bar: float) -> int:
    """A bucket of about a tenth of a typical bar's revisions, never under 20."""
    if not math.isfinite(ticks_per_bar) or ticks_per_bar <= 0:
        return 50
    return max(20, round(ticks_per_bar / 10.0))
