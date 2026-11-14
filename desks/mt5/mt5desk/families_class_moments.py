"""THREE CLASS BOOKS FROM THE PAPERSWITHBACKTEST LIST THE DESK COULD NOT EXPRESS (2026-10-06).

paperswithbacktest/awesome-systematic-trading indexes replicated papers (no licence; the list is an
index and nothing is copied). Three of its commodity strategies were missing as class ranks; each
is built here on the class panel `families_cross_sectional` already loads, one leg per cell, with
its helpers, so the same call builds the same signals in the gauntlet, the forward clock and the
executor:

    cross_sectional_class_skew     Fernandez-Perez, Frijns, Fuertes & Miffre (2018), "The skewness
        of commodity futures returns": investors with a taste for lottery-like payoffs overpay
        for positively skewed contracts. Long the members with the most negative trailing daily
        skew, short those with the most positive. Payer: the lottery-seeking speculator.
        (`skew_premium` holds a negatively skewed instrument on its own; this ranks the class.)
    cross_sectional_class_asymmetry  Return asymmetry (the "IE" of Jiang, Wu & Zhou 2018, carried
        to commodities): IE = days above mean + 2 sd minus days below mean - 2 sd over the last
        260 daily returns. Long the lowest-IE members, short the highest. Same payer, counted by
        tail days rather than the third moment, so one outlier does not decide the rank.
    cross_sectional_class_corr_momentum  Commodity momentum conditioned on intra-class correlation:
        when members move together the cross-section carries little idiosyncratic information and
        momentum is a bet on the factor. Momentum is taken only on days when the class's average
        correlation with its own equal-weight basket, read yesterday, is below its trailing
        median. Payer: the slow reallocator, as in class momentum.

These are NOT added to `universe_policy.CROSS_SECTIONAL_FAMILIES`: they are claims about commodity
classes, seeded on commodity legs only, so share CFDs never reach them.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal


def _trailing(col: np.ndarray, window: int) -> np.ndarray:
    """(rows, window) view of the trailing `window` values of one member ending at each row."""
    full = np.r_[np.full(window - 1, np.nan), col]
    return np.lib.stride_tricks.sliding_window_view(full, window)


def _column_stats(col: np.ndarray, window: int, k_sd: float,
                  min_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """One member's trailing skew and tail-day asymmetry (days > mean + k sd minus days <
    mean - k sd), NaN where fewer than `min_frac` of the window is valid."""
    w = _trailing(col, window)
    valid = np.isfinite(w)
    n = valid.sum(axis=1)
    x = np.where(valid, w, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = x.sum(axis=1) / n
        dev = np.where(valid, w - mu[:, None], 0.0)
        sd = np.sqrt((dev ** 2).sum(axis=1) / (n - 1))
        skew = ((dev ** 3).sum(axis=1) / n) / sd ** 3
        up = (valid & (dev > k_sd * sd[:, None])).sum(axis=1)
        dn = (valid & (dev < -k_sd * sd[:, None])).sum(axis=1)
    ok = (n >= int(window * min_frac)) & (sd > 0)
    return np.where(ok, skew, np.nan), np.where(ok, (up - dn).astype(float), np.nan)


def _stats(r: np.ndarray, window: int, k_sd: float = 2.0,
           min_frac: float = 0.8) -> tuple[np.ndarray, np.ndarray]:
    """Per row and member: trailing skew and asymmetry, member by member (bounded memory)."""
    skew = np.full(r.shape, np.nan)
    ie = np.full(r.shape, np.nan)
    for j in range(r.shape[1]):
        skew[:, j], ie[:, j] = _column_stats(r[:, j], window, k_sd, min_frac)
    return skew, ie


def family_cross_sectional_class_skew(
    df: pd.DataFrame, *, symbol: str = "", window_d: int = 260, hold_d: int = 21,
    quantile: float = 1 / 3, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s trailing daily skew is among the most negative of its class, short
    while among the most positive."""
    if not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(window_d) < 60:
        return []
    got = xs._prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    skew = _stats(xs._returns(panel["logv"]), int(window_d))[0]
    side = xs._rank_sides(-skew, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"xs_skew:{panel['klass']}:{window_d}")


def family_cross_sectional_class_asymmetry(
    df: pd.DataFrame, *, symbol: str = "", window_d: int = 260, k_sd: float = 2.0,
    hold_d: int = 21, quantile: float = 1 / 3, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s tail-day asymmetry (up-tail days minus down-tail days over the
    trailing `window_d`) is among the lowest of its class, short while among the highest."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(window_d) < 60
            or not float(k_sd) > 0):
        return []
    got = xs._prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    ie = _stats(xs._returns(panel["logv"]), int(window_d), float(k_sd))[1]
    side = xs._rank_sides(-ie, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"xs_asymmetry:{panel['klass']}:{window_d}")


def family_cross_sectional_class_corr_momentum(
    df: pd.DataFrame, *, symbol: str = "", lookback_d: int = 250, skip_d: int = 21,
    corr_d: int = 60, history_d: int = 250, hold_d: int = 21, quantile: float = 1 / 3,
    decision_hour: int = 22, max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Class momentum (`lookback_d` skipping `skip_d`) taken only when the class's average
    `corr_d`-day correlation with its basket, read yesterday, is below its trailing median."""
    if (not xs._valid_common(quantile, hold_d, stop_sd, rr) or int(lookback_d) < 20
            or int(corr_d) < 20 or int(history_d) < 60 or int(skip_d) < 0):
        return []
    got = xs._prepare(df, symbol, decision_hour, max_stale_h)
    if got is None:
        return []
    d, panel = got
    lv = panel["logv"]
    r = xs._returns(lv)
    basket = xs._ew_ex_self(r)
    both = np.isfinite(r) & np.isfinite(basket)
    rr_, bb = np.where(both, r, np.nan), np.where(both, basket, np.nan)
    mr, mb = xs._rolling(rr_, corr_d, "mean"), xs._rolling(bb, corr_d, "mean")
    cov = xs._rolling(rr_ * bb, corr_d, "mean") - mr * mb
    vr = xs._rolling(rr_ * rr_, corr_d, "mean") - mr * mr
    vb = xs._rolling(bb * bb, corr_d, "mean") - mb * mb
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where((vr > 0) & (vb > 0), cov / np.sqrt(vr * vb), np.nan)
    avg = xs._row_mean_std(corr, xs.MIN_MEMBERS)[0]
    high = xs._lagged_high(avg, int(history_d), None)
    gate = ~high & np.isfinite(pd.Series(avg).shift(1).to_numpy())
    score = xs._shift(lv, int(skip_d)) - xs._shift(lv, int(skip_d) + int(lookback_d))
    side = xs._rank_sides(score, panel["own"], quantile, gate)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr,
                       tag=f"xs_corr_momentum:{panel['klass']}:{lookback_d}")


CLASS_MOMENT_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "cross_sectional_class_skew": family_cross_sectional_class_skew,
    "cross_sectional_class_asymmetry": family_cross_sectional_class_asymmetry,
    "cross_sectional_class_corr_momentum": family_cross_sectional_class_corr_momentum,
}

ORIGIN = dict.fromkeys(CLASS_MOMENT_FAMILIES,
                       "github.com/paperswithbacktest/awesome-systematic-trading (no licence; "
                       "rewritten)")
CLASS_ONLY = dict.fromkeys(CLASS_MOMENT_FAMILIES, frozenset({"commodity"}))
PARAM_GRID: dict[str, dict[str, list]] = {
    "cross_sectional_class_skew": {"window_d": [260]},
    "cross_sectional_class_asymmetry": {"window_d": [260]},
    "cross_sectional_class_corr_momentum": {"lookback_d": [250]},
}
_PWB = {"source_culture": "academic/en", "participant_structure": "institutional_futures",
        "crowding_prior": "medium"}
CULTURE: dict[str, dict[str, str]] = {
    "cross_sectional_class_skew": {**_PWB, "failure_mode_hypothesis": (
        "fails when a supply shock makes the positively skewed contract the one that keeps "
        "rising, so the short leg is the crowd's correct bet")},
    "cross_sectional_class_asymmetry": {**_PWB, "failure_mode_hypothesis": (
        "fails when tail days cluster in one news event, so the count measures one day's "
        "repricing rather than a persistent preference")},
    "cross_sectional_class_corr_momentum": {**_PWB, "failure_mode_hypothesis": (
        "fails in a low-correlation regime that is low because the class is idle, where "
        "momentum has nothing to ride")},
}
