"""WORLDQUANT-STYLE CROSS-SECTIONAL SETTINGS: group neutralisation, linear decay, truncation.

THE GAP (N8 donor diff, #1020: `wq_group_neutralization` and `wq_decay_truncation` read PARTIAL).
A WorldQuant BRAIN alpha is a cross-sectional vector per date, and three SETTINGS turn it into a
book before it is judged:

  * NEUTRALISATION -- the vector is demeaned within a group (the whole market, or each sector /
    industry), so the alpha bets on relative moves inside the group and not on the group's common
    move. The desk's DSL transpiled `IndNeutralize(x, IndClass.*)` to `xzscore`, a z-score across
    the whole MetaTrader asset-class basket: market neutralisation, one level coarser than the
    paper asks. `neutralize(..., level="group")` demeans and scales within each PEER CLASS
    (`universe_policy.peer_class`: fx_usd / fx_cross / index / commodity / ...), the desk's own
    sector, and falls back to the basket for a member whose group is thinner than `min_members`
    (a one-member group demeaned is identically zero -- a dead signal, not a neutral one).
  * DECAY -- a linearly weighted average of the last `d` vectors (weights d, d-1, ..., 1), which
    trades a little signal freshness for much less turnover. The grammar's `decay` operator is the
    same arithmetic on one series; `decay_linear` is it applied to a panel, so a book can carry it.
  * TRUNCATION -- after the vector is scaled to unit gross (sum |w| = 1), no member may hold more
    than `max_weight` of it; the excess is redistributed to the others pro rata, iteratively, so
    the book stays fully invested at unit gross. It changes the SHAPE of a research signal before
    the gauntlet judges it; it is a parameter the gauntlet sees both values of, never a rail on
    live capital, and it is off (None) unless a cell names it.

Pure functions over a time x symbol DataFrame. Nothing here reads the disk, sizes a position or
touches a gate. NaN in means NaN out for that member at that date; a row with no finite member is
all NaN, never zero.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

import numpy as np
import pandas as pd

__all__ = ["LEVELS", "apply_settings", "decay_linear", "neutralize", "truncate",
           "unit_gross"]

Level = Literal["none", "market", "group"]
LEVELS: tuple[str, ...] = ("none", "market", "group")
#: A group thinner than this at a date is neutralised against the whole basket instead.
MIN_GROUP_MEMBERS = 3


def _row_z(vals: np.ndarray, scale: bool) -> np.ndarray:
    """Demean (and optionally scale) each row over its finite entries; NaN where < 2 finite."""
    finite = np.isfinite(vals)
    n = finite.sum(axis=1)
    masked = np.where(finite, vals, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = masked.sum(axis=1) / n
        out = vals - mean[:, None]
        if scale:
            var = np.where(finite, out, 0.0) ** 2
            sd = np.sqrt(var.sum(axis=1) / n)
            out = out / np.where(sd > 1e-12, sd, np.nan)[:, None]
    out[~finite] = np.nan
    out[n < 2, :] = np.nan
    return np.asarray(out)


def neutralize(panel: pd.DataFrame, groups: Mapping[str, str | None] | None = None, *,
               level: str = "group", scale: bool = True,
               min_members: int = MIN_GROUP_MEMBERS) -> pd.DataFrame:
    """The panel demeaned (and z-scaled when `scale`) within each member's group at each date.

    `level="market"` treats the whole panel as one group; `"none"` returns the panel unchanged.
    `level="group"` needs `groups` (symbol -> group label); a member with no label, or whose group
    has fewer than `min_members` finite members at a date, is neutralised against the members that
    have no usable group of their own pooled with the whole basket -- i.e. the market level -- so
    a thin group is never silently zeroed.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown neutralisation level {level!r}; one of {LEVELS}")
    if level == "none" or panel.empty:
        return panel.copy()
    vals = panel.to_numpy(dtype=float)
    market = _row_z(vals, scale)
    if level == "market":
        return pd.DataFrame(market, index=panel.index, columns=panel.columns)
    if groups is None:
        raise ValueError("level='group' needs a groups mapping")
    out = market.copy()
    labels = [groups.get(str(c)) for c in panel.columns]
    for g in {lab for lab in labels if lab}:
        cols = [j for j, lab in enumerate(labels) if lab == g]
        sub = vals[:, cols]
        z = _row_z(sub, scale)
        enough = np.isfinite(sub).sum(axis=1) >= max(2, min_members)
        for k, j in enumerate(cols):
            out[enough, j] = z[enough, k]
    return pd.DataFrame(out, index=panel.index, columns=panel.columns)


def decay_linear(panel: pd.DataFrame, d: int) -> pd.DataFrame:
    """Linearly weighted mean of the last `d` rows (newest weight d). `d <= 1` is the identity.

    A member missing at a lag contributes nothing at that lag and the weights renormalise over the
    lags it has, as BRAIN's decay does; a member with no finite value in the window is NaN."""
    if d <= 1 or panel.empty:
        return panel.copy()
    acc = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    wsum = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    for k in range(d):
        lag = panel.shift(k)
        w = float(d - k)
        have = lag.notna()
        acc = acc + lag.fillna(0.0) * w
        wsum = wsum + have.astype(float) * w
    return acc / wsum.where(wsum > 0)


def unit_gross(panel: pd.DataFrame) -> pd.DataFrame:
    """Each row scaled so sum |w| = 1 over its finite members; an all-zero row is NaN."""
    gross = panel.abs().sum(axis=1, min_count=1)
    return panel.div(gross.where(gross > 1e-12), axis=0)


def truncate(weights: pd.DataFrame, max_weight: float | None, *,
             max_iter: int = 50) -> pd.DataFrame:
    """Unit-gross weights with no |w| above `max_weight`, the excess redistributed pro rata.

    The cap is applied to magnitudes and the sign kept. Redistribution repeats until no member is
    over the cap (each round moves excess only onto members still under it), so the result stays
    at unit gross. When the cap is infeasible (fewer than 1 / max_weight finite members) every
    member sits at the equal weight 1 / n, which is the most a cap can do without leaving the
    book under-invested. `None` returns `unit_gross(weights)` -- truncation off.
    """
    w = unit_gross(weights)
    if max_weight is None:
        return w
    if not 0.0 < float(max_weight) <= 1.0 or math.isnan(float(max_weight)):
        raise ValueError(f"max_weight must be in (0, 1], got {max_weight!r}")
    cap = float(max_weight)
    vals = w.to_numpy(dtype=float, copy=True)
    for i in range(vals.shape[0]):
        row = vals[i]
        fin = np.isfinite(row)
        n = int(fin.sum())
        if n == 0:
            continue
        mag = np.abs(row[fin])
        sign = np.sign(row[fin])
        if cap * n < 1.0 - 1e-12:            # infeasible: equal weight is the closest feasible
            vals[i, fin] = sign / n
            continue
        for _ in range(max_iter):
            over = mag > cap + 1e-12
            if not over.any():
                break
            excess = float((mag[over] - cap).sum())
            mag[over] = cap
            free = ~over & (mag < cap - 1e-12)
            base = float(mag[free].sum())
            if base <= 1e-12:
                mag[free] += excess / max(int(free.sum()), 1)
            else:
                mag[free] += excess * mag[free] / base
        vals[i, fin] = sign * mag
    return pd.DataFrame(vals, index=w.index, columns=w.columns)


def apply_settings(panel: pd.DataFrame, groups: Mapping[str, str | None] | None = None, *,
                   neutralization: str = "market", decay: int = 0,
                   truncation: float | None = None) -> pd.DataFrame:
    """BRAIN's order: decay the raw vector, neutralise it, scale to unit gross, truncate."""
    x = decay_linear(panel, decay)
    x = neutralize(x, groups, level=neutralization, scale=False)
    return truncate(x, truncation)
