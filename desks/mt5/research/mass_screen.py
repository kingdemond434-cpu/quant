"""THE MASS SCREEN: generate and cheaply screen rule cells by the million, forward FDR survivors.

WHY IT EXISTS (measured on the trading box 2026-09-30). The desk creates ~8,300 cells a day and
the sealed ten-gate gauntlet judges ~5,300 at ~22 s of build each; 1.40M sit unjudged, and 43% of
a week's verdicts came back UNKNOWN (too few trading days to rule on). The judge is the scarce
resource, and it was being spent on cells nobody had looked at even once. This stage is the cheap
look: a vectorised grammar of rules over bar-derived features x symbols x horizons x thresholds x
sides, evaluated in bulk with numpy on H1 bars loaded once per symbol, at tens of thousands of
cells per core-second -- and only the survivors of a within-screen FDR control, deduplicated by
the days they trade, go to the judge.

WHAT IS SCREENED, AND ON WHICH DATA. Each cell's net-of-cost R (the engine's own R: next-bar-open
entry, ATR stop from the signal bar's close, time exit at the open `hold` bars later, the same
single-position thinning, spread x commission x swap priced exactly as `engine.Costs` prices them,
the spread taken as the WORSE of the registry median and the bars' own measured spread at the fill
hour) is summed per entry day like the gauntlet's daily series. Statistics are taken ONLY on a
training window that ends at the EARLIER of
  * TRAIN_FRAC of the symbol's calendar history, and
  * the first day of the cell's own walk-forward test region as the sealed gauntlet will cut it
    (`WalkForwardEngine.evaluate(n_splits=WF_SPLITS, test_size=max(20, N // 6))`, anchored: the
    last WF_SPLITS x test_size active days), which is also where its `lockbox` gate reads,
so the out-of-sample gates are never screened on. (The in-sample gates -- DSR, CPCV, PBO -- span
the whole series by construction; that overlap is inherent to any pre-screen and is why the screen
has zero promotion authority.)

WHAT IS FORWARDED. A cell must have >= MIN_DAYS (the gauntlet's 60-day CPCV/walk-forward floor)
trading days INSIDE the training window alone -- so it cannot come back UNKNOWN -- must pass
Benjamini-Hochberg at FDR_Q across EVERY cell screened in the run (m counts the untestable cells
too, the conservative direction), must stay positive at the gauntlet's 3x spread stress, and must
not trade substantially the same days as a stronger survivor on the same symbol and side
(Jaccard >= DEDUP_JACCARD). Survivors go through the registry's one door
(`libs.moat.registry.enqueue_candidate`), from which `libs.moat.docket_feed` carries them into
`data/hypotheses/external_survivors.json`, the file the sealed gauntlet reads. Each is rebuilt
there by `mt5desk.mass_screen_rules.family_mass_screen_rule`, the same code that computed the
screen's signals.

MULTIPLICITY IS CHARGED, NEVER SKIPPED. Every screened cell -- including the ones that never had
60 days -- is a trial. Each run appends per-grammar counts to `data/MASS_SCREEN_TRIALS.jsonl`,
which `libs.research.experiment_ledger` sums into `EXPERIMENT_LEDGER.json` (lifetime and
per-family trials), the ledger the gauntlet reports beside its sealed charge and
`pf_allocator.search_trials` uses for the winner's-curse shrinkage.

NOTHING HERE REDUCES EXISTING MINING, caps a producer or lowers a gate.

    python desks/mt5/research/mass_screen.py --once --budget-s 900
    python desks/mt5/research/mass_screen.py --once --dry-run --symbols EURUSD,XAUUSD --out-dir X
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import mass_screen_rules as MR  # noqa: E402

DATA = DESK / "data"
UNIVERSE = DATA / "universe"
REPORT = DESK / "reports" / "MASS_SCREEN.json"
#: THE TRIAL LEDGER the effective/lifetime-trials machinery reads (libs/research/experiment_ledger).
TRIALS = DATA / "MASS_SCREEN_TRIALS.jsonl"
RUNS = DATA / "mass_screen_runs.jsonl"
CURSOR = DATA / "mass_screen_cursor.json"
FORWARDED = DATA / "mass_screen_forwarded.json"
UNMEASURED = "UNMEASURED"
ORIGIN = "mass_screen"

#: Share of each symbol's calendar history the screen may look at (then clipped per cell to the
#: start of its walk-forward test region).
TRAIN_FRAC = 0.30
#: The sealed gauntlet's walk-forward cut, mirrored (external_gauntlet.WF_SPLITS and its
#: `test_size=max(20, len(arr) // 6)`); test_mass_screen pins these against the sealed source.
WF_SPLITS = 4
WF_MIN_TEST = 20
WF_TEST_DIV = 6
#: The gauntlet's 60-observation floor (CPCV + walk-forward); required INSIDE the training window.
MIN_DAYS = 60
#: The gauntlet's cost stress (external_gauntlet.COST_SCENARIO): spread x3.
COST_STRESS = 3.0
#: Within-screen false-discovery rate (Benjamini-Hochberg over every cell in the run).
FDR_Q = 0.05
#: Two survivors on one symbol and side that share this share of their trading days are one bet.
DEDUP_JACCARD = 0.5
#: Axes of the grammar.
HORIZONS = (1, 2, 4, 8, 12, 24, 48)
STOPS = (1.0, 2.5)
QUANTILES = ((0.05, "lt"), (0.10, "lt"), (0.20, "lt"), (0.80, "gt"), (0.90, "gt"), (0.95, "gt"))
TERCILE_Q = (1.0 / 3.0, 2.0 / 3.0)
SESSIONS = ((0, 8), (8, 13), (13, 17), (17, 24))
CLOCK_WEEKDAYS = (-1, 0, 1, 2, 3, 4)
CARRY_HOURS = (0, 8, 16)
LEADERS = ("XAUUSD", "EURUSD", "USDJPY", "US500", "XTIUSD", "NAS100", "UST10Y", "GER40")
#: Variants evaluated per (condition, horizon): (direction, stop_atr).
VARIANTS = tuple((d, k) for d in (1, -1) for k in STOPS)
#: Memory one worker is allowed to assume it holds (features + R arrays of one symbol). Used only
#: to derive the worker count from MEASURED free memory, never to size anything else.
WORKER_MB = 700
NS_DAY = 86_400 * 10**9


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------------------------
# universe, costs
# --------------------------------------------------------------------------------------------
_META: dict[str, Any] | None = None


def universe_meta() -> dict[str, Any]:
    global _META
    if _META is None:
        try:
            raw = json.loads((UNIVERSE / "universe.json").read_text("utf-8"))
            _META = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            _META = {}
    return _META


def hypothesis_symbols() -> list[str]:
    """Every symbol with H1 bars that the TWO-LANE law lets the desk hunt statistically.

    Routing is by asset class through `universe_policy.may_hypothesise`: single-name equities are
    the event lane and are never screened here; an unclassified symbol is hunted by nothing."""
    have = sorted(p.name[:-len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet"))
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return []
    out = []
    for s in have:
        try:
            if may_hypothesise(s):
                out.append(s)
        except Exception:
            continue
    return out


def cost_model(meta: dict[str, Any]) -> dict[str, float]:
    """The pieces of `engine.Costs.from_symbol`, so the screen can price a per-bar spread."""
    from mt5desk.engine import Costs
    c0 = Costs.from_symbol(meta or {})
    cs = float(c0.contract_oz) or 1.0
    return {"cs": cs, "ts": float((meta or {}).get("tick_size", 0.0) or 0.0),
            "median_pts": float((meta or {}).get("median_spread_pts", 0.0) or 0.0),
            "comm_price": 2.0 * float(c0.commission_per_lot) * float(c0.quote_per_account) / cs,
            "swap_price": float(c0.swap_per_lot_per_night) / cs}


def nights_between(a_ns: np.ndarray, b_ns: np.ndarray) -> np.ndarray:
    """`engine.rollovers_between`, vectorised: rollover instants strictly after a and at or
    before b, the triple-swap weekday counting three."""
    from mt5desk.engine import ROLLOVER_HOUR_UTC, TRIPLE_SWAP_WEEKDAY
    off = ROLLOVER_HOUR_UTC * 3600 * 10**9
    da = np.floor_divide(a_ns - off, NS_DAY)
    db = np.floor_divide(b_ns - off, NS_DAY)
    k = np.maximum(db - da, 0)
    # day d (days since 1970-01-01, a Thursday) has weekday (d + 3) % 7.
    r = (TRIPLE_SWAP_WEEKDAY - 3) % 7
    trip = np.floor_divide(db - r, 7) - np.floor_divide(da - r, 7)
    return (k + 2 * np.where(k > 0, trip, 0)).astype("float64")


# --------------------------------------------------------------------------------------------
# one symbol, prepared once
# --------------------------------------------------------------------------------------------
class Prepared:
    """Bars, features, and the per-(horizon, variant) net R arrays of ONE symbol."""

    def __init__(self, symbol: str, df, meta: dict[str, Any] | None = None,
                 leaders: dict[str, Any] | None = None, *, use_bar_spread: bool = True):
        import pandas as pd
        self.symbol = symbol
        df = MR._h1(df)
        self.df = df
        self.n = n = len(df)
        self.t_ns = np.asarray(pd.DatetimeIndex(df.index).as_unit("ns").asi8, dtype="int64")
        self.feats = MR.features(df)
        self.lead: dict[str, dict[str, np.ndarray]] = {}
        for name, frame in (leaders or {}).items():
            if frame is not None and name.upper() != symbol.upper():
                lf = MR.lead_features(df, frame)
                if lf:
                    self.lead[name] = lf
        self.hour, self.wd = MR.clock_arrays(df)
        o = df["open"].to_numpy("float64")
        hi = df["high"].to_numpy("float64")
        lo = df["low"].to_numpy("float64")
        c = df["close"].to_numpy("float64")
        atr = MR._atr(df, 20).to_numpy("float64")
        self.valid = np.isfinite(atr) & (atr > 0) & np.isfinite(c)
        t0, t1 = self.t_ns[0], self.t_ns[-1]
        self.cut = int(np.searchsorted(self.t_ns, t0 + int(TRAIN_FRAC * (t1 - t0))))
        # entry day of a fire at bar i is the day of bar i + 1
        self.entry_day = MR.entry_days(self.t_ns)
        cm = cost_model(meta or {})
        self.costs = cm
        pts = np.full(n, cm["median_pts"], dtype="float64")
        if use_bar_spread and "spread" in df.columns and self.cut > 24:
            sp = df["spread"].to_numpy("float64")[: self.cut]
            hr = self.hour[: self.cut]
            by_hour = np.full(24, np.nan)
            for hh in range(24):
                v = sp[(hr == hh) & np.isfinite(sp)]
                if v.size:
                    by_hour[hh] = float(np.median(v))
            fill_hour = np.empty(n, dtype="int64")
            fill_hour[:-1] = self.hour[1:]
            fill_hour[-1] = self.hour[-1]
            hs = by_hour[fill_hour]
            pts = np.where(np.isfinite(hs), np.maximum(pts, hs), pts)
        spread_x1 = np.maximum(pts * cm["ts"] * cm["cs"], 0.05) / cm["cs"]
        spread_x3 = np.maximum(pts * cm["ts"] * cm["cs"] * COST_STRESS, 0.05) / cm["cs"]
        self.R1: dict[int, np.ndarray] = {}
        self.R3: dict[int, np.ndarray] = {}
        V = len(VARIANTS)
        for h in HORIZONS:
            r1 = np.full((V, n), np.nan)
            r3 = np.full((V, n), np.nan)
            m = n - 1 - h          # fires i in [0, m): entry i+1, exit open i+1+h <= n-1
            if m <= 0:
                self.R1[h], self.R3[h] = r1, r3
                continue
            i = np.arange(m)
            entry = o[1: m + 1]
            exitp = o[1 + h: m + 1 + h]
            win_lo = np.lib.stride_tricks.sliding_window_view(lo[1:], h)[:m].min(axis=1)
            win_hi = np.lib.stride_tricks.sliding_window_view(hi[1:], h)[:m].max(axis=1)
            nights = nights_between(self.t_ns[1: m + 1], self.t_ns[1 + h: m + 1 + h])
            fin = nights * cm["swap_price"]
            for vi, (d, k) in enumerate(VARIANTS):
                stop = c[:m] - d * k * atr[:m]
                sd = np.abs(entry - stop)
                hit = (win_lo <= stop) if d > 0 else (win_hi >= stop)
                px = np.where(hit, stop, exitp)
                with np.errstate(divide="ignore", invalid="ignore"):
                    gross = d * (px - entry) / sd
                    r1[vi, :m] = gross - (spread_x1[:m] + cm["comm_price"] + fin) / sd
                    r3[vi, :m] = gross - (spread_x3[:m] + cm["comm_price"] + fin) / sd
                bad = ~(sd > 0) | ~np.isfinite(entry) | ~np.isfinite(exitp)
                r1[vi, :m][bad] = np.nan
                r3[vi, :m][bad] = np.nan
            del i
            self.R1[h], self.R3[h] = r1, r3

    def feature(self, name: str, leader: str = "") -> np.ndarray | None:
        if leader:
            return (self.lead.get(leader) or {}).get(name)
        return self.feats.get(name)

    def mask(self, cond: dict[str, Any]) -> np.ndarray:
        feats = self.feats
        if cond.get("leader"):
            feats = {**self.feats, **self.lead.get(cond["leader"], {})}
        m = MR.condition_mask(feats, self.hour, self.wd, feat=cond.get("feat", ""),
                              op=cond.get("op", "gt"), thr=cond.get("thr", 0.0),
                              cond_feat=cond.get("cond_feat", ""),
                              cond_lo=cond.get("cond_lo", -MR.OPEN_BOUND),
                              cond_hi=cond.get("cond_hi", MR.OPEN_BOUND),
                              hour=cond.get("hour", -1), weekday=cond.get("weekday", -1))
        return m & self.valid


def _q(a: np.ndarray, q: float) -> float | None:
    v = a[np.isfinite(a)]
    if v.size < 200:
        return None
    return float(f"{float(np.quantile(v, q)):.6g}")


def carry_side(meta: dict[str, Any]) -> int:
    """+1 / -1 for the side whose recorded swap is POSITIVE, 0 when neither pays."""
    sl = float((meta or {}).get("swap_long", 0.0) or 0.0)
    ss = float((meta or {}).get("swap_short", 0.0) or 0.0)
    if max(sl, ss) <= 0:
        return 0
    return 1 if sl >= ss else -1


def conditions(P: Prepared, meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The symbol's grammar, deterministic in its order. Thresholds are quantiles of the TRAINING
    window only, rounded so the stored number is the number that fired."""
    cut = P.cut
    out: list[dict[str, Any]] = []
    base: list[dict[str, Any]] = []
    for f in MR.base_feature_names():
        a = P.feats[f][:cut]
        for q, op in QUANTILES:
            thr = _q(a, q)
            if thr is not None:
                base.append({"feat": f, "op": op, "thr": thr, "_q": q})
    for b in base:
        out.append({"grammar": "thresh", **b})
    # conditioners: every other feature's tercile, and the four broker-session buckets
    cond_bands: list[tuple[str, float, float, str]] = []
    for f in MR.base_feature_names():
        a = P.feats[f][:cut]
        lo_q, hi_q = _q(a, TERCILE_Q[0]), _q(a, TERCILE_Q[1])
        if lo_q is None or hi_q is None or not lo_q < hi_q:
            continue
        cond_bands += [(f, -MR.OPEN_BOUND, lo_q, "t1"), (f, lo_q, hi_q, "t2"),
                       (f, hi_q, MR.OPEN_BOUND, "t3")]
    for a_, b_ in SESSIONS:
        cond_bands.append(("hour", float(a_), float(b_), f"s{a_}"))
    for b in base:
        for cf, lo_, hi_, _lab in cond_bands:
            if cf == b["feat"]:
                continue
            out.append({"grammar": "cond", **b, "cond_feat": cf, "cond_lo": lo_,
                        "cond_hi": hi_})
    for hh in range(24):
        for wd in CLOCK_WEEKDAYS:
            out.append({"grammar": "clock", "feat": "", "op": "gt", "thr": 0.0, "hour": hh,
                        "weekday": wd})
    for leader in sorted(P.lead):
        for f in sorted(P.lead[leader]):
            a = P.lead[leader][f][:cut]
            for q, op in QUANTILES:
                thr = _q(a, q)
                if thr is not None:
                    out.append({"grammar": "lead", "feat": f, "op": op, "thr": thr,
                                "leader": leader, "_q": q})
    cs = carry_side(meta or {})
    if cs:
        vr = P.feats["volratio"][:cut]
        v1, v2 = _q(vr, TERCILE_Q[0]), _q(vr, TERCILE_Q[1])
        regimes: list[tuple[str, float, float]] = [("", -MR.OPEN_BOUND, MR.OPEN_BOUND)]
        if v1 is not None and v2 is not None and v1 < v2:
            regimes += [("volratio", -MR.OPEN_BOUND, v1), ("volratio", v1, v2)]
        for hh in CARRY_HOURS:
            for cf, lo_, hi_ in regimes:
                for trend in ("", "gt" if cs > 0 else "lt"):
                    out.append({"grammar": "carry", "feat": "ret_120" if trend else "",
                                "op": trend or "gt", "thr": 0.0, "hour": hh,
                                "cond_feat": cf, "cond_lo": lo_, "cond_hi": hi_,
                                "carry_side": cs})
    return out


def wf_start_rank(n_days: int) -> int:
    """Index (into the cell's active days) of the first walk-forward TEST day, as the sealed
    gauntlet cuts it; n_days when the series is too short to have one."""
    ts = max(WF_MIN_TEST, n_days // WF_TEST_DIV)
    start = n_days - WF_SPLITS * ts
    return start if start > 0 else 0


def cell_days(P: Prepared, kept_full: np.ndarray, h: int) -> tuple[np.ndarray, int]:
    """(training-window prefix of the kept fires, the WF-test start day) for one cell."""
    if kept_full.size == 0:
        return kept_full, 0
    days = P.entry_day[kept_full]
    uniq = np.unique(days)
    r = wf_start_rank(len(uniq))
    wf_day = int(uniq[r]) if r < len(uniq) else int(uniq[-1]) + 1
    lim = P.cut - 2 - h
    sel = (kept_full <= lim) & (days < wf_day)
    return kept_full[sel], wf_day


def cell_stats(R1: np.ndarray, R3: np.ndarray, kept: np.ndarray, days: np.ndarray
               ) -> dict[str, np.ndarray] | None:
    """Per-variant daily-series statistics over the kept fires (None when < MIN_DAYS days).

    ONE TRADE PER ENTRY DAY BY CONSTRUCTION (`mass_screen_rules.thin`), so the day's value is that
    trade's R -- the sum, the last and the only trade all agree, and the sealed judge's
    `daily_series` (a dict keyed by entry date, last trade wins) reproduces it exactly. The
    last-of-day slice below is therefore the identity; it is written as the judge's arithmetic so
    a future relaxation of the thinning law cannot silently diverge from what the judge computes.
    """
    if kept.size == 0:
        return None
    last = np.flatnonzero(np.r_[days[1:] != days[:-1], True])
    D = last.size
    if D < MIN_DAYS:
        return {"n_days": np.full(R1.shape[0], D)}
    s1 = R1[:, kept[last]]
    s3 = R3[:, kept[last]]
    if not np.isfinite(s1).all():
        s1 = np.where(np.isfinite(s1), s1, 0.0)
        s3 = np.where(np.isfinite(s3), s3, 0.0)
    mean = s1.mean(axis=1)
    sd = s1.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(sd > 0, mean / sd * math.sqrt(D), 0.0)
    return {"n_days": np.full(R1.shape[0], D), "n_trades": np.full(R1.shape[0], kept.size),
            "mean": mean, "t": t, "hit": (s1 > 0).mean(axis=1), "mean_x3": s3.mean(axis=1)}


def screen_symbol(P: Prepared, meta: dict[str, Any] | None = None, *, q: float = FDR_Q,
                  conds: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Screen every cell of one symbol. Returns counts per grammar and the CANDIDATES -- cells
    whose one-sided p-value is <= q, the only ones Benjamini-Hochberg can ever reject at q --
    with the days they trade, for the run-level FDR and dedup."""
    from scipy.stats import t as student_t
    started = time.monotonic()
    conds = conds if conds is not None else conditions(P, meta)
    by_grammar: dict[str, dict[str, int]] = {}
    cands: list[dict[str, Any]] = []
    for cond in conds:
        g = cond["grammar"]
        agg = by_grammar.setdefault(g, {"cells": 0, "testable": 0, "candidates": 0})
        allowed = [vi for vi, (d, _k) in enumerate(VARIANTS)
                   if g != "carry" or d == cond.get("carry_side")]
        pos_all = np.flatnonzero(P.mask(cond))
        for h in HORIZONS:
            agg["cells"] += len(allowed)
            if pos_all.size < MIN_DAYS:
                continue
            kept_full = MR.thin(pos_all[pos_all <= P.n - 2 - h], h, P.entry_day)
            kept, _wf = cell_days(P, kept_full, h)
            if kept.size < MIN_DAYS:
                continue
            days = P.entry_day[kept]
            st = cell_stats(P.R1[h], P.R3[h], kept, days)
            if st is None or "t" not in st:
                continue
            D = int(st["n_days"][0])
            agg["testable"] += len(allowed)
            p = student_t.sf(st["t"], df=D - 1)
            for vi in allowed:
                if not (p[vi] <= q) or not np.isfinite(p[vi]):
                    continue
                d, k = VARIANTS[vi]
                agg["candidates"] += 1
                cands.append({
                    "symbol": P.symbol, "grammar": g, "cond": _public(cond), "hold": h,
                    "direction": d, "stop_atr": k, "p": float(p[vi]),
                    "t": float(st["t"][vi]), "mean_r": float(st["mean"][vi]),
                    "hit": float(st["hit"][vi]), "mean_r_x3": float(st["mean_x3"][vi]),
                    "n_days": D, "n_trades": int(st["n_trades"][0]),
                    "days": np.unique(days).astype("int32"),
                })
    cells = sum(v["cells"] for v in by_grammar.values())
    return {"symbol": P.symbol, "cells": cells,
            "testable": sum(v["testable"] for v in by_grammar.values()),
            "by_grammar": by_grammar, "candidates": cands,
            "seconds": round(time.monotonic() - started, 4), "n_bars": P.n,
            "train_end_utc": _iso(P.t_ns[min(P.cut, P.n - 1)])}


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(int(ns) / 1e9, tz=UTC).isoformat(timespec="seconds")


def _public(cond: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cond.items() if not k.startswith("_") and k != "grammar"}


# --------------------------------------------------------------------------------------------
# run-level FDR, dedup, forward
# --------------------------------------------------------------------------------------------
def bh_threshold(pvals: np.ndarray, m: int, q: float) -> float:
    """Benjamini-Hochberg over m hypotheses of which only `pvals` (the ones <= q) are listed;
    every unlisted p exceeds q, so it can never be rejected and never moves the cut. Returns the
    p-value cut (0.0 when nothing is rejected). Same arithmetic as libs.validation.fdr._control."""
    p = np.sort(np.asarray(pvals, dtype="float64"))
    if p.size == 0 or m <= 0:
        return 0.0
    ranks = np.arange(1, p.size + 1)
    below = p <= ranks / float(m) * q
    if not below.any():
        return 0.0
    return float(p[int(np.max(np.flatnonzero(below)))])


def params_of(c: dict[str, Any]) -> dict[str, Any]:
    """The executable identity the gauntlet rebuilds -- every argument, defaults spelled out."""
    cd = c["cond"]
    return {"feat": str(cd.get("feat", "")), "op": str(cd.get("op", "gt")),
            "thr": float(cd.get("thr", 0.0)), "direction": int(c["direction"]),
            "hold": int(c["hold"]), "stop_atr": float(c["stop_atr"]),
            "cond_feat": str(cd.get("cond_feat", "")),
            "cond_lo": float(cd.get("cond_lo", -MR.OPEN_BOUND)),
            "cond_hi": float(cd.get("cond_hi", MR.OPEN_BOUND)),
            "hour": int(cd.get("hour", -1)), "weekday": int(cd.get("weekday", -1)),
            "leader": str(cd.get("leader", "")), "atr_n": 20, "gv": MR.GRAMMAR_VERSION}


def structural_key(c: dict[str, Any]) -> str:
    """Identity WITHOUT the numeric thresholds, so a re-screen on grown data (thresholds drift in
    the sixth digit) does not re-forward the same rule under a new content hash."""
    cd = c["cond"]
    return "|".join(str(x) for x in (
        c["symbol"], c["grammar"], cd.get("feat", ""), cd.get("op", ""), cd.get("_q", ""),
        cd.get("cond_feat", ""), _band_label(cd), cd.get("hour", -1), cd.get("weekday", -1),
        cd.get("leader", ""), c["hold"], c["direction"], c["stop_atr"], MR.GRAMMAR_VERSION))


def _band_label(cd: dict[str, Any]) -> str:
    lo, hi = cd.get("cond_lo"), cd.get("cond_hi")
    if lo is None and hi is None:
        return ""
    if cd.get("cond_feat") == "hour":
        return f"{lo}-{hi}"
    return ("lo" if (lo or 0) <= -MR.OPEN_BOUND else "x") + ("hi" if (hi or 0) >= MR.OPEN_BOUND
                                                             else "y")


def dedup(survivors: list[dict[str, Any]], jaccard: float = DEDUP_JACCARD
          ) -> tuple[list[dict[str, Any]], int]:
    """Greedy by t: keep a survivor unless it trades >= `jaccard` of the same days as a stronger
    kept one on the same symbol and side. Returns (kept, dropped count)."""
    kept: list[dict[str, Any]] = []
    by_key: dict[tuple[str, int], list[np.ndarray]] = {}
    dropped = 0
    for c in sorted(survivors, key=lambda r: -r["t"]):
        key = (c["symbol"], int(c["direction"]))
        days = c["days"]
        dup = False
        for other in by_key.get(key, []):
            inter = np.intersect1d(days, other, assume_unique=True).size
            union = days.size + other.size - inter
            if union and inter / union >= jaccard:
                dup = True
                break
        if dup:
            dropped += 1
            continue
        kept.append(c)
        by_key.setdefault(key, []).append(days)
    return kept, dropped


def mechanism_of(c: dict[str, Any]) -> str:
    cd = c["cond"]
    g = c["grammar"]
    if g == "clock":
        cls = MR.MECHANISM_OF_FEATURE["clock"]
    elif g == "carry":
        cls = MR.MECHANISM_OF_FEATURE["carry"]
    elif g == "lead":
        cls = MR.MECHANISM_OF_FEATURE["lead_ret"]
    else:
        cls = MR.MECHANISM_OF_FEATURE.get(str(cd.get("feat", "")).split("_")[0], "bar feature")
    side = "long" if c["direction"] > 0 else "short"
    rule = (f"{cd.get('feat') or 'clock'} {cd.get('op')} {cd.get('thr')}"
            + (f" | {cd['cond_feat']} in [{cd.get('cond_lo'):.6g},{cd.get('cond_hi'):.6g})"
               if cd.get("cond_feat") else "")
            + (f" | hour {cd['hour']}" if int(cd.get("hour", -1)) >= 0 else "")
            + (f" wd {cd['weekday']}" if int(cd.get("weekday", -1)) >= 0 else "")
            + (f" | leader {cd['leader']}" if cd.get("leader") else ""))
    return (f"{cls}. mass_screen/{g}: {rule} -> {side}, hold {c['hold']}h, stop "
            f"{c['stop_atr']}ATR. Screened in-sample only (train t={c['t']:.2f} over "
            f"{c['n_days']} days, net R/day {c['mean_r']:.4f}, x3 {c['mean_r_x3']:.4f}); "
            f"selected from {c.get('_m', 0)} cells at BH q={c.get('_q', FDR_Q)}.")


def forward(cells: list[dict[str, Any]], *, conn=None) -> dict[str, Any]:
    """Through the registry's one door. Returns counts; never raises."""
    out = {"attempted": 0, "created": 0, "already_present": 0, "failed": 0, "why": None}
    if not cells:
        return out
    try:
        from libs.moat.registry import connect, enqueue_candidate
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry door unimportable ({type(exc).__name__}: {exc})"
        out["failed"] = len(cells)
        return out
    own = conn is None
    try:
        con = conn or connect()
    except Exception as exc:
        out["why"] = f"{UNMEASURED}: registry unopenable ({type(exc).__name__}: {exc})"
        out["failed"] = len(cells)
        return out
    try:
        for c in cells:
            out["attempted"] += 1
            try:
                _id, made = enqueue_candidate(
                    family=f"mass_screen_{c['grammar']}", symbol=c["symbol"],
                    params=params_of(c), origin=ORIGIN, mechanism=mechanism_of(c), conn=con,
                    chart="H1", horizon=f"{c['hold']}h",
                    # MEASURED evidence, not a prior: 1 - the BH-adjusted p on the training
                    # window. score_candidate reads it; an unmeasured row keeps the 0.5 prior.
                    p_edge=round(max(0.5, min(0.99, 1.0 - float(c.get("_qvalue", 1.0)))), 4),
                    producer="desks/mt5/research/mass_screen.py", generator=ORIGIN)
            except Exception:
                out["failed"] += 1
                continue
            out["created" if made else "already_present"] += 1
    finally:
        if own:
            with contextlib.suppress(Exception):
                con.close()
    return out


# --------------------------------------------------------------------------------------------
# workers, budget, the run
# --------------------------------------------------------------------------------------------
def derive_workers(override: int | None = None) -> tuple[int, dict[str, Any]]:
    """Worker count from MEASURED free cores and free memory on THIS machine, never a constant."""
    info: dict[str, Any] = {}
    try:
        import psutil
        cores = int(psutil.cpu_count(logical=True) or 1)
        busy_pct = float(psutil.cpu_percent(interval=1.0))
        avail_mb = float(psutil.virtual_memory().available) / 2**20
        busy = round(busy_pct / 100.0 * cores)
        free = max(1, cores - busy - 1)
        mem_cap = max(1, int(avail_mb * 0.5 // WORKER_MB))
        w = max(1, min(free, mem_cap))
        info = {"cores": cores, "busy_pct": busy_pct, "busy_cores": busy,
                "free_cores_less_one": free, "available_mb": round(avail_mb),
                "memory_cap_workers": mem_cap, "basis": "psutil, measured this run"}
    except Exception as exc:
        w = 1
        info = {"basis": f"{UNMEASURED}: psutil unavailable ({type(exc).__name__}); one worker"}
    if override:
        w = max(1, int(override))
        info["override"] = w
    info["workers"] = w
    return w, info


def _load_leaders(symbols: list[str]) -> dict[str, Any]:
    out = {}
    for s in LEADERS:
        if s in symbols or (UNIVERSE / f"{s}_H1.parquet").exists():
            df = MR.load_bars(s)
            if df is not None and len(df):
                out[s] = df
    return out


def _worker(symbol: str, q: float) -> dict[str, Any]:
    """One symbol, end to end, in a worker process. Never raises."""
    t0 = time.monotonic()
    try:
        df = MR.load_bars(symbol)
        if df is None or len(df) < 2000:
            return {"symbol": symbol, "error": "no or too few H1 bars", "cells": 0,
                    "seconds": round(time.monotonic() - t0, 3)}
        meta = universe_meta().get(symbol) or {}
        P = Prepared(symbol, df, meta, _load_leaders([symbol]))
        prep_s = time.monotonic() - t0
        res = screen_symbol(P, meta, q=q)
        res["prep_seconds"] = round(prep_s, 3)
        res["seconds"] = round(time.monotonic() - t0, 3)
        return res
    except Exception as exc:
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "cells": 0, "seconds": round(time.monotonic() - t0, 3)}


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")


def run(*, budget_s: float = 900.0, workers: int | None = None, symbols: list[str] | None = None,
        q: float = FDR_Q, dry_run: bool = False, out_dir: Path | None = None,
        conn=None) -> dict[str, Any]:
    started = time.monotonic()
    run_id = f"ms_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    report = (out_dir / "MASS_SCREEN.json") if out_dir else REPORT
    trials_p = (out_dir / "MASS_SCREEN_TRIALS.jsonl") if out_dir else TRIALS
    runs_p = (out_dir / "mass_screen_runs.jsonl") if out_dir else RUNS
    cursor_p = (out_dir / "mass_screen_cursor.json") if out_dir else CURSOR
    fwd_p = (out_dir / "mass_screen_forwarded.json") if out_dir else FORWARDED
    universe = symbols if symbols else hypothesis_symbols()
    if not universe:
        doc = {"generated_utc": _now(), "status": UNMEASURED, "run_id": run_id,
               "why": "no hypothesis-lane symbol with H1 bars (universe_policy / parquets)"}
        _write_json(report, doc)
        return doc
    cursor = _read_json(cursor_p, {}) if not symbols else {}
    start = int(cursor.get("next", 0)) % len(universe)
    epoch = int(cursor.get("epoch", 0))
    order = universe[start:] + universe[:start]
    w, winfo = derive_workers(workers)
    results: list[dict[str, Any]] = []
    done = 0
    per_symbol_s: list[float] = []

    def _time_left() -> float:
        return budget_s - (time.monotonic() - started)

    if w <= 1:
        for s in order:
            if results and _time_left() < (np.median(per_symbol_s) if per_symbol_s else 0):
                break
            r = _worker(s, q)
            results.append(r)
            per_symbol_s.append(float(r.get("seconds") or 0))
            done += 1
            if _time_left() <= 0:
                break
    else:
        with ProcessPoolExecutor(max_workers=w) as ex:
            it = iter(order)
            live: dict[Any, str] = {}
            for s in it:
                live[ex.submit(_worker, s, q)] = s
                if len(live) >= w:
                    break
            while live:
                fin, _ = wait(list(live), timeout=max(1.0, _time_left()),
                              return_when=FIRST_COMPLETED)
                if not fin:
                    break
                for f in fin:
                    live.pop(f)
                    r = f.result()
                    results.append(r)
                    per_symbol_s.append(float(r.get("seconds") or 0))
                    done += 1
                    est = float(np.median(per_symbol_s)) if per_symbol_s else 0.0
                    if _time_left() > est:
                        nxt = next(it, None)
                        if nxt is not None:
                            live[ex.submit(_worker, nxt, q)] = nxt
            for f in live:
                f.cancel()
    wall = time.monotonic() - started
    nxt_idx = start + done
    if nxt_idx >= len(universe):
        epoch += nxt_idx // len(universe)
    new_cursor = {"next": nxt_idx % len(universe), "epoch": epoch, "updated_utc": _now(),
                  "universe": len(universe)}

    # ---- run-level FDR over EVERY cell screened --------------------------------------------
    m = int(sum(int(r.get("cells") or 0) for r in results))
    testable = int(sum(int(r.get("testable") or 0) for r in results))
    cands = [c for r in results for c in (r.get("candidates") or [])]
    cut = bh_threshold(np.array([c["p"] for c in cands]), m, q)
    rejected = [c for c in cands if cut > 0 and c["p"] <= cut]
    ranked = sorted(p for p in (c["p"] for c in cands))
    for c in rejected:
        rank = int(np.searchsorted(ranked, c["p"], side="right"))
        c["_qvalue"] = min(1.0, c["p"] * m / max(rank, 1))
        c["_m"], c["_q"] = m, q
    stressed = [c for c in rejected if c["mean_r_x3"] > 0 and c["mean_r"] > 0]
    kept, dup_dropped = dedup(stressed)
    already = set(_read_json(fwd_p, []))
    fresh = [c for c in kept if structural_key(c) not in already]
    fwd = ({"attempted": 0, "created": 0, "already_present": 0, "failed": 0,
            "why": "dry run: nothing forwarded"} if dry_run else forward(fresh, conn=conn))
    if not dry_run and fresh and not fwd.get("why"):
        already |= {structural_key(c) for c in fresh}
        _write_json(fwd_p, sorted(already))

    # ---- multiplicity: every screened cell is a trial, per grammar --------------------------
    by_g: dict[str, dict[str, int]] = {}
    for r in results:
        for g, v in (r.get("by_grammar") or {}).items():
            a = by_g.setdefault(g, {"cells": 0, "testable": 0, "candidates": 0})
            for k in a:
                a[k] += int(v.get(k) or 0)
    for g, a in by_g.items():
        a["fdr_rejected"] = sum(1 for c in rejected if c["grammar"] == g)
        a["forwarded"] = sum(1 for c in fresh if c["grammar"] == g) if not dry_run else 0
    ts = _now()
    trial_rows = [{"ts": ts, "run_id": run_id, "family": f"mass_screen_{g}", "grammar": g,
                   "cells_screened": a["cells"], "cells_testable": a["testable"],
                   "fdr_q": q, "fdr_rejected": a["fdr_rejected"], "forwarded": a["forwarded"],
                   "epoch": epoch, "dry_run": bool(dry_run)} for g, a in sorted(by_g.items())]
    if not dry_run or out_dir is not None:
        _append(trials_p, trial_rows)
    cps = m / wall if wall > 0 else 0.0
    worker_s = sum(float(r.get("seconds") or 0) for r in results)
    cps_core = m / worker_s if worker_s > 0 else 0.0
    run_row = {"ts": ts, "run_id": run_id, "symbols": done, "cells": m, "testable": testable,
               "candidates": len(cands), "fdr_rejected": len(rejected),
               "stress_pass": len(stressed), "dedup_dropped": dup_dropped,
               "forwarded": int(fwd.get("created", 0)) + int(fwd.get("already_present", 0)),
               "wall_s": round(wall, 2), "worker_s": round(worker_s, 2), "workers": w,
               "cells_per_sec": round(cps, 1), "cells_per_core_sec": round(cps_core, 1),
               "dry_run": bool(dry_run)}
    if not dry_run or out_dir is not None:
        _append(runs_p, [run_row])
        if not symbols:
            _write_json(cursor_p, new_cursor)
    day = _day_totals(runs_p)
    cores = int(winfo.get("cores") or w)
    doc = {
        "generated_utc": ts, "status": "MEASURED" if results else UNMEASURED,
        "run_id": run_id, "dry_run": bool(dry_run),
        "law": ("screen on the TRAINING window only (first TRAIN_FRAC of history, clipped per "
                "cell to the start of its walk-forward/lockbox test region); >= MIN_DAYS trading "
                "days inside it; BH at q over every screened cell; 3x-spread stress; Jaccard "
                "dedup; forwarded through the registry door; every screened cell charged as a "
                "trial in MASS_SCREEN_TRIALS.jsonl"),
        "run": {**run_row, "symbols_screened": [r["symbol"] for r in results],
                "errors": {r["symbol"]: r["error"] for r in results if r.get("error")},
                "cursor": new_cursor},
        "per_day": day,
        "fdr": {"method": "benjamini_hochberg", "q": q, "m": m, "p_cut": cut,
                "rejected": len(rejected), "candidates_p_le_q": len(cands)},
        "forward": {**fwd, "survivors_after_dedup": len(kept),
                    "skipped_already_forwarded": len(kept) - len(fresh),
                    "door": "libs.moat.registry.enqueue_candidate -> libs.moat.docket_feed -> "
                            "research/merge_hypotheses.py -> data/hypotheses/"
                            "external_survivors.json (read by the sealed gauntlet)"},
        "trials_recorded": {"ledger": str(trials_p.relative_to(DESK) if trials_p.is_relative_to(
                                DESK) else trials_p),
                            "rows": trial_rows,
                            "reader": "libs/research/experiment_ledger.py::_mass_screen_counts"},
        "by_grammar": by_g,
        "throughput": {
            "cells_per_sec_wall": round(cps, 1), "cells_per_core_sec": round(cps_core, 1),
            "workers": w, "wall_s": round(wall, 2), "numba": bool(MR._HAVE_NUMBA),
            "projected_cells_per_day_all_cores": (int(cps_core * cores * 86400)
                                                  if cps_core else UNMEASURED),
            "projected_cells_per_day_at_this_duty": (int(cps * 24 * min(wall, budget_s))
                                                     if cps else UNMEASURED),
            "note": ("projections are cells/core-second x cores x 86,400 and cells/sec x this "
                     "run's wall seconds x 24 hourly runs; measured, not asserted"),
        },
        "workers": winfo,
        "windows": {"train_frac": TRAIN_FRAC, "wf_splits": WF_SPLITS, "wf_test_div": WF_TEST_DIV,
                    "min_days": MIN_DAYS, "cost_stress": COST_STRESS,
                    "train_end_by_symbol": {r["symbol"]: r.get("train_end_utc")
                                            for r in results if r.get("train_end_utc")}},
        "forwarded_sample": [{"symbol": c["symbol"], "family": f"mass_screen_{c['grammar']}",
                              "params": params_of(c), "t": round(c["t"], 3), "p": c["p"],
                              "n_days": c["n_days"], "mean_r": round(c["mean_r"], 5),
                              "mean_r_x3": round(c["mean_r_x3"], 5)}
                             for c in (fresh if not dry_run else kept)[:25]],
    }
    _write_json(report, doc)
    return doc


def _day_totals(runs_p: Path) -> dict[str, Any]:
    """Trailing-24h totals from the run ledger. Absent ledger: UNMEASURED, never 0."""
    try:
        lines = runs_p.read_text("utf-8").splitlines()
    except OSError:
        return {"status": UNMEASURED, "why": f"{runs_p.name} absent"}
    floor = datetime.now(tz=UTC) - timedelta(hours=24)
    tot = {"runs": 0, "cells_screened": 0, "testable": 0, "fdr_rejected": 0, "forwarded": 0,
           "wall_s": 0.0}
    for ln in lines:
        try:
            r = json.loads(ln)
            if datetime.fromisoformat(str(r["ts"])) < floor:
                continue
        except (ValueError, KeyError, TypeError):
            continue
        tot["runs"] += 1
        tot["cells_screened"] += int(r.get("cells") or 0)
        tot["testable"] += int(r.get("testable") or 0)
        tot["fdr_rejected"] += int(r.get("fdr_rejected") or 0)
        tot["forwarded"] += int(r.get("forwarded") or 0)
        tot["wall_s"] += float(r.get("wall_s") or 0.0)
    if not tot["runs"]:
        return {"status": UNMEASURED, "why": "no run in the trailing 24h"}
    return {"status": "MEASURED", **tot, "wall_s": round(tot["wall_s"], 1)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one bounded run (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--workers", type=int, default=None, help="override the measured count")
    ap.add_argument("--symbols", default="", help="comma list (default: the hypothesis lane)")
    ap.add_argument("--q", type=float, default=FDR_Q)
    ap.add_argument("--dry-run", action="store_true", help="screen but forward nothing")
    ap.add_argument("--out-dir", type=Path, default=None, help="write artifacts here instead")
    a = ap.parse_args(argv)
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] or None
    doc = run(budget_s=a.budget_s, workers=a.workers, symbols=syms, q=a.q,
              dry_run=a.dry_run, out_dir=a.out_dir)
    t = doc.get("throughput") or {}
    r = doc.get("run") or {}
    print(f"mass_screen {doc.get('status')}: {r.get('symbols', 0)} symbol(s), "
          f"{r.get('cells', 0):,} cells in {r.get('wall_s')}s on {t.get('workers')} worker(s) "
          f"= {t.get('cells_per_sec_wall')} cells/s ({t.get('cells_per_core_sec')}/core-s); "
          f"FDR rejected {r.get('fdr_rejected')}, forwarded {r.get('forwarded')}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
