"""THE PERFECT-INFORMATION CEILING: what knowing the true state EARLY would have been worth.

THE QUESTION BEFORE ANY SENSOR (owner's brief, 2026-10-13). Before money and compute go into a
sensor that estimates a hidden state -- Cushing crude stocks from tank shadows, a port's throughput
from ship counts -- ask what a PERFECT reading of that state would have been worth if it had been
known k days before the official number. A proxy can never beat its own ceiling: it carries the
state plus measurement error, so its predictive content is at most the state's. If the ceiling is
NO_GAIN for an asset, no sensor of that state is worth judging on that asset, and the factory says
so per (sensor x entity x asset) instead of spending the gauntlet's trial budget on it.

THE TEST. Events i carry the official value ``s_i`` (e.g. the weekly change in Cushing stocks)
and its release instant ``R_i``. For each lead ``k`` (days before release) the oracle enters the
asset at the last bar at or before ``R_i - k`` and exits at the first bar at or after
``R_i + hold``. Over the events:

  rho_k          Spearman rank correlation of s_i with the oracle-window return (two-sided)
  p_k            its permutation p (the returns are shuffled against the values), two-sided
  kelly_k        annualised full-Kelly growth of trading sign(rho_k) * sign(s_i - median) per
                 event, the same growth arithmetic as `sensor_engines.kelly_growth`, scaled by
                 events per year rather than trading days
  verdict_k      GAIN when n >= min_n and p_k * n_leads < alpha (Bonferroni over the leads tried),
                 NO_GAIN otherwise, UNMEASURED below min_n -- never a zero and never a pass

The overall verdict is GAIN when any lead is GAIN. The sign of rho is reported, never assumed: a
stock BUILD is bearish for crude in the textbook, and the ceiling measures whether the book's asset
agrees. The row shape matches `sensor_engines.contract` (engine, metric, baseline, falsifier,
value, baseline_value, gain, null_p, n, min_n, verdict) so one reader can rank both.

This is an UPPER BOUND, by construction generous (the sign is chosen in-sample): a GAIN here is a
licence to look, never evidence of an edge; a NO_GAIN is a reason not to.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
GAIN = "GAIN"
NO_GAIN = "NO_GAIN"
ALPHA = 0.05
MIN_N = 50
N_NULL = 1000
EVENTS_PER_YEAR_DEFAULT = 52.0


def _rank(x: np.ndarray) -> np.ndarray:
    order = x.argsort(kind="mergesort")
    r = np.empty(x.size, dtype=float)
    r[order] = np.arange(x.size, dtype=float)
    return r


def spearman_perm(x: Sequence[float] | np.ndarray, y: Sequence[float] | np.ndarray,
                  n_null: int = N_NULL, seed: int = 17
                  ) -> tuple[float | None, float | None, int]:
    """(rho, two-sided permutation p, n) over the finite pairs."""
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = int(a.size)
    if n < 3:
        return None, None, n
    ra, rb = _rank(a), _rank(b)
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    if den <= 0:
        return 0.0, 1.0, n
    rho = float((ra * rb).sum() / den)
    rng = np.random.default_rng(seed)
    hits = sum(int(abs(float((ra * rng.permutation(rb)).sum()) / den) >= abs(rho) - 1e-12)
               for _ in range(n_null))
    return rho, (hits + 1) / (n_null + 1), n


def kelly_growth_events(payoff: Sequence[float], per_year: float) -> float | None:
    """Annualised full-Kelly log growth of a per-event payoff: per_year * mu^2 / (2 sigma^2),
    signed by mu (the `sensor_engines.kelly_growth` arithmetic on an event clock)."""
    p = np.asarray(payoff, dtype=float)
    p = p[np.isfinite(p)]
    if p.size < 2:
        return None
    mu, sd = float(p.mean()), float(p.std(ddof=1))
    if sd <= 0 or not math.isfinite(sd):
        return None
    return round(math.copysign(per_year * mu * mu / (2 * sd * sd), mu), 6)


def window_returns(times: Sequence[datetime], closes: Sequence[float],
                   releases: Sequence[datetime], lead_days: float, hold_hours: float
                   ) -> list[float]:
    """Log return from the last close at/before release - lead to the first close at/after
    release + hold; NaN when either end is missing or the bars do not span the window."""
    t = np.asarray([np.datetime64(x.replace(tzinfo=None), "s") for x in times])
    c = np.asarray(closes, dtype=float)
    out: list[float] = []
    for r in releases:
        rr = r.replace(tzinfo=None)
        t0 = np.datetime64(rr - timedelta(days=lead_days), "s")
        t1 = np.datetime64(rr + timedelta(hours=hold_hours), "s")
        i0 = int(np.searchsorted(t, t0, side="right")) - 1
        i1 = int(np.searchsorted(t, t1, side="left"))
        if i0 < 0 or i1 >= t.size or i1 <= i0:
            out.append(float("nan"))
            continue
        # a bar more than 4 days from either end is a gap, not the window's price
        if (t0 - t[i0]) > np.timedelta64(4, "D") or (t[i1] - t1) > np.timedelta64(4, "D"):
            out.append(float("nan"))
            continue
        a, b = c[i0], c[i1]
        out.append(math.log(b / a) if a > 0 and b > 0 else float("nan"))
    return out


def ceiling_test(state: Sequence[tuple[datetime, float]], times: Sequence[datetime],
                 closes: Sequence[float], *, leads_days: Sequence[float] = (1, 2, 3, 4, 5),
                 hold_hours: float = 24.0, min_n: int = MIN_N, alpha: float = ALPHA,
                 n_null: int = N_NULL, per_year: float = EVENTS_PER_YEAR_DEFAULT,
                 engine: str = "perfect_information_ceiling", entity: str = "",
                 asset: str = "") -> dict[str, Any]:
    """The ceiling for one (state series, asset): per-lead rows and the overall verdict.

    `state`: (official release instant, true value) pairs -- the value the world learned at that
    instant. `times`/`closes`: the asset's bars (UTC)."""
    releases = [r for r, _ in state]
    values = np.asarray([v for _, v in state], dtype=float)
    rows: list[dict[str, Any]] = []
    n_leads = max(len(leads_days), 1)
    for k in leads_days:
        rets = np.asarray(window_returns(times, closes, releases, float(k), hold_hours))
        rho, p, n = spearman_perm(values, rets, n_null=n_null)
        ok = np.isfinite(values) & np.isfinite(rets)
        sign = 0.0 if rho is None else math.copysign(1.0, rho) if rho != 0 else 0.0
        med = float(np.median(values[ok])) if ok.any() else 0.0
        payoff = sign * np.sign(values[ok] - med) * rets[ok]
        kg = kelly_growth_events(payoff, per_year) if n >= 2 else None
        p_adj = None if p is None else min(1.0, p * n_leads)
        if n < min_n or rho is None:
            verdict, why = UNMEASURED, f"n={n} < {min_n}"
        elif p_adj is not None and p_adj < alpha and (kg or 0) > 0:
            verdict, why = GAIN, ""
        else:
            verdict, why = NO_GAIN, f"p_bonferroni={p_adj}"
        rows.append({"engine": engine, "entity": entity, "asset": asset,
                     "metric": "spearman_rho_and_oracle_kelly", "lead_days": float(k),
                     "hold_hours": hold_hours, "baseline": "no information (rho = 0)",
                     "falsifier": "the state known k days early does not order the asset's "
                                  "return into the release",
                     "value": None if rho is None else round(rho, 6), "baseline_value": 0.0,
                     "gain": None if rho is None else round(abs(rho), 6),
                     "rho_sign": sign, "oracle_kelly_annual": kg, "null_p": p,
                     "null_p_bonferroni": p_adj, "n": int(n), "min_n": int(min_n),
                     "alpha": alpha, "verdict": verdict, "why": why})
    verdicts = [r["verdict"] for r in rows]
    if GAIN in verdicts:
        overall = GAIN
    elif rows and all(v == UNMEASURED for v in verdicts):
        overall = UNMEASURED
    elif NO_GAIN in verdicts:
        overall = NO_GAIN
    else:
        overall = UNMEASURED
    best = max((r for r in rows if r["value"] is not None), key=lambda r: abs(r["value"]),
               default=None)
    return {"engine": engine, "entity": entity, "asset": asset, "verdict": overall,
            "n_events": len(state), "n": max((r["n"] for r in rows), default=0),
            "best_lead_days": None if best is None else best["lead_days"],
            "best_rho": None if best is None else best["value"], "leads": rows}


def decision(ceiling: Mapping[str, Any]) -> dict[str, Any]:
    """May this sensor's cells on this asset be judged? Only where the ceiling shows GAIN."""
    v = str(ceiling.get("verdict") or UNMEASURED)
    return {"judge_cells": v == GAIN, "ceiling_verdict": v,
            "why": ("the perfect-information ceiling shows gain" if v == GAIN else
                    "the perfect-information ceiling is NO_GAIN: no proxy of this state can "
                    "beat it, so its cells are not worth the trial budget" if v == NO_GAIN else
                    "the ceiling is UNMEASURED: cells wait for it, they are not judged blind")}


__all__ = ["ALPHA", "GAIN", "MIN_N", "NO_GAIN", "UNMEASURED", "ceiling_test", "decision",
           "kelly_growth_events", "spearman_perm", "window_returns"]
