"""Carry-crash hazard: a TWO-SIDED capital modifier for the carry family, armed only on proof.

THE MECHANISM (footprint sweep 2026-11-03, row 7 / A21). Carry trades crash when a crowded
funding short is forced to cover. The crowding is visible in point-in-time data the desk already
holds, and so is the trigger:

    crowding   CFTC TFF leveraged-fund net position in JPY futures, as a share of open interest.
               Very short JPY means the carry trade is crowded.
    trigger    the 5-day change in VIX: a risk-off shock is what forces the cover.
    momentum   the carry book's own drawdown from its 63-day peak: an unwind already under way.

hazard = mean of the three z-scores, each oriented so that high = more crash risk.

TWO-SIDED, PER GROWTH GOVERNANCE RULE 2. The modifier LIFTS carry size when the hazard is in its
lowest tercile, as well as cutting it in the highest. The pair (cut, lift) is chosen per
walk-forward fold from a small grid that includes (1, 1), so "do nothing" is always a
candidate and is selected
whenever the hazard says nothing in the training block. Every grid point is a charged trial.

RULE 1: IT TOUCHES NO SIZING UNTIL IT PROVES ROBUST FORWARD E[log W] RISES. `prove()` scores the
modified against the unmodified carry book on folds the multiplier never saw, at the growth-
optimal fraction fitted on the training block, and arms only when
  - there are at least MIN_OOS_DAYS out-of-sample days,
  - the per-day log-growth difference has a stationary block-bootstrap 5% lower bound above 0
    with the grid's trial count charged (Bonferroni on the one-sided alpha),
  - and the difference is not negative at 3x costs.
Otherwise the multiplier is 1.0 and the report carries what NOT arming costs, as its missed-
growth line, so the rail that keeps it disarmed is itself measured.

POINT IN TIME. COT is as of Tuesday and published Friday 15:30 ET, so a report is usable from
report_date + 4 days. VIX is used from the day after its print. The carry drawdown uses returns
through the previous day. Every input is therefore known before the day it conditions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

#: (cut multiplier in the top tercile, lift multiplier in the bottom tercile). (1, 1) is "no
#: modifier" and is always a candidate. Each pair is one trial and is charged in the proof.
GRID: tuple[tuple[float, float], ...] = (
    (1.0, 1.0), (0.5, 1.0), (1.0, 1.5), (0.5, 1.5), (0.0, 1.5), (0.5, 2.0))
COT_PUBLICATION_LAG_DAYS = 4
COT_Z_WEEKS = 156
VIX_CHANGE_DAYS = 5
VIX_Z_DAYS = 252
DD_PEAK_DAYS = 63
DD_Z_DAYS = 252
MIN_TRAIN_DAYS = 500
N_FOLDS = 5
MIN_OOS_DAYS = 250
BOOT_N = 2000
BOOT_BLOCK = 20
ALPHA = 0.05
F_GRID = np.linspace(0.0, 0.05, 51)  # fraction of equity per 1R


def _z(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    m = s.rolling(window, min_periods=min_periods).mean()
    sd = s.rolling(window, min_periods=min_periods).std()
    return (s - m) / sd.replace(0.0, np.nan)


def cot_crowding(cot: pd.DataFrame, days: pd.DatetimeIndex) -> pd.Series:
    """-z(lev-fund net / OI) on `days` from report_date + publication lag. High = crowded short."""
    if cot is None or cot.empty or not {"report_date", "lm_l", "lm_s", "oi"} <= set(cot.columns):
        return pd.Series(np.nan, index=days)
    c = cot.copy()
    c["report_date"] = pd.to_datetime(c["report_date"], utc=True).dt.tz_localize(None)
    c = c.sort_values("report_date").drop_duplicates("report_date", keep="last")
    oi = pd.to_numeric(c["oi"], errors="coerce").replace(0.0, np.nan)
    lm_l = pd.to_numeric(c["lm_l"], errors="coerce")
    net = (lm_l - pd.to_numeric(c["lm_s"], errors="coerce")) / oi
    z = -_z(pd.Series(net.to_numpy(), index=c["report_date"].to_numpy()), COT_Z_WEEKS, 52)
    z.index = pd.DatetimeIndex(z.index) + pd.Timedelta(days=COT_PUBLICATION_LAG_DAYS)
    return z.reindex(days.union(z.index)).sort_index().ffill().reindex(days)


def vix_shock(vix: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    """z of the 5-day log change in VIX, usable the day after its print. High = risk-off shock."""
    if vix is None or vix.dropna().empty:
        return pd.Series(np.nan, index=days)
    v = vix.dropna().astype(float)
    v = v[v > 0].sort_index()
    ch = np.log(v).diff(VIX_CHANGE_DAYS)
    z = _z(ch, VIX_Z_DAYS, 60)
    z.index = pd.DatetimeIndex(z.index) + pd.Timedelta(days=1)
    return z.reindex(days.union(z.index)).sort_index().ffill(limit=5).reindex(days)


def carry_drawdown(r: pd.Series) -> pd.Series:
    """-z of the drawdown from the 63-day peak, through the PREVIOUS day. High = unwinding."""
    cum = r.fillna(0.0).cumsum()
    dd = cum - cum.rolling(DD_PEAK_DAYS, min_periods=10).max()
    return (-_z(dd, DD_Z_DAYS, 60)).shift(1)


def hazard(r: pd.Series, cot: pd.DataFrame | None, vix: pd.Series | None) -> pd.DataFrame:
    """The three oriented z-scores and their mean on the carry book's own days."""
    days = pd.DatetimeIndex(r.index)
    parts = pd.DataFrame({"crowding": cot_crowding(cot, days) if cot is not None
                          else pd.Series(np.nan, index=days),
                          "vix_shock": vix_shock(vix, days) if vix is not None
                          else pd.Series(np.nan, index=days),
                          "drawdown": carry_drawdown(r)}, index=days)
    parts["hazard"] = parts[["crowding", "vix_shock", "drawdown"]].mean(axis=1, skipna=True)
    return parts


def _growth(r: np.ndarray, f: float) -> np.ndarray:
    x = 1.0 + f * r
    return np.where(x > 0, np.log(np.maximum(x, 1e-12)), -50.0)


def growth_fraction(r: np.ndarray) -> float:
    """argmax mean log(1 + f r) over F_GRID: the growth-optimal fraction of equity per 1R."""
    if r.size == 0:
        return 0.0
    g = [float(np.mean(_growth(r, f))) for f in F_GRID]
    return float(F_GRID[int(np.argmax(g))])


def multipliers(h: np.ndarray, lo_edge: float, hi_edge: float, cut: float,
                lift: float) -> np.ndarray:
    m = np.ones_like(h, dtype=float)
    ok = np.isfinite(h)
    m[ok & (h >= hi_edge)] = cut
    m[ok & (h <= lo_edge)] = lift
    return m


def _boot_lb(d: np.ndarray, alpha: float, rng: np.random.Generator) -> float:
    """Stationary block-bootstrap lower `alpha` quantile of the mean of `d`."""
    n = d.size
    if n < 2:
        return float("nan")
    new = rng.random((BOOT_N, n)) < 1.0 / BOOT_BLOCK
    new[:, 0] = True
    pos = np.where(new, np.arange(n)[None, :], 0)
    first = np.maximum.accumulate(pos, axis=1)                  # where the current block began
    starts = rng.integers(n, size=(BOOT_N, n))
    start_of = np.take_along_axis(starts, first, axis=1)
    idx = (start_of + (np.arange(n)[None, :] - first)) % n
    return float(np.quantile(d[idx].mean(axis=1), alpha))


@dataclass
class Proof:
    armed: bool
    reason: str
    oos_days: int = 0
    trials: int = len(GRID)
    delta_elog_per_day: float | None = None
    delta_elog_per_day_3x: float | None = None
    lower_bound: float | None = None
    folds: list[dict[str, Any]] = field(default_factory=list)
    cut: float = 1.0
    lift: float = 1.0
    lo_edge: float | None = None
    hi_edge: float | None = None
    f_star: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _fit(h: np.ndarray, r: np.ndarray) -> tuple[float, float, float, float, float, float]:
    """Edges, the unmodified growth fraction, and the best (cut, lift) with ITS OWN growth
    fraction, on one training block. Each book is sized at its own optimum, so the comparison is
    E[log W] against E[log W], never a modifier scored at a fraction fitted for something else."""
    hf = h[np.isfinite(h)]
    lo, hi = (float(np.quantile(hf, 1 / 3)), float(np.quantile(hf, 2 / 3))) if hf.size >= 30 \
        else (-np.inf, np.inf)
    f0 = growth_fraction(r)
    best, best_f, best_g = (1.0, 1.0), f0, float(np.mean(_growth(r, f0)))
    for cut, lift in GRID:
        rm = r * multipliers(h, lo, hi, cut, lift)
        f = growth_fraction(rm)
        g = float(np.mean(_growth(rm, f)))
        if g > best_g + 1e-12:
            best, best_f, best_g = (cut, lift), f, g
    return lo, hi, f0, best_f, best[0], best[1]


def prove(r1: pd.Series, r3: pd.Series | None, haz: pd.Series, seed: int = 7) -> Proof:
    """Anchored walk-forward: fit on everything before each fold, score on the fold."""
    df = pd.DataFrame({"r1": r1, "h": haz}).dropna(subset=["r1"]).sort_index()
    if r3 is not None:
        df["r3"] = r3.reindex(df.index)
    n = len(df)
    if n < MIN_TRAIN_DAYS + MIN_OOS_DAYS:
        return Proof(False, f"UNMEASURED: {n} carry days, need {MIN_TRAIN_DAYS + MIN_OOS_DAYS}")
    if df["h"].notna().sum() < MIN_TRAIN_DAYS:
        return Proof(False, "UNMEASURED: hazard defined on too few days (inputs missing or stale)")
    edges = np.linspace(MIN_TRAIN_DAYS, n, N_FOLDS + 1).astype(int)
    d1: list[np.ndarray] = []
    d3: list[np.ndarray] = []
    folds: list[dict[str, Any]] = []
    for a, b in pairwise(edges):
        tr, te = df.iloc[:a], df.iloc[a:b]
        lo, hi, f0, fm, cut, lift = _fit(tr["h"].to_numpy(float), tr["r1"].to_numpy(float))
        m = multipliers(te["h"].to_numpy(float), lo, hi, cut, lift)
        r = te["r1"].to_numpy(float)
        d1.append(_growth(r * m, fm) - _growth(r, f0))
        if "r3" in te and te["r3"].notna().any():
            r_3 = te["r3"].fillna(0.0).to_numpy(float)
            d3.append(_growth(r_3 * m, fm) - _growth(r_3, f0))
        folds.append({"start": str(te.index[0].date()), "end": str(te.index[-1].date()),
                      "f_unmodified": f0, "f_modified": fm, "cut": cut, "lift": lift,
                      "delta": float(d1[-1].mean())})
    dd = np.concatenate(d1)
    lb = _boot_lb(dd, ALPHA / len(GRID), np.random.default_rng(seed))
    delta3 = float(np.concatenate(d3).mean()) if d3 else None
    lo, hi, _f0, f, cut, lift = _fit(df["h"].to_numpy(float), df["r1"].to_numpy(float))
    p = Proof(False, "", oos_days=int(dd.size), delta_elog_per_day=float(dd.mean()),
              delta_elog_per_day_3x=delta3, lower_bound=lb, folds=folds, cut=cut, lift=lift,
              lo_edge=lo if math.isfinite(lo) else None,
              hi_edge=hi if math.isfinite(hi) else None, f_star=f)
    if dd.size < MIN_OOS_DAYS:
        p.reason = f"UNMEASURED: {dd.size} out-of-sample days, need {MIN_OOS_DAYS}"
    elif (cut, lift) == (1.0, 1.0):
        p.reason = "the full-sample fit selects no modifier: the hazard says nothing here"
    elif not (lb > 0):
        p.reason = (f"NOT PROVEN: OOS gain {dd.mean():.3g}/day, bootstrap lower bound {lb:.3g} "
                    f"at alpha {ALPHA}/{len(GRID)} trials")
    elif delta3 is not None and delta3 < 0:
        p.reason = f"NOT PROVEN: the gain turns negative at 3x costs ({delta3:.3g}/day)"
    else:
        p.armed = True
        p.reason = "PROVEN: OOS E[log W] gain with a positive charged lower bound"
    return p


def current(haz: pd.DataFrame, proof: Proof) -> dict[str, Any]:
    """Today's reading: the category and the multiplier the sizing layer may apply (1.0 unarmed)."""
    last = haz.dropna(subset=["hazard"])
    if last.empty or proof.lo_edge is None or proof.hi_edge is None:
        return {"hazard": None, "category": "UNMEASURED", "multiplier": 1.0,
                "proposed_multiplier": 1.0}
    h = float(last["hazard"].iloc[-1])
    if h >= proof.hi_edge:
        cat, prop = ("STRONG_VETO" if proof.cut == 0 else "REDUCE"), proof.cut
    elif h <= proof.lo_edge:
        cat, prop = ("STRONG_BOOST" if proof.lift >= 2 else "BOOST"), proof.lift
    else:
        cat, prop = "NORMAL", 1.0
    if prop == 1.0:
        cat = "NORMAL"
    return {"hazard": h, "as_of": str(last.index[-1].date()),
            "parts": {k: (None if pd.isna(v) else float(v))
                      for k, v in last[["crowding", "vix_shock", "drawdown"]].iloc[-1].items()},
            "category": cat, "proposed_multiplier": prop,
            "multiplier": prop if proof.armed else 1.0}
