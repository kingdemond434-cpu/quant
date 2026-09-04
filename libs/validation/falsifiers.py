"""Executable objections: every "maybe it's just X" becomes a test, ordered by information
per second.

The adversarial scientists -- skeptic, leakage prosecutor, cost specialist, regime analyst,
statistician, execution specialist, portfolio scientist -- do not vote. Each objection is a
FALSIFIER: a function of (bars, signals, cost) that returns a verdict, with a declared cost in
seconds and a prior kill rate from the graveyard's failure classes, so the scheduler runs the
cheapest most-lethal test first:

    order = argsort( -P(kill | class) / cost_s )         with the pre-mortem's class first

    cost_surface        net expectancy at 1x / 1.5x / 2x the modelled round trip
    half_stability      both halves of the history carry the edge (sign and magnitude)
    truncation          the lookahead sentinel (libs.validation.lookahead)
    usd_residual        the signal's P&L survives regressing out the USD driver's returns
    tail_worst_decile   the worst-decile trade cluster does not hold the whole edge
    placebo_battery     the red team's entry-shift / side-flip / random-entry controls

A candidate that fails a falsifier is not deleted -- the gauntlet decides -- but the failure is
written with the falsifier's name, which is what the graveyard model learns from.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pandas as pd

#: (declared cost in seconds, prior P(kill) for the class it targets)
CATALOGUE: dict[str, tuple[float, str]] = {
    "cost_surface": (0.5, "COST_DEATH"),
    "half_stability": (1.0, "STATE_FRAGILE"),
    "truncation": (2.0, "LEAKAGE"),
    "usd_residual": (1.0, "CORRELATION_DUPLICATE"),
    "tail_worst_decile": (0.5, "TAIL_FAILURE"),
    "placebo_battery": (20.0, "LEAKAGE"),
}
DEFAULT_KILL: dict[str, float] = {"COST_DEATH": 0.35, "STATE_FRAGILE": 0.25, "LEAKAGE": 0.10,
                                  "CORRELATION_DUPLICATE": 0.20, "TAIL_FAILURE": 0.15}


def _trade_returns(df: pd.DataFrame, signals: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    """Non-overlapping forward log returns at each signal's own TTL, and their bar indices."""
    idx = df.index
    o = df["open"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    pos = {ts: i for i, ts in enumerate(idx)}
    rs, at = [], []
    last = -1
    for s in sorted(signals, key=lambda x: x.time):
        i = pos.get(s.time)
        if i is None or i + 1 >= len(o) or i + 1 <= last:
            continue
        e = i + 1
        x = min(e + max(1, int(s.ttl_bars)), len(c) - 1)
        if o[e] <= 0:
            continue
        r = math.log(c[x] / o[e]) * int(s.side)
        if math.isfinite(r):
            rs.append(r)
            at.append(e)
            last = x
    return np.asarray(rs, dtype=float), np.asarray(at, dtype=int)


def _t(x: np.ndarray) -> float:
    if x.size < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(x.size)))


def cost_surface(df: pd.DataFrame, signals: Sequence[Any], cost: float,
                 **_kw: Any) -> dict[str, Any]:
    r, _ = _trade_returns(df, signals)
    if r.size < 20:
        return {"verdict": "UNMEASURED", "n": int(r.size)}
    rows = {f"{m:.1f}x": round(float(r.mean() - m * cost), 8) for m in (1.0, 1.5, 2.0)}
    return {"verdict": "PASS" if rows["1.0x"] > 0 else "FAIL", "net_by_cost": rows,
            "survives_1.5x": rows["1.5x"] > 0, "survives_2x": rows["2.0x"] > 0, "n": int(r.size)}


def half_stability(df: pd.DataFrame, signals: Sequence[Any], cost: float,
                   **_kw: Any) -> dict[str, Any]:
    r, at = _trade_returns(df, signals)
    if r.size < 40:
        return {"verdict": "UNMEASURED", "n": int(r.size)}
    mid = len(df) // 2
    a, b = r[at < mid] - cost, r[at >= mid] - cost
    ta, tb = _t(a), _t(b)
    return {"verdict": "PASS" if (ta > 0 and tb > 0) else "FAIL",
            "t_first_half": round(ta, 2), "t_second_half": round(tb, 2),
            "n": [int(a.size), int(b.size)]}


def truncation(df: pd.DataFrame, signals: Sequence[Any], cost: float, *,
               family: Callable[..., Sequence[Any]] | None = None,
               params: dict[str, Any] | None = None, **_kw: Any) -> dict[str, Any]:
    if family is None:
        return {"verdict": "UNMEASURED", "why": "no family callable supplied"}
    from libs.validation.lookahead import truncation_test
    out = truncation_test(family, df, len(df) * 2 // 3, **(params or {}))
    return {"verdict": "PASS" if out["ok"] else "FAIL", **out}


def usd_residual(df: pd.DataFrame, signals: Sequence[Any], cost: float, *,
                 usd: pd.DataFrame | None = None, **_kw: Any) -> dict[str, Any]:
    if usd is None or "close" not in usd.columns:
        return {"verdict": "UNMEASURED", "why": "no USD driver bars supplied"}
    r, at = _trade_returns(df, signals)
    if r.size < 30:
        return {"verdict": "UNMEASURED", "n": int(r.size)}
    u = usd["close"].astype(float)
    u.index = pd.DatetimeIndex(pd.to_datetime(u.index, utc=True, errors="coerce"))
    u = u.reindex(df.index, method="ffill")
    ur = np.log(u).diff().to_numpy(dtype=float)
    x = np.array([np.nansum(ur[e:e + 6]) for e in at])
    ok = np.isfinite(x)
    r, x = r[ok], x[ok]
    if x.std() == 0:
        return {"verdict": "UNMEASURED", "why": "USD driver flat over the trades"}
    beta = float(np.cov(r, x)[0, 1] / np.var(x, ddof=1))
    resid = r - beta * x
    return {"verdict": "PASS" if _t(resid - cost) > 2.0 else "FAIL", "beta_usd": round(beta, 4),
            "t_raw": round(_t(r - cost), 2), "t_residual": round(_t(resid - cost), 2),
            "n": int(r.size)}


def tail_worst_decile(df: pd.DataFrame, signals: Sequence[Any], cost: float,
                      **_kw: Any) -> dict[str, Any]:
    r, _ = _trade_returns(df, signals)
    if r.size < 30:
        return {"verdict": "UNMEASURED", "n": int(r.size)}
    k = max(1, r.size // 10)
    best = np.sort(r)[::-1][:k]
    without = np.sort(r)[::-1][k:]
    share = float(best.sum() / r.sum()) if r.sum() > 0 else float("inf")
    return {"verdict": "PASS" if (without.mean() - cost) > 0 else "FAIL",
            "top_decile_share_of_pnl": round(share, 3),
            "net_without_top_decile": round(float(without.mean() - cost), 8), "n": int(r.size)}


def placebo_battery(df: pd.DataFrame, signals: Sequence[Any], cost: float,
                    **_kw: Any) -> dict[str, Any]:
    try:
        from libs.validation.redteam import run as redteam_run
    except Exception:
        return {"verdict": "UNMEASURED", "why": "red team unavailable"}

    def _score(sigs: Sequence[Any]) -> float:
        r, _ = _trade_returns(df, sigs)
        return float(r.mean() - cost) if r.size else float("nan")
    try:
        out = redteam_run(df, list(signals), _score)
    except Exception as exc:
        return {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    v = str(getattr(out, "verdict", ""))
    return {"verdict": ("PASS" if v == "DISTINGUISHED" else
                        ("FAIL" if v == "UNDISTINGUISHED" else "UNMEASURED")),
            "redteam": v, "why": getattr(out, "why", "")}


FALSIFIERS: dict[str, Callable[..., dict[str, Any]]] = {
    "cost_surface": cost_surface, "half_stability": half_stability, "truncation": truncation,
    "usd_residual": usd_residual, "tail_worst_decile": tail_worst_decile,
    "placebo_battery": placebo_battery,
}


def schedule(premortem: dict[str, Any] | None = None,
             kill_rates: dict[str, float] | None = None) -> list[str]:
    """Cheapest, most lethal first; the pre-mortem's own class jumps the queue."""
    kr = {**DEFAULT_KILL, **(kill_rates or {})}
    first = str((premortem or {}).get("failure_class") or "")
    order = sorted(CATALOGUE, key=lambda n: -(kr.get(CATALOGUE[n][1], 0.1) / CATALOGUE[n][0]))
    if first:
        head = [n for n in order if CATALOGUE[n][1] == first]
        order = head + [n for n in order if n not in head]
    return order


def run(df: pd.DataFrame, signals: Sequence[Any], cost: float, *, stop_on_fail: bool = True,
        premortem: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    """Run the battery in schedule order; stop at the first kill when asked (successive halving)."""
    results: dict[str, Any] = {}
    order = schedule(premortem)
    killed_by = None
    t0 = time.monotonic()
    for name in order:
        results[name] = FALSIFIERS[name](df, signals, cost, **kw)
        if results[name].get("verdict") == "FAIL":
            killed_by = name
            if stop_on_fail:
                break
    return {"order": order, "results": results, "killed_by": killed_by,
            "verdict": "KILLED" if killed_by else "SURVIVED",
            "seconds": round(time.monotonic() - t0, 3)}
