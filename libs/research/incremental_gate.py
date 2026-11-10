"""BEFORE THE GAUNTLET: does a released series add anything to what the instrument already knows,
does it survive a battery of placebos, and how many trials did the search really spend?

WHY (DATA-47, principal 2026-10-07: "charge source x transform x asset x horizon x session x
state x threshold x lag x interaction trials; placebo battery per alt family; base vs base+new
incremental gate before expensive gauntlet work"). `release_gain` already asks one question of a
released alternative-data series -- does its surprise's IC on the post-release return beat the
same surprises on shifted dates -- and charges a Bonferroni over the cells tested. Three things
were missing, and each lets a cell reach the gauntlet that should not:

    INCREMENTAL   a surprise that only restates the instrument's own recent move (a trending
                  series released into a trending tape) passes an IC test and adds nothing. The
                  gate fits the forward return on the BASE (the instrument's own pre-release
                  returns over the horizon and over one day) and on BASE + SURPRISE: the partial
                  F of the surprise, Bonferroni-charged over the cells tested, must clear alpha
                  AND the surprise must lower the squared error out of sample (fit on the first
                  60% of windows in time, scored on the last 40%).
    BATTERY       the date-shift placebo keeps the values and moves the dates. Three more, each
                  destroying a different thing: VALUE_PERMUTATION (the surprises reassigned across
                  the same windows), SIGN_FLIP (each surprise's sign by a fair coin -- keeps the
                  magnitudes, destroys direction), and PRE_RELEASE (the same surprise against the
                  return that ENDED at release -- a series that "predicts" the move it was
                  published after is restating the tape, not informing it).
    TRIAL GRID    every tested cell carries its coordinates on the nine axes the principal named,
                  so the charge can be audited per axis: the number of trials a pass charged must
                  be at least the number of distinct coordinates it tested, or the census says
                  UNDER_CHARGED by name.

UNMEASURED is a verdict (L1.28a): too few windows, a degenerate base, or a placebo that could not
be formed is never a pass and never a fail. Pure numpy/pandas, no desk paths: testable on a
planted tape.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

PASS, FAIL, UNMEASURED = "PASS", "FAIL", "UNMEASURED"
#: The nine axes a trial is charged on (DATA-47).
AXES: tuple[str, ...] = ("source", "transform", "asset", "horizon", "session", "state",
                         "threshold", "lag", "interaction")
ALPHA = 0.05
MIN_EVENTS = 24
TRAIN_SHARE = 0.6
#: One day of H1 bars: the short base lag.
SHORT_LAG_BARS = 24
N_PERMUTATIONS = 199


def _ts(when: Any) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(when)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def event_frame(events: Sequence[tuple[Any, float]], close: pd.Series, horizon_bars: int, *,
                clock_pad_h: int = 3, short_lag: int = SHORT_LAG_BARS) -> pd.DataFrame:
    """One row per non-overlapping post-release window: the surprise `x`, the forward log return
    `y` (entry close to the close `horizon_bars` later, the window `release_gain` scores), and the
    BASE the instrument already knew at entry -- `pre_h` (log return over the `horizon_bars` that
    ended at entry) and `pre_s` (over the last `short_lag` bars). Windows without that much
    history are dropped, never padded."""
    idx = pd.DatetimeIndex(close.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    px = close.to_numpy(dtype=float)
    rows: list[tuple[pd.Timestamp, float]] = []
    for when, s in events:
        ts = _ts(when)
        if ts is None or s is None or not math.isfinite(float(s)):
            continue
        rows.append((ts + pd.Timedelta(hours=int(clock_pad_h)), float(s)))
    rows.sort(key=lambda r: r[0])
    out: list[dict[str, float]] = []
    free_from = -1
    lag = max(int(horizon_bars), int(short_lag))
    for ts, s in rows:
        pos = int(idx.searchsorted(ts, side="left"))
        end = pos + int(horizon_bars)
        if pos - lag < 0 or end >= len(idx) or pos < free_from:
            continue
        a, b = px[pos], px[end]
        h0, s0 = px[pos - int(horizon_bars)], px[pos - int(short_lag)]
        if not all(np.isfinite(v) and v > 0 for v in (a, b, h0, s0)):
            continue
        out.append({"x": s, "y": math.log(b / a), "pre_h": math.log(a / h0),
                    "pre_s": math.log(a / s0)})
        free_from = end
    return pd.DataFrame(out, columns=["x", "y", "pre_h", "pre_s"])


def _rank_ic(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 3 or a.size != b.size:
        return None
    ra = pd.Series(a).rank().to_numpy(dtype=float)
    rb = pd.Series(b).rank().to_numpy(dtype=float)
    if float(np.std(ra)) == 0.0 or float(np.std(rb)) == 0.0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _ols_sse(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return beta, float(resid @ resid)


def _f_sf(f: float, d1: int, d2: int) -> float:
    """Upper tail of F(d1, d2) through the regularized incomplete beta (no scipy needed)."""
    if not math.isfinite(f) or f <= 0:
        return 1.0
    x = d2 / (d2 + d1 * f)
    return _betainc(d2 / 2.0, d1 / 2.0, x)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) by Lentz's continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _betainc(b, a, 1.0 - x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        num = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c if abs(c) > tiny else tiny
        h *= d * c
        num = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0))
        d = 1.0 + num * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + num / c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return float(min(1.0, max(0.0, front * h / a)))


def incremental_gain(frame: pd.DataFrame, *, n_cells: int = 1, alpha: float = ALPHA,
                     min_events: int = MIN_EVENTS) -> dict[str, Any]:
    """BASE vs BASE + SURPRISE on the post-release return: charged partial F and out-of-sample
    squared error. PASS needs both."""
    n = len(frame)
    if n < min_events:
        return {"verdict": UNMEASURED, "n": n, "why": f"{n} windows < {min_events}"}
    y = frame["y"].to_numpy(dtype=float)
    base = np.column_stack([np.ones(n), frame["pre_h"].to_numpy(float),
                            frame["pre_s"].to_numpy(float)])
    full = np.column_stack([base, frame["x"].to_numpy(float)])
    if np.linalg.matrix_rank(full) < full.shape[1]:
        return {"verdict": UNMEASURED, "n": n,
                "why": "the surprise or the base is degenerate (rank-deficient design)"}
    _, sse_b = _ols_sse(base, y)
    _, sse_f = _ols_sse(full, y)
    d2 = n - full.shape[1]
    f = ((sse_b - sse_f) / 1.0) / (sse_f / d2) if sse_f > 0 and d2 > 0 else float("inf")
    p_f = _f_sf(f, 1, d2) if d2 > 0 else 1.0
    p_charged = min(1.0, p_f * max(1, int(n_cells)))
    k = int(n * TRAIN_SHARE)
    if n - k < 8:
        return {"verdict": UNMEASURED, "n": n, "why": "too few windows to hold any out"}
    bb, _ = _ols_sse(base[:k], y[:k])
    bf, _ = _ols_sse(full[:k], y[:k])
    oos_b = float(np.sum((y[k:] - base[k:] @ bb) ** 2))
    oos_f = float(np.sum((y[k:] - full[k:] @ bf) ** 2))
    r2_b = 1.0 - sse_b / float(np.sum((y - y.mean()) ** 2)) if np.var(y) > 0 else 0.0
    r2_f = 1.0 - sse_f / float(np.sum((y - y.mean()) ** 2)) if np.var(y) > 0 else 0.0
    ok = p_charged <= alpha and oos_f < oos_b
    why = (f"partial F {f:.2f} (p {p_f:.4g}, x{max(1, int(n_cells))} cells -> {p_charged:.4g}); "
           f"held-out SSE {oos_b:.4g} -> {oos_f:.4g}")
    return {"verdict": PASS if ok else FAIL, "n": n, "f": round(f, 4) if math.isfinite(f)
            else None, "p_f": p_f, "p_charged": p_charged, "delta_r2": round(r2_f - r2_b, 6),
            "oos_sse_base": oos_b, "oos_sse_full": oos_f, "n_train": k, "why": why}


def placebo_battery(frame: pd.DataFrame, *, seed: int = 0, n_perm: int = N_PERMUTATIONS,
                    alpha: float = ALPHA, min_events: int = MIN_EVENTS) -> dict[str, Any]:
    """Three placebos beyond the date shift. PASS needs the real IC to beat each one."""
    n = len(frame)
    if n < min_events:
        return {"verdict": UNMEASURED, "n": n, "why": f"{n} windows < {min_events}"}
    x = frame["x"].to_numpy(float)
    y = frame["y"].to_numpy(float)
    ic = _rank_ic(x, y)
    if ic is None:
        return {"verdict": UNMEASURED, "n": n, "why": "no rank correlation exists"}
    rng = np.random.default_rng(seed)
    perm, flip = [], []
    for _ in range(n_perm):
        pi = _rank_ic(rng.permutation(x), y)
        if pi is not None:
            perm.append(abs(pi))
        fi = _rank_ic(x * rng.choice((-1.0, 1.0), size=n), y)
        if fi is not None:
            flip.append(abs(fi))
    p_perm = (1 + sum(v >= abs(ic) for v in perm)) / (1 + len(perm))
    p_flip = (1 + sum(v >= abs(ic) for v in flip)) / (1 + len(flip))
    pre = _rank_ic(x, frame["pre_h"].to_numpy(float))
    legs: dict[str, dict[str, Any]] = {
        "value_permutation": {"p": round(p_perm, 4), "ok": p_perm <= alpha},
        "sign_flip": {"p": round(p_flip, 4), "ok": p_flip <= alpha},
        "pre_release": {"ic_pre": None if pre is None else round(pre, 4),
                        "ok": pre is not None and abs(pre) < abs(ic)},
    }
    bad = [k for k, v in legs.items() if not v["ok"]]
    return {"verdict": FAIL if bad else PASS, "n": n, "ic": round(ic, 4), "legs": legs,
            "failed": bad,
            "why": ("beats value permutation, sign flip and the pre-release window" if not bad
                    else f"does not beat: {', '.join(bad)}")}


def admit(events: Sequence[tuple[Any, float]], close: pd.Series, *, horizon_bars: int,
          n_cells: int = 1, seed: int = 0, clock_pad_h: int = 3) -> dict[str, Any]:
    """The pre-gauntlet admission: incremental gain AND the placebo battery."""
    frame = event_frame(events, close, horizon_bars, clock_pad_h=clock_pad_h)
    inc = incremental_gain(frame, n_cells=n_cells)
    bat = placebo_battery(frame, seed=seed)
    vs = (inc["verdict"], bat["verdict"])
    verdict = FAIL if FAIL in vs else PASS if vs == (PASS, PASS) else UNMEASURED
    return {"verdict": verdict, "incremental": inc, "battery": bat}


def trial(**coords: Any) -> dict[str, str]:
    """One trial's coordinates on the nine axes; an axis not given is `-` (not varied)."""
    unknown = set(coords) - set(AXES)
    if unknown:
        raise ValueError(f"unknown trial axes {sorted(unknown)}; the axes are {AXES}")
    return {a: str(coords.get(a, "-")) for a in AXES}


def grid_census(trials: Iterable[Mapping[str, Any]], charged: int) -> dict[str, Any]:
    """Per-axis distinct values, the distinct coordinates tested, and whether `charged` (the
    multiplicity the pass actually applied) covers them."""
    rows = [tuple(str(t.get(a, "-")) for a in AXES) for t in trials]
    distinct = len(set(rows))
    per_axis = {a: len({r[i] for r in rows}) for i, a in enumerate(AXES)}
    return {"axes": list(AXES), "per_axis_distinct": per_axis, "tested": len(rows),
            "distinct_coordinates": distinct, "charged": int(charged),
            "verdict": (UNMEASURED if not rows else
                        "CHARGED" if int(charged) >= distinct else "UNDER_CHARGED"),
            "rule": "the multiplicity charged must be at least the distinct coordinates tested"}
