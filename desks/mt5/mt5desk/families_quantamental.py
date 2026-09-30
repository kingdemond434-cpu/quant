"""QUANTAMENTAL CLASS BOOKS: value, quality and earnings yield, ranked within the equity class.

WHY. The desk quotes 103 single-name share CFDs and until now ranked them on nothing but their own
prices (reports/asia_quant_gap_2026-09-30.md row 9: quantamental MISSING). Tier-1 equity books earn
their cross-sectional breadth from FUNDAMENTAL characteristics, which a price-only rank cannot see.
These families rank a share against the equity peer class on point-in-time SEC fundamentals
(`mt5desk/fundamentals_pit.py`, refreshed by `research/sec_fundamentals.py`) valued at the bar
store's own close on the decision bar.

ONE LEG PER CELL, BUILT FROM `symbol` ALONE. Like every class book here, a family loads its own
panel -- the equity class's closes from `data/universe/*_H1.parquet` via
`families_cross_sectional.class_panel`, and every member's fundamentals as known at each decision
stamp from `data/lake/fundamentals/sec_pit.parquet` -- so the sealed gauntlet builds a cell through
its ordinary `fn(h1, **params)` call.

THE FAMILIES AND THEIR PRIORS (written before any data was looked at):

  quantamental_value           Cheap relative to fundamentals beats dear: book-to-price
      (Fama & French 1992), sales-to-EV, and their composite with earnings yield (Asness,
      Moskowitz & Pedersen 2013). Payer: the extrapolator who overprices glamour.
  quantamental_quality         Profitable firms are under-priced relative to their profitability
      (Novy-Marx 2013 gross profitability; Asness, Frazzini & Pedersen 2019 quality-minus-junk).
      Payer: the lottery-seeking holder of junk.
  quantamental_earnings_yield  E/P rank (Basu 1977): trailing earnings against price, the
      simplest value signal and the one with the longest out-of-sample record.

NO LOOKAHEAD. A member's fundamentals at a stamp are the snapshot ACCEPTED by the SEC at or before
that stamp (never the period end), and a snapshot describing a period more than `max_age_d` days
old is absent from the cross-section rather than carried forward. The price is the member's own
bar as of the stamp, the same one the price-only class books read.

HONEST LIMITS. A family returns [] when the symbol is not a share CFD, has no fundamentals, or
fewer than MIN_MEMBERS members carry a finite characteristic that day. Foreign filers reporting in
another currency carry no USD facts and are simply absent (the coverage artifact names them).
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk import fundamentals_pit as fp
from mt5desk.families import Signal

#: The peer class these rank within.
KLASS = "equity"

PARAM_GRID: dict[str, dict[str, list]] = {
    "quantamental_value": {"metric": ["composite", "book_to_price", "sales_to_ev"],
                           "hold_d": [20, 60]},
    "quantamental_quality": {"metric": ["gross_margin", "roe", "operating_margin"],
                             "hold_d": [20, 60]},
    "quantamental_earnings_yield": {"hold_d": [20, 60], "quantile": [0.2, 1 / 3]},
}

_VALUE = ("earnings_yield", "book_to_price", "sales_to_ev")
_QUALITY = ("gross_margin", "roe", "operating_margin", "net_margin")


def _characteristic(panel: dict, name: str, max_age_d: float) -> np.ndarray:
    """rows x members: `name` for every member as known at each decision stamp."""
    stamps = panel["stamps"]
    out = np.full(panel["logv"].shape, np.nan, dtype="float64")
    for j, member in enumerate(panel["members"]):
        ok = fp.fresh(member, stamps, max_age_d)
        if not ok.any():
            continue
        if name in _QUALITY:
            v = fp.asof(member, stamps, name)
        else:
            with np.errstate(over="ignore", invalid="ignore"):
                price = np.exp(panel["logv"][:, j])
            v = fp.valuation(member, stamps, price)[name]
        out[:, j] = np.where(ok, v, np.nan)
    return out


def _cs_rank(m: np.ndarray) -> np.ndarray:
    """Per-row percentile rank in [0, 1] over finite entries (NaN elsewhere)."""
    frame = pd.DataFrame(m)
    return frame.rank(axis=1, pct=True).to_numpy()


def _run(df, symbol, score_fn, *, hold_d, quantile, decision_hour, max_stale_h, stop_sd, rr,
         tag) -> list[Signal]:
    if not xs._valid_common(quantile, hold_d, stop_sd, rr):
        return []
    if xs.class_of(symbol) != KLASS:
        return []
    if not symbol or str(symbol).upper() not in set(fp.covered_symbols()):
        return []
    got = xs._prepare(df, symbol, decision_hour, max_stale_h, klass=KLASS)
    if got is None:
        return []
    d, panel = got
    score = score_fn(panel)
    side = xs._rank_sides(score, panel["own"], quantile)
    return xs._signals(d, panel, side, hold_d=hold_d, stop_sd=stop_sd, rr=rr, tag=tag)


def family_quantamental_value(
    df: pd.DataFrame, *, symbol: str = "", metric: str = "composite", hold_d: int = 20,
    quantile: float = 1 / 3, max_age_d: float = 200.0, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol` is among the equity class's CHEAPEST on `metric` (book-to-price,
    sales-to-EV, or the mean rank of those two with earnings yield), short while among the
    dearest."""
    if metric not in ("composite", "book_to_price", "sales_to_ev"):
        return []

    def score(panel):
        if metric != "composite":
            return _characteristic(panel, metric, max_age_d)
        ranks = [_cs_rank(_characteristic(panel, m, max_age_d)) for m in _VALUE]
        stack = np.stack(ranks)
        n = np.isfinite(stack).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(n >= 2, np.nansum(stack, axis=0) / np.maximum(n, 1), np.nan)
        return mean
    return _run(df, symbol, score, hold_d=hold_d, quantile=quantile,
                decision_hour=decision_hour, max_stale_h=max_stale_h, stop_sd=stop_sd, rr=rr,
                tag=f"qm_value:{metric}")


def family_quantamental_quality(
    df: pd.DataFrame, *, symbol: str = "", metric: str = "gross_margin", hold_d: int = 20,
    quantile: float = 1 / 3, max_age_d: float = 200.0, decision_hour: int = 22,
    max_stale_h: float = 12.0, stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol` is among the equity class's MOST profitable on `metric` (gross margin,
    ROE, operating margin), short while among the least."""
    if metric not in _QUALITY:
        return []
    return _run(df, symbol, lambda p: _characteristic(p, metric, max_age_d), hold_d=hold_d,
                quantile=quantile, decision_hour=decision_hour, max_stale_h=max_stale_h,
                stop_sd=stop_sd, rr=rr, tag=f"qm_quality:{metric}")


def family_quantamental_earnings_yield(
    df: pd.DataFrame, *, symbol: str = "", hold_d: int = 20, quantile: float = 1 / 3,
    max_age_d: float = 200.0, decision_hour: int = 22, max_stale_h: float = 12.0,
    stop_sd: float = 3.0, rr: float = 2.0,
) -> list[Signal]:
    """Long while `symbol`'s trailing earnings yield (EPS_ttm / price) ranks in the top
    `quantile` of the equity class, short while in the bottom."""
    return _run(df, symbol, lambda p: _characteristic(p, "earnings_yield", max_age_d),
                hold_d=hold_d, quantile=quantile, decision_hour=decision_hour,
                max_stale_h=max_stale_h, stop_sd=stop_sd, rr=rr, tag="qm_earnings_yield")


QUANTAMENTAL_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "quantamental_value": family_quantamental_value,
    "quantamental_quality": family_quantamental_quality,
    "quantamental_earnings_yield": family_quantamental_earnings_yield,
}

FAMILY_CLASSES: dict[str, tuple[str, ...]] = dict.fromkeys(QUANTAMENTAL_FAMILIES, (KLASS,))

TARGETS: dict[str, dict[str, str]] = {
    "quantamental_value": {
        "cluster": "cross_sectional_fx",
        "prior": "cheap on point-in-time fundamentals beats dear (Fama & French 1992; AMP 2013)"},
    "quantamental_quality": {
        "cluster": "cross_sectional_fx",
        "prior": "profitability is under-priced (Novy-Marx 2013; Asness, Frazzini & Pedersen "
                 "2019 quality-minus-junk)"},
    "quantamental_earnings_yield": {
        "cluster": "cross_sectional_fx",
        "prior": "high trailing E/P outperforms low (Basu 1977), point-in-time"},
}
