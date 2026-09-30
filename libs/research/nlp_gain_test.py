"""THE ADMISSION TEST for text-derived indices: predictive IC against a shuffled-date placebo.

A daily index -- a policy-tone drift, a blog-attention delta -- earns a place in the desk's
conditioning set only if it carries information about the instrument's NEXT move that the same
values on the WRONG dates do not. So each (index, instrument, horizon) is measured three ways:

  IC            Spearman rank correlation of the index on day d with the log return from the
                close of the FIRST trading day AFTER d to h trading days later. The skip is
                deliberate: a day's index is stamped available at the following 00:00 UTC, after
                that day's close, so the return that starts at d's own close was not tradable.
  PLACEBO       the index values block-permuted across dates (blocks of >= 2h days so the null
                keeps the index's own autocorrelation), IC recomputed each time. p is the share
                of placebo |IC| at least as large as the real one, with the +1 correction.
  BOOTSTRAP CI  a moving-block bootstrap of the paired (index, return) days, 90% interval.

Every test is a trial. The q-values are Benjamini-Hochberg over the WHOLE grid the caller ran,
and GAIN needs q <= alpha AND a bootstrap interval that excludes zero. A grid where no series had
`min_obs` aligned days is UNMEASURED, never NO_GAIN (L1.28a).

Pure numpy/pandas; deterministic under `seed`.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

UNMEASURED = "UNMEASURED"
GAIN = "GAIN"
NO_GAIN = "NO_GAIN_SHOWN"
MIN_OBS = 60
#: The longest calendar gap allowed between an index day and the first close after it. An index
#: day before the bar history begins (or inside a hole in it) would otherwise map onto the first
#: close that exists and pair many index values with ONE return -- measured 2026-09-30 on the BIS
#: title corpus, where it manufactured an IC of 0.76 out of 1996 index days and 2018 bars.
MAX_GAP_DAYS = 5


def _rank(a: np.ndarray) -> np.ndarray:
    return np.asarray(pd.Series(a).rank(method="average").to_numpy(dtype=float), dtype=float)


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 3:
        return math.nan
    rx, ry = _rank(x), _rank(y)
    sx, sy = rx.std(), ry.std()
    if sx <= 0 or sy <= 0:
        return math.nan
    return float(np.mean((rx - rx.mean()) * (ry - ry.mean())) / (sx * sy))


def align(index: pd.Series, close: pd.Series, h: int) -> tuple[np.ndarray, np.ndarray]:
    """(index value on day d, log return from the first close AFTER d to h closes later)."""
    idx = index.dropna()
    cl = close.dropna()
    if idx.empty or cl.empty:
        return np.array([]), np.array([])
    idx.index = pd.DatetimeIndex(pd.to_datetime(idx.index)).tz_localize(None).normalize()
    cl.index = pd.DatetimeIndex(pd.to_datetime(cl.index)).tz_localize(None).normalize()
    cl = cl[~cl.index.duplicated(keep="last")].sort_index()
    days = cl.index.to_numpy(dtype="datetime64[ns]")
    px = np.log(cl.to_numpy(dtype=float))
    keys = idx.index.to_numpy(dtype="datetime64[ns]")
    vals = idx.to_numpy(dtype=float)
    pos = np.searchsorted(days, keys, side="right")
    ok = (pos >= 1) & (pos + h < len(px))
    pos, vals, keys = pos[ok], vals[ok], keys[ok]
    near = (days[pos] - keys) <= np.timedelta64(MAX_GAP_DAYS, "D")
    pos, vals = pos[near], vals[near]
    rets = px[pos + h] - px[pos]
    keep = np.isfinite(rets) & np.isfinite(vals)
    return np.asarray(vals[keep], dtype=float), np.asarray(rets[keep], dtype=float)


def block_permute(x: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    n = x.size
    starts = np.arange(0, n, max(1, block))
    order = rng.permutation(starts.size)
    return np.concatenate([x[s:s + block] for s in starts[order]])[:n]


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    sa, sb = a.std(), b.std()
    if sa <= 0 or sb <= 0:
        return math.nan
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def block_bootstrap_ci(x: np.ndarray, y: np.ndarray, block: int, n_boot: int,
                       rng: np.random.Generator, level: float = 0.90) -> tuple[float, float]:
    """Moving-block bootstrap of the paired days. The ranks are taken ONCE on the full sample and
    the Pearson of the resampled ranks is the statistic -- the standard fast approximation, and
    exact whenever a resample holds no new ties."""
    x, y = _rank(x), _rank(y)
    n = x.size
    b = max(1, min(block, n))
    k = math.ceil(n / b)
    stats = []
    for _ in range(n_boot):
        st = rng.integers(0, n - b + 1, size=k)
        ii = np.concatenate([np.arange(s, s + b) for s in st])[:n]
        v = _pearson(x[ii], y[ii])
        if math.isfinite(v):
            stats.append(v)
    if not stats:
        return math.nan, math.nan
    lo, hi = np.quantile(stats, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def bh_qvalues(p: Sequence[float]) -> list[float]:
    arr = np.asarray([v if math.isfinite(v) else 1.0 for v in p], dtype=float)
    n = arr.size
    if n == 0:
        return []
    order = np.argsort(arr)
    q = np.empty(n)
    prev = 1.0
    for rank_i in range(n - 1, -1, -1):
        i = order[rank_i]
        prev = min(prev, arr[i] * n / (rank_i + 1))
        q[i] = prev
    return [float(v) for v in q]


def one_test(index: pd.Series, close: pd.Series, h: int, *, n_placebo: int = 200,
             n_boot: int = 300, seed: int = 0, min_obs: int = MIN_OBS) -> dict[str, Any]:
    x, y = align(index, close, h)
    row: dict[str, Any] = {"horizon": h, "n_obs": int(x.size)}
    if x.size < min_obs:
        row.update(state=UNMEASURED, why=f"{x.size} aligned days < {min_obs}")
        return row
    rng = np.random.default_rng(seed)
    ic = spearman(x, y)
    if not math.isfinite(ic):
        # A CONSTANT INDEX HAS NO RANK ORDER. It was not tested, so it is not a trial and not a
        # NO_GAIN: it is UNMEASURED with its reason.
        row.update(state=UNMEASURED, why="index or return constant over the aligned days")
        return row
    block = max(5, 2 * h)
    # A PERMUTATION OF x IS A PERMUTATION OF ITS RANKS, so the ranks are taken once and the
    # placebo is a Pearson on permuted ranks -- identical to recomputing Spearman, far cheaper.
    rx, ry = _rank(x), _rank(y)
    null = [_pearson(block_permute(rx, block, rng), ry) for _ in range(n_placebo)]
    null_arr = np.asarray([v for v in null if math.isfinite(v)])
    p = ((1 + int(np.sum(np.abs(null_arr) >= abs(ic)))) / (1 + null_arr.size)
         if math.isfinite(ic) else 1.0)
    lo, hi = block_bootstrap_ci(x, y, block, n_boot, rng)
    row.update(state="MEASURED", ic=round(ic, 5), placebo_ic_mean=round(float(null_arr.mean()), 5),
               placebo_ic_sd=round(float(null_arr.std()), 5), p_placebo=round(p, 5),
               ci90=[round(lo, 5), round(hi, 5)])
    return row


def gain_grid(indices: Mapping[str, pd.Series], closes: Mapping[str, pd.Series],
              pairs: Sequence[tuple[str, str]], *, horizons: Sequence[int] = (1, 5),
              alpha: float = 0.10, n_placebo: int = 200, n_boot: int = 300, seed: int = 0,
              min_obs: int = MIN_OBS) -> dict[str, Any]:
    """Every (index, instrument, horizon) in `pairs` x `horizons`; BH across all measured tests."""
    rows: list[dict[str, Any]] = []
    for k, (iname, inst) in enumerate(pairs):
        s, c = indices.get(iname), closes.get(inst)
        for h in horizons:
            base = {"index": iname, "instrument": inst}
            if s is None or c is None:
                rows.append({**base, "horizon": h, "n_obs": 0, "state": UNMEASURED,
                             "why": "no index series" if s is None else "no bars for instrument"})
                continue
            rows.append({**base, **one_test(s, c, h, n_placebo=n_placebo, n_boot=n_boot,
                                            seed=seed + 7919 * k + h, min_obs=min_obs)})
    measured = [r for r in rows if r.get("state") == "MEASURED"]
    for r, q in zip(measured, bh_qvalues([float(r["p_placebo"]) for r in measured]), strict=True):
        r["q_bh"] = round(q, 5)
        lo, hi = r["ci90"]
        r["gain"] = bool(q <= alpha and math.isfinite(lo) and (lo > 0 or hi < 0))
    verdict = (UNMEASURED if not measured
               else GAIN if any(r["gain"] for r in measured) else NO_GAIN)
    return {"verdict": verdict, "n_trials": len(measured),
            "n_unmeasured": len(rows) - len(measured),
            "alpha": alpha, "n_placebo": n_placebo, "rule": (
                "GAIN needs BH q <= alpha over every measured test AND a 90% block-bootstrap IC "
                "interval excluding zero; the placebo shuffles the index's dates in blocks"),
            "tests": rows}
