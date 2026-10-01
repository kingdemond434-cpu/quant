"""THE GAIN TEST FOR A RELEASED SERIES: does its surprise lead the instrument AFTER release, more
than the same surprises stamped on the wrong dates do?

WHY A PLACEBO AND NOT ONLY A t-STAT. An alternative-data series that trends with the business
cycle correlates with any instrument that trends with the business cycle, whatever day the print
lands. The claim worth paying for is narrower: the market moves in the direction of the surprise
in the window AFTER the desk could first read it. So the same surprise values are re-stamped on
shifted release dates -- same values, same distribution, same regime -- and the true IC must beat
the |IC| of those placebos. A series whose "edge" survives the shift is a slow trend co-moving
with the tape, not information arriving on a date.

POINT IN TIME. An event is `(available_time, surprise)`. The entry is the first bar whose label is
at or after `available_time + clock_pad_h` (bars carry BROKER time under a UTC tzinfo, +2 winter
and +3 summer, so a flat +3h pad can only ever be late, never early); the return runs from that
bar's close to the close `horizon_bars` later. Events are thinned so no two windows overlap --
overlapping windows are one observation counted several times.

    ic, n, placebo -> GainResult.verdict in {PASS, FAIL, UNMEASURED}

UNMEASURED is a verdict (L1.28a): fewer than `min_events` independent windows is not a zero.
UNDERPOWERED is a verdict too, distinct from FAIL: a cell that did not pass AND whose minimum
detectable IC (80% power at its own n and Bonferroni charge) is above `TARGET_IC` could not have
detected a realistic edge, so its miss says nothing about the edge. `power_table` measures the
detection rate by simulation with a planted IC; the null row is the false-positive rate.
Pure numpy/pandas; no desk paths, so it is testable on synthetic data with a planted effect.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

#: Bars carry broker time (UTC+2 winter, UTC+3 summer) under a UTC tzinfo. Adding 3h to a UTC
#: release instant can only place the entry at or after the true first tradable bar.
CLOCK_PAD_H = 3
#: Placebo shifts in calendar days, both directions, none a multiple of 7 below 30 so a weekly
#: seasonal cannot line the placebo up with the true calendar. 38 shifts: the smallest reachable
#: placebo p is 1/39 ~= 0.026.
PLACEBO_SHIFTS_D: tuple[int, ...] = tuple(
    s * d for d in (3, 5, 9, 11, 13, 16, 19, 23, 26, 31, 37, 41, 45, 50, 55, 61, 67, 73, 79)
    for s in (1, -1))
MIN_EVENTS = 24
ALPHA_PLACEBO = 0.05
ALPHA_FAMILY = 0.05
#: The IC a released alt-data series can realistically carry on a post-release window. A cell
#: whose minimum detectable IC is above this is UNDERPOWERED when it does not pass, never FAIL.
TARGET_IC = 0.05
#: Power at which the minimum detectable IC is quoted.
POWER = 0.80


def min_detectable_ic(n: int, n_cells: int = 1, *, alpha: float = ALPHA_FAMILY,
                      power: float = POWER, two_sided: bool = True) -> float | None:
    """The smallest |IC| the t-leg detects with `power` at `n` independent windows and a
    Bonferroni charge over `n_cells` (Fisher z, Spearman variance 1.06/(n-3)). A LOWER BOUND on
    the gate's true MDE: the placebo leg and any autocorrelation can only raise it."""
    if n <= 4:
        return None
    a = alpha / max(1, int(n_cells)) / (2.0 if two_sided else 1.0)
    z = NormalDist().inv_cdf(1.0 - a) + NormalDist().inv_cdf(power)
    return round(math.tanh(z * math.sqrt(1.06 / (n - 3))), 4)


@dataclass
class GainResult:
    verdict: str
    ic: float | None
    n: int
    t: float | None
    p_t: float | None
    p_placebo: float | None
    placebo_abs_ic_median: float | None
    placebo_abs_ic_p95: float | None
    n_placebos: int
    horizon_bars: int
    why: str
    events_dropped: dict[str, int] = field(default_factory=dict)
    min_detectable_ic: float | None = None
    target_ic: float = TARGET_IC

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 3 or b.size != a.size:
        return None
    ra = pd.Series(a).rank().to_numpy(dtype=float)
    rb = pd.Series(b).rank().to_numpy(dtype=float)
    if float(np.std(ra)) == 0.0 or float(np.std(rb)) == 0.0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _norm_sf(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def event_returns(events: Sequence[tuple[Any, float]], close: pd.Series, horizon_bars: int, *,
                  clock_pad_h: int = CLOCK_PAD_H,
                  dropped: dict[str, int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(surprises, forward log returns) for non-overlapping post-release windows."""
    drop = dropped if dropped is not None else {}
    idx = pd.DatetimeIndex(close.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    px = close.to_numpy(dtype=float)
    rows: list[tuple[pd.Timestamp, float]] = []
    for when, s in events:
        try:
            ts = pd.Timestamp(when)
        except (TypeError, ValueError):
            drop["bad_time"] = drop.get("bad_time", 0) + 1
            continue
        if pd.isna(ts) or s is None or not math.isfinite(float(s)):
            drop["bad_value"] = drop.get("bad_value", 0) + 1
            continue
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        rows.append((ts + pd.Timedelta(hours=int(clock_pad_h)), float(s)))
    rows.sort(key=lambda r: r[0])
    xs: list[float] = []
    ys: list[float] = []
    free_from = -1
    for ts, s in rows:
        pos = int(idx.searchsorted(ts, side="left"))
        end = pos + int(horizon_bars)
        if pos >= len(idx) or end >= len(idx):
            drop["no_forward_bars"] = drop.get("no_forward_bars", 0) + 1
            continue
        if pos < free_from:
            drop["overlapping_window"] = drop.get("overlapping_window", 0) + 1
            continue
        a, b = px[pos], px[end]
        if not (np.isfinite(a) and np.isfinite(b)) or a <= 0 or b <= 0:
            drop["bad_price"] = drop.get("bad_price", 0) + 1
            continue
        xs.append(s)
        ys.append(math.log(b / a))
        free_from = end
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


def release_gain(events: Sequence[tuple[Any, float]], close: pd.Series, *,
                 horizon_bars: int = 120, n_cells: int = 1,
                 shifts_d: Sequence[int] = PLACEBO_SHIFTS_D, min_events: int = MIN_EVENTS,
                 clock_pad_h: int = CLOCK_PAD_H) -> GainResult:
    """IC of surprise on the post-release return, against shifted-date placebos.

    PASS needs all three: enough independent windows, a Bonferroni-charged t across `n_cells`
    (every cell the caller tested is charged, not only this one), and the true |IC| beating the
    placebo distribution at ALPHA_PLACEBO.
    """
    dropped: dict[str, int] = {}
    x, y = event_returns(events, close, horizon_bars, clock_pad_h=clock_pad_h, dropped=dropped)
    n = int(x.size)
    if n < min_events:
        return GainResult("UNMEASURED", None, n, None, None, None, None, None, 0, horizon_bars,
                          f"{n} independent post-release windows < {min_events}",
                          dropped)
    ic = _spearman(x, y)
    if ic is None:
        return GainResult("UNMEASURED", None, n, None, None, None, None, None, 0, horizon_bars,
                          "surprise or return is constant: no rank correlation exists", dropped)
    t = ic * math.sqrt(max(n - 2, 1) / max(1e-12, 1.0 - ic * ic))
    p_t = 2.0 * _norm_sf(abs(t))
    placebo: list[float] = []
    for d in shifts_d:
        shifted = [(pd.Timestamp(w) + pd.Timedelta(days=int(d)), s) for w, s in events]
        px_, py_ = event_returns(shifted, close, horizon_bars, clock_pad_h=clock_pad_h)
        pic = _spearman(px_, py_) if px_.size >= max(8, min_events // 2) else None
        if pic is not None:
            placebo.append(abs(pic))
    if len(placebo) < 10:
        return GainResult("UNMEASURED", round(ic, 4), n, round(t, 3), p_t, None, None, None,
                          len(placebo), horizon_bars,
                          f"only {len(placebo)} placebo windows could be formed", dropped)
    arr = np.asarray(placebo)
    p_pl = float((1 + int((arr >= abs(ic)).sum())) / (1 + arr.size))
    charged = min(1.0, p_t * max(1, int(n_cells)))
    ok = charged <= ALPHA_FAMILY and p_pl <= ALPHA_PLACEBO
    mde = min_detectable_ic(n, n_cells)
    under = not ok and mde is not None and mde > TARGET_IC
    why = (f"IC {ic:+.3f} over {n} windows; t {t:+.2f} (Bonferroni over {n_cells} cells -> "
           f"p {charged:.3g}); placebo p {p_pl:.3f} against {arr.size} shifted calendars; "
           f"min detectable IC {mde} (80% power) vs target {TARGET_IC}")
    verdict = "PASS" if ok else ("UNDERPOWERED" if under else "FAIL")
    return GainResult(verdict, round(ic, 4), n, round(t, 3), p_t, round(p_pl, 4),
                      round(float(np.median(arr)), 4), round(float(np.quantile(arr, 0.95)), 4),
                      int(arr.size), horizon_bars, why, dropped, mde)


#: Random-regime masks a conditioned child is compared against. Enough that the smallest
#: reachable p (1/(N+1)) clears a Bonferroni charge over a full pass of children.
REGIME_MASKS = 2000
#: A child with fewer in-regime parent signals than this is UNMEASURED, not a verdict.
MIN_IN_REGIME = 20


def regime_placebo(sig_pos: Sequence[int] | np.ndarray, sig_ret: Sequence[float] | np.ndarray,
                   bar_mask: Sequence[bool] | np.ndarray, *, n_trials: int = 1,
                   n_masks: int = REGIME_MASKS, min_in: int = MIN_IN_REGIME,
                   min_shift_frac: float = 0.0, alpha: float = ALPHA_FAMILY,
                   seed: int = 0) -> dict[str, Any]:
    """THE PLACEBO-CONDITIONED TEST for a child that trades its parent only inside a regime.

    `sig_pos` are the bar positions of the PARENT's signals, `sig_ret` their forward returns
    (already signed by the signal's side), `bar_mask` the regime on every bar (True where the
    child would trade). The statistic is the mean return of the parent's signals inside the
    regime. The null is the same statistic under N random regimes WITH THE SAME DUTY CYCLE AND
    THE SAME RUN STRUCTURE: the mask circularly shifted by a random offset of at least
    `min_shift_frac` of the history, so a slow regime stays slow and only its alignment with the
    signals is destroyed. p is one-sided (the child must BEAT random regimes), with the +1
    correction, and is charged Bonferroni over `n_trials` -- every child tested this pass.

    THE SHIFT FLOOR IS 0 BY DEFAULT, MEASURED (`power_table`, 2026-09-30). Excluding shifts near
    zero drops exactly the placebo regimes that look most like the real one, so the real mask is
    no longer exchangeable with its nulls and the test runs LIBERAL: at a 5% floor the null
    false-positive rate was 0.064 at n=250 (2,400 draws) and 0.059 at n=1000, above alpha. With
    every shift eligible it was 0.039 and 0.052 (1,000 draws each), at a power cost of a few
    points (IC 0.05, n=1000: 0.47 -> 0.45).

    PASS needs the in-regime mean > 0, n_in >= min_in and charged p <= alpha. Fewer in-regime
    signals, a regime that is always or never on, or too short a history is UNMEASURED.
    """
    pos = np.asarray(sig_pos, dtype=int)
    ret = np.asarray(sig_ret, dtype=float)
    mask = np.asarray(bar_mask, dtype=bool)
    ok = np.isfinite(ret) & (pos >= 0) & (pos < mask.size)
    pos, ret = pos[ok], ret[ok]
    T = int(mask.size)
    duty = float(mask.mean()) if T else 0.0
    base: dict[str, Any] = {"n_signals": int(pos.size), "duty_cycle": round(duty, 4),
                            "n_trials": int(max(1, n_trials)), "n_masks": 0}
    if T < 20 or duty <= 0.0 or duty >= 1.0:
        return {**base, "verdict": "UNMEASURED", "n_in": int(mask[pos].sum()) if T else 0,
                "why": "the regime is never or always on over the history: nothing to condition"}
    inside = mask[pos]
    n_in = int(inside.sum())
    if n_in < min_in:
        return {**base, "verdict": "UNMEASURED", "n_in": n_in,
                "why": f"{n_in} parent signals inside the regime < {min_in}"}
    real = float(ret[inside].mean())
    rng = np.random.default_rng(seed)
    lo = max(1, int(T * min_shift_frac))
    shifts = rng.integers(lo, T - lo + 1, size=int(n_masks)) if T - lo >= lo else \
        rng.integers(1, T, size=int(n_masks))
    # mask shifted right by k: shifted[i] = mask[(i - k) mod T], read at every signal position.
    cnt = np.empty(shifts.size, dtype=float)
    sums = np.empty(shifts.size, dtype=float)
    for a in range(0, shifts.size, 128):                       # bounded memory per chunk
        hits = mask[(pos[None, :] - shifts[a:a + 128, None]) % T]
        cnt[a:a + 128] = hits.sum(axis=1)
        sums[a:a + 128] = hits.astype(float) @ ret
    valid = cnt >= max(1, min_in // 2)
    null = sums[valid] / cnt[valid]
    if null.size < 100:
        return {**base, "verdict": "UNMEASURED", "n_in": n_in, "mean_in": round(real, 6),
                "why": f"only {null.size} placebo regimes held enough signals"}
    p = float((1 + int((null >= real).sum())) / (1 + null.size))
    charged = min(1.0, p * max(1, int(n_trials)))
    passed = real > 0 and charged <= alpha
    # Power, as the point-biserial IC between "inside the regime" and the signal's return: the
    # smallest one detected with 80% power at this many signals and this charge (a lower bound:
    # a slow regime has fewer independent blocks than signals).
    mde = min_detectable_ic(int(pos.size), max(1, int(n_trials)), alpha=alpha, two_sided=False)
    under = not passed and mde is not None and mde > TARGET_IC
    verdict = "PASS" if passed else ("UNDERPOWERED" if under else "FAIL")
    return {**base, "verdict": verdict, "n_in": n_in,
            "min_detectable_ic": mde, "target_ic": TARGET_IC,
            "n_masks": int(null.size), "mean_in": round(real, 6),
            "mean_all": round(float(ret.mean()), 6),
            "placebo_mean": round(float(null.mean()), 6),
            "placebo_p95": round(float(np.quantile(null, 0.95)), 6),
            "p_placebo": round(p, 5), "p_charged": round(charged, 5),
            "why": (f"in-regime mean {real:+.5f} over {n_in} parent signals vs {null.size} "
                    f"circularly shifted regimes of duty {duty:.2f}: p {p:.4f}, Bonferroni over "
                    f"{max(1, int(n_trials))} children -> {charged:.4f}")}


# ============================================================================ power
def _sim_release(ic: float, n: int, rng: np.random.Generator, *, horizon: int = 5,
                 sigma: float = 0.001) -> tuple[list[tuple[Any, float]], pd.Series]:
    """n daily releases on hourly bars with a planted post-release IC of `ic` (Pearson on the
    window return; the entry is exactly the first bar the gate may trade)."""
    margin = 100                                   # days, covers the widest placebo shift
    t_bars = 24 * (n + 2 * margin)
    idx = pd.date_range("2015-01-01", periods=t_bars, freq="h", tz="UTC")
    r = rng.normal(0.0, sigma, t_bars)
    x = rng.normal(0.0, 1.0, n)
    pos = 24 * margin + 24 * np.arange(n)
    beta = ic * sigma * math.sqrt(horizon) / math.sqrt(max(1e-12, 1.0 - ic * ic))
    for k in range(1, horizon + 1):
        r[pos + k] += beta * x / horizon
    close = pd.Series(100.0 * np.exp(np.cumsum(r)), index=idx)
    pad = pd.Timedelta(hours=CLOCK_PAD_H)
    return [(idx[int(p)] - pad, float(v)) for p, v in zip(pos, x, strict=True)], close


def _sim_regime(ic: float, n: int, rng: np.random.Generator, *, duty: float = 0.4,
                block: int = 300, sigma: float = 0.004) -> tuple[np.ndarray, np.ndarray,
                                                                 np.ndarray]:
    """A slow regime (blocks of `block` bars, duty ~`duty`) and n parent signals whose return
    carries a planted point-biserial IC of `ic` with being inside the regime."""
    t_bars = max(20 * block, 12 * n)
    mask = np.repeat(rng.random(t_bars // block + 1) < duty, block)[:t_bars]
    pos = np.sort(rng.choice(t_bars, n, replace=False))
    inside = mask[pos].astype(float)
    p = float(inside.mean()) if 0 < inside.mean() < 1 else duty
    delta = ic * sigma / math.sqrt(p * (1 - p)) / math.sqrt(max(1e-12, 1.0 - ic * ic))
    ret = rng.normal(0.0, sigma, n) + delta * inside
    return pos, ret, mask


def power_table(ics: Sequence[float] = (0.0, 0.05, 0.10), ns: Sequence[int] = (250, 1000), *,
                n_sims: int = 100, n_cells: int = 1, seed: int = 0,
                gates: Sequence[str] = ("release_gain", "regime_placebo"),
                regime_masks: int = 500) -> list[dict[str, Any]]:
    """Detection rate (share of PASS) of each gate at each planted IC and n, over `n_sims`
    synthetic draws. The ic=0 rows are the false-positive rate, which must stay <= alpha."""
    rows: list[dict[str, Any]] = []
    for gate in gates:
        for n in ns:
            for ic in ics:
                rng = np.random.default_rng([seed, int(n), round(ic * 1000),
                                             0 if gate == "release_gain" else 1])
                hits = under = 0
                for k in range(int(n_sims)):
                    if gate == "release_gain":
                        ev, close = _sim_release(ic, int(n), rng)
                        v = release_gain(ev, close, horizon_bars=5, n_cells=n_cells).verdict
                    else:
                        pos, ret, mask = _sim_regime(ic, int(n), rng)
                        v = str(regime_placebo(pos, ret, mask, n_trials=n_cells,
                                               n_masks=regime_masks, seed=k)["verdict"])
                    hits += v == "PASS"
                    under += v == "UNDERPOWERED"
                rows.append({"gate": gate, "n": int(n), "planted_ic": ic, "n_cells": n_cells,
                             "n_sims": int(n_sims),
                             "pass_rate": round(hits / max(1, n_sims), 4),
                             "underpowered_rate": round(under / max(1, n_sims), 4),
                             "min_detectable_ic": min_detectable_ic(
                                 int(n), n_cells, two_sided=gate == "release_gain")})
    return rows
